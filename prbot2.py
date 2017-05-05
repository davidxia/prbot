#!/usr/bin/env python

"""Create pull requests to search and replace strings in GitHub repos."""

import argparse
import datetime
import logging
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import date

import requests
from dateutil.relativedelta import relativedelta
from github import Github
from github.AuthenticatedUser import AuthenticatedUser
from github.GithubException import UnknownObjectException, GithubException

DEFAULT_DOMAIN = 'github.com'
DEFAULT_API_URL = 'https://api.github.com'
RESULTS_PER_PAGE = 100
CLONE_DIR = 'repos'
LOG_FORMAT = '%(asctime)s %(levelname)s: %(message)s'
DEFAULT_PUSHED_DATE = (date.today() + relativedelta(months=-1))\
    .strftime('%Y-%m-%d')
MAX_CMD_RETRIES = 10
CLONE_RETRY_INTERVAL_SEC = 10
REMINDER_INTERVAL_DAYS = 7
MAX_GITHUB_RESULTS_PAGE = 10  # Only first 1000 search results are available

logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--language',
        help='Searches repositories that are written in this language.')
    parser.add_argument(
        '--pushed',
        default=DEFAULT_PUSHED_DATE,
        help='Filters code search based on last push to repos. '
             'Must be in the format [><=]YYYY-MM-DD. '
             'Defaults to repos last pushed within the last month.')
    parser.add_argument(
        '--no-pushed', action='store_true',
        default=False,
        help='Do not limit to searching for repos pushed to within the time '
             'specified by --pushed. Overrides the --pushed flag. '
             'Defaults to false')
    parser.add_argument(
        '--at-mention-committers', action='store_true',
        help='@ mention recent committers.')
    parser.add_argument(
        '--api-url',
        help='The API URL of GitHub or GitHub Enterprise. Defaults to %s.'
             % DEFAULT_API_URL)
    parser.add_argument(
        '-v', '--verbosity', action='count', default=0,
        help='Increase output verbosity.')
    parser.add_argument(
        'old', help='Old string to replace. Can be regex expression.')
    parser.add_argument(
        'new', help='Replacement string.')
    parser.add_argument(
        'commit_message_file',
        help='File containing the Git commit message.')
    parser.add_argument('fork_owner', help='The owner of the git forks.')
    parser.add_argument(
        'github_token',
        help='The personal access token of the owner of the git forks.')

    args = parser.parse_args()

    if args.verbosity > 0:
        logger.setLevel(logging.DEBUG)

    gh = Github(args.github_token, base_url=args.api_url)
    authed_user = gh.get_user()
    if not isinstance(authed_user, AuthenticatedUser):
        exit('PyGithub did not return AuthenticatedUser')

    try:
        commit_msg_title, commit_msg = parse_commit_message_file(
            args.commit_message_file)
    except IOError as e:
        exit('Specify path to a file containing the commit message.\n%s' % e)

    # Remind committers for open PRs
    if args.at_mention_committers:
        remind_open_pulls(gh)

    remove_dir(CLONE_DIR)

    logger.info('Searching all code...')
    qualifiers = {'language': args.language}
    if not args.no_pushed:
        qualifiers['pushed'] = args.pushed

    # noinspection PyUnboundLocalVariable
    pr_branch = branch_name(commit_msg_title)

    content_files = gh.search_code('%s' % args.old, **qualifiers)
    # TODO find unique repos to which these files belong so we can open one
    # PR per repo instead of per file?
    for cf in content_files:
        logger.debug('Searching %s', cf.repository.full_name)
        # Github search returns fuzzy results. Check the raw file has exact
        # string before cloning whole repo.
        if not string_in_file(cf.git_url, args.old):
            continue

        head = authed_user.login + ':' + pr_branch
        repo_pulls = cf.repository.get_pulls(head=head)

        # See if repo already has an open PR with the same branch name
        # TODO Doing this check here without doing the TODO above might skip
        # over other files in the other that also have the old string.
        existing_pull = False
        for pull in repo_pulls:
            existing_pull = True
            logger.info('Already an open PR for %s from %s. See %s. Skipping.',
                        cf.repository.full_name, head, pull.html_url)
            break
        if existing_pull:
            continue

        try:
            repo_name = cf.repository.name
            fork = authed_user.get_repo(repo_name)
            # Check the parent of the fork is the ContentFile's repo to prevent
            # false matches.
            if fork.parent is None:
                logger.warn('%s has no parent!!' % fork.full_name)
            if fork.parent.owner.login == authed_user.login:
                logger.debug('Skipping code search matches on own repo %s',
                             cf.repository.full_name)
            if fork.parent is None \
                    or fork.parent.full_name != cf.repository.full_name:
                raise UnknownObjectException(None, None)
        except UnknownObjectException:
            # Fork repo
            # noinspection PyUnresolvedReferences
            fork = authed_user.create_fork(cf.repository)
            # Sleep to give GitHub enough time to fork.
            time.sleep(CLONE_RETRY_INTERVAL_SEC)

        # Clone forked repo
        clone_path = clone_repo(fork.clone_url, cf.repository.owner.login,
                                repo_name, CLONE_DIR,
                                authed_user.login, args.github_token,
                                retry=True)
        if clone_path is None:
            logger.warning('Failed to clone repo %s/%s.'
                           % (args.fork_owner, repo_name))
            continue

        # Sync in case fork is behind upstream.
        # This can happen if upstream repo's name changed after forking.
        # Then we won't find the authed_user's repo with the new name,
        # and create_fork() doesn't sync the fork.
        sync_fork_with_upstream(clone_path, cf.repository)

        file_path = os.path.join(clone_path, cf.path.lstrip('/'))

        with open(file_path.decode('ascii')) as f:
            text = f.read()

        m = re.search(r'%s\b' % args.old, text)
        if m is None:
            logger.debug('Did not find old string "%s" in %s. Skipping.',
                         args.old, file_path)
            continue
        logger.info('Found old string "%s" in %s. Editing',
                    args.old, file_path)

        new_text = text.replace(args.old, args.new)
        with open(file_path, 'w') as f:
            f.write(new_text)

        # Git commit file and push to Github
        branch_add_commit_push(file_path, pr_branch, commit_msg, clone_path)
        logger.info('Pushed new branch %s to repo %s.',
                    pr_branch, fork.html_url)

        try:
            pull = cf.repository.create_pull(
                pull_request_title(commit_msg_title), commit_msg,
                cf.repository.default_branch,
                '%s:%s' % (authed_user.login, pr_branch))
        except GithubException as e:
            # For some reason listing PRs and filtering to `head` doesn't work
            # sometimes. This will then fail because the PR already exists.
            logger.warn(e)

        logger.info('Created PR %s.', pull.html_url)

        if args.at_mention_committers:
            at_mention_recent_committers(pull, datetime.datetime.now(),
                                         authed_user.login)


def string_in_file(git_url, string):
    """
    Search git URL for str.
    :param git_url: URL
    :param string: String to find.
    :return: True if string is found. False otherwise.
    """
    headers = {'Accept': 'application/vnd.github.v3.raw'}
    try:
        text = requests.get(git_url, headers=headers).text
        m = re.search(r'%s\b' % string, text)
        return m is not None
    except requests.exceptions.ConnectionError as e:
        logger.warn(e)
    return False


def remove_dir(dir_name):
    """
    Create directory if it doesn't exist. If it does, make it empty.
    :param dir_name:
    :return:
    """
    logger.info('Removing directory "%s" if it exists.', dir_name)
    try:
        shutil.rmtree(dir_name)
    except OSError:
        pass


def branch_add_commit_push(file_path, new_branch, commit_msg, base_path):
    """
    Git commit a file. cd to base_path if not None.
    :param file_path:
    :param new_branch: New git branch name
    :param commit_msg:
    :param base_path:
    :return:
    """
    with in_dir(base_path):
        run_cmd(['git', 'checkout', '-b', new_branch],
                stderr=subprocess.STDOUT)
        # TODO Seems brittle here; want to remove base part of the file path
        run_cmd(['git', 'add', file_path.split(base_path + '/')[1]],
                stderr=subprocess.STDOUT)
        run_cmd(['git', 'commit', '-m', commit_msg], stderr=subprocess.STDOUT)
        run_cmd(['git', 'push', '-f', '--set-upstream', 'origin', new_branch],
                stderr=subprocess.STDOUT)
    return True


def run_cmd(cmd_parts, stderr=None, retry=False, log_msg=None):
    """
    Run a shell command. cmd_parts must be a list of strings.
    :param cmd_parts:
    :param stderr:
    :param retry:
    :param log_msg: Overriding log message. Good when cmd has sensitive info.
    :return:
    """
    if log_msg is not None:
        logger.debug(log_msg)
    else:
        logger.debug('%s "%s"', 'Running command', ' '.join(cmd_parts))

    success = False
    retries = 0
    output = None

    while not success and retries < MAX_CMD_RETRIES:
        try:
            output = subprocess.check_output(cmd_parts, stderr=stderr)
            success = True
        except subprocess.CalledProcessError as e:
            if not retry:
                raise e
            logger.info('Failed to run command. Retries: %d of %d.',
                        retries, MAX_CMD_RETRIES)
            output = e.message
            retries += 1
            time.sleep(CLONE_RETRY_INTERVAL_SEC)

    return output


@contextmanager
def in_dir(path):
    """
    Switch to a path, do something, then switch back.
    :param path:
    :return:
    """
    saved_path = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(saved_path)


def get_recent_committers(repo):
    """
    Get recent committers for repo ordered by frequency of commits descending.
    :param repo: github.Github.Repository
    :return: A set of strings representing recent committers' usernames
    """
    recent_committers = set()

    for c in repo.get_commits().get_page(0):
        if c.committer is None:
            continue
        recent_committers.add(c.committer.login)

    return recent_committers


def pull_request_title(string):
    """
    Create a GitHub pull request title from a string.
    :param string:
    :return:
    """
    return string[:50]


def branch_name(string):
    """
    Create a git branch name from a string. Remove invalid characters.
    :param string:
    :return:
    """
    s = re.sub(r'\s+', '-', string)
    s = re.sub(r'[:~^\\]+', '-', s)
    return s[:15]


def clone_repo(clone_url, parent_owner, repo, clone_dir, login, token,
               retry=False):
    """
    Clone repo with retries. Return path of the cloned repo or None on failure.
    :param clone_url: URL of the form https://../.git
    :param parent_owner: Name of parent repo's owner.
                         To prevent collisions on repo name.
    :param repo: Name of repo
    :param clone_dir Directory into which to clone
    :param login: Username of current user
    :param token: Corresponding access token of current user
    :param retry: Whether to retry
    :return:
    """
    repo_clone_path = os.path.join(clone_dir, '%s_%s' % (parent_owner, repo))

    # If it exists, assume it's already cloned
    if os.path.isdir(repo_clone_path):
        return
    partial_clone_url = clone_url.split('https://')[1]
    authed_clone_url = 'https://%s:%s@%s' % (login, token, partial_clone_url)

    try:
        run_cmd(['git', 'clone', authed_clone_url, repo_clone_path],
                stderr=subprocess.STDOUT, retry=retry,
                log_msg='Cloning %s' % clone_url)
    except subprocess.CalledProcessError as e:
        logger.info('Failed to clone repo %s into %s.\n%s', clone_url,
                    repo_clone_path, e)
        return None
    return repo_clone_path


def sync_fork_with_upstream(repo_path, parent_repo):
    """
    Sync the repo's default branch with upstream's default branch
    :param repo_path: path to clone of the forked repo
    :param parent_repo: github.Github.Repository
    :return:
    """
    default_branch = parent_repo.default_branch
    upstream = 'upstream'

    with in_dir(repo_path):
        run_cmd(['git', 'checkout', default_branch], stderr=subprocess.STDOUT)

        try:
            run_cmd(['git', 'remote', 'add', upstream, parent_repo.clone_url],
                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            # Ignore non-zero exit code; we'll assume it's because remote exists
            pass

        # Go back in case upstream was force pushed
        try:
            run_cmd(['git', 'reset', '--hard', 'HEAD~10'],
                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            # Ignore in case there aren't that many commits
            pass

        run_cmd(['git', 'pull', upstream, default_branch],
                stderr=subprocess.STDOUT)

        run_cmd(['git', 'push', '-f', 'origin', default_branch],
                stderr=subprocess.STDOUT)


def at_mention_recent_committers(pull, now, commenting_user):
    """
    @Mention recent committers
    :param pull: github.PullRequest.PullRequest
    :param now: datetime.datetime
    :param commenting_user:
    :return:
    """
    # Do not remind/spam too frequently
    last_reminder_datetime = get_last_reminder_datetime(pull, commenting_user)
    if last_reminder_datetime is not None \
            and (now - last_reminder_datetime).days < REMINDER_INTERVAL_DAYS:
        logger.debug('Last @ mention reminder for PR %s was less than a week '
                     'ago.', pull.html_url)
        return

    # We can't get collaborators even though that'd make more sense because
    # you need push rights to view collaborators. Just hope some of the recent
    # committers are also collaborators.
    # TODO mention only 4 or so recent committers?
    recent_committers = get_recent_committers(pull.base.repo)
    comment = 'Please review. ' \
              + ' '.join(['@' + rc for rc in recent_committers])
    pull.create_issue_comment(comment)
    logger.info('@ mentioned recent committers: "%s" on PR %s.',
                comment, pull.html_url)


def get_last_reminder_datetime(pull, commenting_user):
    """
    Get the datetime of the last @mention comment/reminder by the
    commenting_user. Return None to indicate error or that no reminder has been
    posted.
    :param pull:
    :param commenting_user:
    :return: datetime
    """
    for comment in pull.get_issue_comments().reversed:
        if comment.user.login == commenting_user:
            return comment.created_at
    return None


def parse_commit_message_file(file_path):
    """
    Parse commit message title and body from file.
    :param file_path:
    :return:
    """
    with open(file_path) as f:
        commit_msg = f.read()
        commit_msg_title = commit_msg.splitlines()[0]
    return commit_msg_title, commit_msg


def remind_open_pulls(gh):
    """
    For all this user's open PRs, comment on them with @ mentions as a reminder
    :param gh: github.Github client
    :return:
    """
    user = gh.get_user()
    issues = gh.search_issues('', state='open', author=user.login, type='pr')
    now = datetime.datetime.now()

    for issue in issues:
        pull = issue.repository.get_pull(issue.number)
        at_mention_recent_committers(pull, now, user.login)


def html_url_to_raw_url(base_url, html_url):
    """
    Return a URL to the raw file on the master branch from Github given an HTML
    URL from a commit hash.
    E.g. https://github.com/spotify/helios/blob/ea5e46dc0bd3a996/pom.xml ->
    https://github.com/raw/spotify/helios/master/pom.xml.
    :param base_url:
    :param html_url:
    :return:
    """
    t = re.sub(r'blob/[a-z0-9]+?/', 'blob/master/', html_url)
    t = re.sub(r'^%s' % base_url, '%sraw/' % base_url, t)
    return t.replace('/blob/master/', '/master/')


if __name__ == '__main__':
    main()
