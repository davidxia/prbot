#!/usr/bin/env python

"""Create pull requests to update GitHub repos that are using old versions of pom dependencies."""
import argparse
from contextlib import contextmanager

from datetime import date
import datetime
import os
from dateutil.relativedelta import relativedelta
import json
import logging
import re
import urllib
import operator
import requests
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth
import semantic_version
import subprocess
import shutil
import time


def base_url_from_domain(domain):
    """
    Return GitHub base URL from GitHub domain.
    :param domain:
    :return:
    """
    return 'https://%s/' % domain


def ssh_uri_from_domain(domain):
    """
    Return GitHub SSH URI from GitHub domain.
    :param domain:
    :return:
    """
    return 'git@%s' % domain


DEFAULT_DOMAIN = 'github.com'
DEFAULT_BASE_URL = base_url_from_domain(DEFAULT_DOMAIN)
DEFAULT_API_URL = 'https://api.github.com/'
DEFAULT_SSH_URI = ssh_uri_from_domain(DEFAULT_DOMAIN)
RESULTS_PER_PAGE = 100
CLONE_DIR = 'repos'
LOG_FORMAT = '%(asctime)s %(levelname)s: %(message)s'
DEFAULT_PUSHED_DATE = (date.today() + relativedelta(months=-1)).strftime('%Y-%m-%d')
MAX_CMD_RETRIES = 10
CLONE_RETRY_INTERVAL_SEC = 10
REMINDER_INTERVAL_SECONDS = 7 * 24 * 60 * 60
MAX_GITHUB_RESULTS_PAGE = 10  # Only the first 1000 search results are available

logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', help='Searches repositories that are written in this language.')
    parser.add_argument('--pushed-date', help='Filters repositories based on date they were last updated. '
                                              'Must be in the format YYYY-MM-DD.')
    parser.add_argument('--no-pushed-date', action='store_true',
                        help='Do not limit to searching for repos pushed to '
                             'within the time specified by --pushed-date. '
                             'Overrides the --pushed-date flag.')
    parser.add_argument('--delete-forks', action='store_true',
                        help='Delete your existing repository forks. This makes sure your fork '
                             'is synced with the base repository and that your pull '
                             'request doesn\'t have unintended commits.')
    parser.add_argument('--at-mention-committers', action='store_true', help='@ mention recent committers.')
    parser.add_argument('--domain',
                        help='The GitHub or GitHub Enterprise domain. Defaults to %s.' % DEFAULT_DOMAIN)
    parser.add_argument('--api-url',
                        help='The API URL of GitHub or GitHub Enterprise. Defaults to %s.' % DEFAULT_API_URL)
    parser.add_argument('--group-id', help='Limit the search to a specific maven group id.')
    parser.add_argument('--dep-type', default='dependency',
                        help='The type of dependency. '
                             'Specify "--dep-type plugin" to replace outdated '
                             'plugins under build/plugins.')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Increase output verbosity.')
    parser.add_argument('artifact_id',
                        help='Artifact ID to use when creating helios job name. The default is to look in pom.xml')
    parser.add_argument('version', help='Version of the artifact ID desired.')
    parser.add_argument('commit_message_file', help='File containing the Git commit message.')
    parser.add_argument('fork_owner', help='The owner of the git forks.')
    parser.add_argument('github_token', help='The personal access token of the owner of the git forks.')

    args = parser.parse_args()

    if args.verbosity > 0:
        logger.setLevel(logging.DEBUG)

    if args.dep_type == 'plugin':
        dep_parent = './build/plugins'
        dep_children = 'plugin'
    else:
        dep_parent = 'dependencies'
        dep_children = 'dependency'

    # if args.domain is not None:
    base_url = base_url_from_domain(args.domain) if args.domain is not None else DEFAULT_BASE_URL
    ssh_uri = ssh_uri_from_domain(args.domain) if args.domain is not None else DEFAULT_SSH_URI
    api_url = args.api_url if args.api_url is not None else DEFAULT_API_URL

    # Try to validate the version string. Script will exit if any exception is raised
    semantic_version.Version(args.version)

    try:
        commit_msg_title, commit_msg = parse_commit_message_file(args.commit_message_file)
    except IOError as e:
        exit('Specify the path to a file containing the commit message.\n%s' % e)

    pr_branch = branch_name(commit_msg_title)

    # Remind committers for open PRs
    if args.at_mention_committers:
        remind_prs(base_url, api_url, pr_branch, args.fork_owner, args.github_token)

    recently_pushed_repos = get_recently_pushed_repos(
        api_url, lang=args.language, pushed_date=args.pushed_date,
        no_pushed_date=args.no_pushed_date)
    logger.info('Number of repos recently pushed: %d', len(recently_pushed_repos))

    remove_dir(CLONE_DIR)

    # search for the artifact ID in poms in each repo
    for repo in recently_pushed_repos:
        raw_url = find_outdated_pom_dependency(
            base_url, api_url, repo, args.artifact_id, args.version, dep_parent,
            dep_children, group_id=args.group_id)
        if raw_url is None:
            continue

        repo_parts = repo.split('/')
        repo_owner = repo_parts[0]
        repo_name = repo_parts[1]

        # See if there's already an open pull request for the repo with the same title
        # TODO (dxia) We are assuming any pull request for this repo from this fork owner is the relevant one.
        pull_reqs = get_pull_requests(api_url, repo_owner, repo_name, branch=args.fork_owner + ':' + pr_branch)
        if len(pull_reqs) > 0:
            logger.info('Already an open pull request for %s/%s from %s/%s:%s. See %s. Skipping.',
                        repo_owner, repo_name, args.fork_owner, repo_name, pr_branch,
                        pull_reqs[0]['html_url'])
            continue

        # Fork repo
        forked_repo = '%s/%s' % (args.fork_owner, repo_name)

        if args.delete_forks:
            logger.info('Deleting your fork %s if it exists.', forked_repo)
            status = delete_repo(api_url, args.fork_owner, repo_name, args.github_token)
            if status == requests.codes.no_content:
                logger.info('Successfully deleted your fork "%s/%s".', args.fork_owner, repo_name)
            else:
                logger.info('Couldn\'t delete your fork "%s/%s". Got status code %d.'
                            % (args.fork_owner, repo_name, status))

        if not fork_repo(api_url, repo_owner, repo_name, args.github_token):
            exit('Couldn\'t fork repository %s to owner %s.' % (repo, args.fork_owner))

        # Sleep to give GitHub enough time to fork.
        time.sleep(CLONE_RETRY_INTERVAL_SEC)
        repo_clone_path = clone_repo(ssh_uri, args.fork_owner, repo_name, CLONE_DIR, retry=True)
        if repo_clone_path is None:
            exit('Failed to clone repo %s/%s.', args.fork_owner, repo_name)

        file_path = file_path_from_html_url(raw_url)
        if file_path is None:
            logger.info('File "%s" no longer exists in the master branch of repo %s. Skipping.',
                        file_path, repo_clone_path)
            continue

        repo_file_path = os.path.join(repo_clone_path, file_path)

        with open(repo_file_path.decode('ascii')) as f:
            pom_text = f.read()

        pom_root = ElementTree.XML(pom_text)

        deps = pom_root.find(dep_parent)
        if deps is None:
            logger.warn('Couldn\'t find any dependencies in pom.xml in at %s.', repo_file_path)
            continue

        for j in deps.findall(dep_children):
            artifact_id_el = j.find('artifactId')
            version_string_el = j.find('version')
            group_id_el = j.find('groupId')

            if artifact_id_el is None or artifact_id_el.text != args.artifact_id or version_string_el is None:
                continue

            version_string = version_string_el.text
            if semantic_version.Version(version_string) >= semantic_version.Version(args.version):
                continue

            if args.group_id is not None and group_id_el is not None and args.group_id != group_id_el.text:
                continue

            logger.info('File "%s" on master branch of repo %s has %s version %s. Editing...',
                        file_path, repo, args.artifact_id, version_string)

            new_pom_text = pom_text.replace('<version>%s</version>' % version_string_el.text,
                                            '<version>%s</version>' % args.version, 1)
            with open(repo_file_path, 'w') as f:
                f.write(new_pom_text)

            # Git commit file and push to Github
            branch_add_commit_push(file_path, pr_branch, commit_msg, repo_clone_path)
            logger.info('Pushed new branch %s to repo %s.', pr_branch, forked_repo)

            pr_number = create_pull_request(
                api_url, repo_owner, repo_name, args.github_token,
                pull_request_title(commit_msg_title),
                '%s:%s' % (args.fork_owner, pr_branch), body=commit_msg)

            if pr_number is None:
                exit('Couldn\'t create pull request from head repo %s:%s to base repo %s.'
                     % (forked_repo, pr_branch, repo))

            pr_url = '%s%s/pull/%d' % (base_url, repo, pr_number)
            logger.info('Created pull request. See %s.', pr_url)

            if args.at_mention_committers:
                at_mention_recent_committers(base_url, api_url, repo, pr_number, args.fork_owner, args.github_token)


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


def html_url_to_raw_url(base_url, html_url):
    """
    Return a URL to the raw file on the master branch from Github given an HTML URL from a commit hash.
    E.g. https://github.com/spotify/helios/blob/ea5e46dc0bd3a996d57d5ec4568ba758e4d59d24//pom.xml ->
    https://github.com/raw/spotify/helios/master//pom.xml.
    :param base_url:
    :param html_url:
    :return:
    """
    t = re.sub(r'blob/[a-z0-9]+?/', 'blob/master/', html_url)
    t = re.sub(r'^%s' % base_url, '%sraw/' % base_url, t)
    return t.replace('/blob/master/', '/master/')


def file_path_from_html_url(github_master_file_url):
    """
    Return the file path from a Github HTML URL from master branch.
    E.g. https://github.com/spotify/helios/blob/master/.gitignore -> .gitignore.
    :param github_master_file_url:
    :return:
    """
    m = re.search(r'master/+(.+)$', urllib.unquote(github_master_file_url))
    if m is not None:
        return m.group(1)


def branch_add_commit_push(file_path, git_branch_name, commit_msg, base_path=None):
    """
    Git commit a file. cd to base_path if not None.
    :param file_path:
    :param git_branch_name:
    :param commit_msg:
    :param base_path:
    :return:
    """
    if base_path is not None:
        with in_dir(base_path):
            run_cmd(['git', 'checkout', '-b', git_branch_name], stderr=subprocess.STDOUT)
            run_cmd(['git', 'add', file_path], stderr=subprocess.STDOUT)
            run_cmd(['git', 'commit', '-m', commit_msg], stderr=subprocess.STDOUT)
            run_cmd(['git', 'push', '-f', '--set-upstream', 'origin', git_branch_name],
                    stderr=subprocess.STDOUT)
    return True


def run_cmd(cmd_parts, stderr=None, retry=False):
    """
    Run a shell command. cmd_parts must be a list of strings.
    :param cmd_parts:
    :param stderr:
    :param retry:
    :return:
    """
    logger.info('%s "%s"', 'Running command', ' '.join(cmd_parts))

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
            logger.info('Failed to run command. Retries: %d of %d.',  retries, MAX_CMD_RETRIES)
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


def fork_repo(api_url, owner, repo, token, organization=None):
    """
    Fork a repo from owner/repo to organization.
    :param api_url:
    :param owner:
    :param repo:
    :param token:
    :param organization:
    :return:
    """
    data = None
    if organization is not None:
        data = json.dumps({'organization': organization})

    r = requests.post('%srepos/%s/%s/forks' % (api_url, owner, repo), data=data,
                      auth=HTTPBasicAuth(token, 'x-oauth-basic'))
    if r.status_code == requests.codes.accepted:
        return True
    else:
        print r.content
        return False


def create_pull_request(api_url, owner, repo, token, title, head, base='master', body=None):
    """
    Create a GitHub pull request and return the pull request number if successful.
    None if not successful.
    :param api_url:
    :param owner:
    :param repo:
    :param token:
    :param title:
    :param head:
    :param base:
    :param body:
    :return:
    """
    r = requests.post('%srepos/%s/%s/pulls' % (api_url, owner, repo), data=json.dumps({
        'title': title,
        'head': head,
        'base': base,
        'body': body,
    }), auth=HTTPBasicAuth(token, 'x-oauth-basic'))

    if r.status_code != requests.codes.created:
        return None

    response = json.loads(r.text)
    return response.get('number', None)


def delete_repo(api_url, owner, repo, token):
    """
    Delete git repo.
    :param api_url:
    :param owner:
    :param repo:
    :param token:
    :return:
    """
    r = requests.delete('%srepos/%s/%s' % (api_url, owner, repo),
                        auth=HTTPBasicAuth(token, 'x-oauth-basic'))
    return r.status_code


def get_recently_pushed_repos(api_url, lang=None, pushed_date=None,
                              no_pushed_date=False):
    """
    Get a list of repos in the form of 'owner/repo' that were recently pushed, i.e. updated.
    :param api_url:
    :param lang:
    :param pushed_date:
    :param no_pushed_date: If true, do not limit search to repos pushed to
                           since specified date.
    :return:
    """
    query_str = ''

    if not no_pushed_date:
        if pushed_date:
            query_str = 'pushed:>%s' % pushed_date
        else:
            query_str = 'pushed:>%s' % DEFAULT_PUSHED_DATE

    if lang:
        query_str += '+language:%s' % lang

    r = requests.get('%ssearch/repositories?q=%s&sort=updated&per_page=%d'
                     % (api_url, urllib.quote(query_str, '/+'),
                        RESULTS_PER_PAGE))

    results = json.loads(r.text)

    total_count = results['total_count']
    total_pages = total_count / RESULTS_PER_PAGE
    if total_count % RESULTS_PER_PAGE > 0:
        total_pages += 1

    curr_page = 1
    recently_pushed_repos = []

    for item in results['items']:
        recently_pushed_repos.append(item['full_name'])

    while curr_page < min(MAX_GITHUB_RESULTS_PAGE, total_pages):
        curr_page += 1
        r = requests.get('%ssearch/repositories?q=%s&sort=updated&per_page=%d&page=%d'
                         % (api_url, urllib.quote(query_str, '/+'),
                            RESULTS_PER_PAGE, curr_page))

        if r.status_code == requests.codes.forbidden:
            j = json.loads(r.text)
            logger.warn('%s: %s.', j['message'], j['documentation_url'])
            return recently_pushed_repos
        elif r.status_code != requests.codes.ok:
            logger.warn('%s returned status code %d.', r.url, r.status_code)

        results = json.loads(r.text)
        for item in results['items']:
            recently_pushed_repos.append(item['full_name'])

    return recently_pushed_repos


def search_in_repo(api_url, repo, string, lang=None):
    """
    Search in repo for string and language.
    :param api_url:
    :param repo:
    :param string:
    :param lang:
    :return:
    """
    query = '%s repo:%s' % (string, repo)
    if lang is not None:
        query += ' language:"%s"' % lang
    r = requests.get('%ssearch/code?q=%s' % (api_url, urllib.quote(query)))
    return json.loads(r.text)


def get_pull_requests(api_url, owner, repo, branch=None):
    """
    Get pull requests for owner/repo.
    :param api_url:
    :param owner:
    :param repo:
    :param branch: Filter pulls by head user and branch name in the format of user:ref-name.
    :return:
    """
    url = '%srepos/%s/%s/pulls' % (api_url, owner, repo)
    params = None if branch is None else {'head': branch}
    r = requests.get(url, params=params)
    return json.loads(r.text)


def get_recent_committers(api_url, repo):
    """
    Get recent committers for repo ordered by frequency of commits descending.
    :param api_url:
    :param repo:
    :return:
    """
    r = requests.get('%srepos/%s/commits' % (api_url, repo))
    if r.status_code != requests.codes.ok:
        logger.error('Could not get list of commits from repo "%s". Returning empty list for recent committers.', repo)
        return []
    commits = json.loads(r.text)

    recent_committers = {}
    for c in commits:
        if c.get('committer') is not None and c['committer'].get('login') is not None:
            committer = c['committer']['login']
            if committer not in recent_committers:
                recent_committers[committer] = 1
            else:
                recent_committers[committer] += 1
    return [c[0] for c in sorted(recent_committers.items(), key=operator.itemgetter(1), reverse=True)]


def comment_on_issue(api_url, repo, issue_number, comment, token):
    """
    Comment on an issue.
    :param api_url:
    :param repo:
    :param issue_number:
    :param comment:
    :param token:
    :return:
    """
    r = requests.post('%srepos/%s/issues/%d/comments' % (api_url, repo, issue_number),
                      data=json.dumps({'body': comment}), auth=HTTPBasicAuth(token, 'x-oauth-basic'))
    return r.status_code == requests.codes.created


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
    s = re.sub(r'[:~\^\\]+', '-', s)
    return s[:15]


def find_outdated_pom_dependency(
        base_url, api_url, repo, dependency, minimum_version, target_parent,
        target_children, group_id=None):
    """
    Search GitHub in the repo for the dependency.
    Return None if we cannot find a version of it less than the specified minimum version.
    Otherwise return a string of the raw file's URL.
    :param base_url:
    :param api_url:
    :param repo:
    :param dependency:
    :param minimum_version:
    :param target_parent: The name of the XML element under which to search
    :param target_children: The name of the XML elements to search
    :param group_id: Optional group ID to limit searches to.
    :return:
    """
    logger.info('Scanning repo %s...', repo)

    result = search_in_repo(api_url, repo, dependency, lang='Maven POM')

    # Skip if no matches.
    if len(result['items']) < 1:
        return None

    html_url = result['items'][0]['html_url']
    raw_url = html_url_to_raw_url(base_url, html_url)
    xml = requests.get(raw_url).text
    try:
        root = ElementTree.XML(xml)
    except UnicodeEncodeError as e:
        logger.warn('Could not parse xml of repo %s.\n%s', repo, e)
        return None

    deps = root.find(target_parent)
    if deps is None:
        return None

    for i in deps.findall(target_children):
        artifact_id_el = i.find('artifactId')
        version_string_el = i.find('version')
        group_id_el = i.find('groupId')

        if artifact_id_el is None or artifact_id_el.text != dependency or version_string_el is None:
            continue

        version_string = version_string_el.text
        if semantic_version.Version(version_string) >= semantic_version.Version(minimum_version):
            continue

        if group_id is not None and group_id_el is not None and group_id != group_id_el.text:
            continue

        logger.info('According to the search index, repo %s has %s version %s',
                    repo, dependency, version_string)

        # We found an outdated dependency
        return raw_url

    # We didn't find an outdated dependency
    return None


def clone_repo(ssh_uri, owner, repo, clone_dir, retry=False):
    """
    Clone a repo with retries. Return the path of the cloned repo or None on failure.
    :param ssh_uri:
    :param owner:
    :param repo:
    :param clone_dir
    :param retry:
    :return:
    """
    repo_uri = '%s:%s/%s' % (ssh_uri, owner, repo)
    repo_clone_path = os.path.join(clone_dir, repo)

    try:
        run_cmd(['git', 'clone', repo_uri, repo_clone_path], stderr=subprocess.STDOUT, retry=retry)
    except subprocess.CalledProcessError as e:
        logger.info('Failed to clone repo %s into %s.\n%s', repo_uri, repo_clone_path, e)
        return None
    return repo_clone_path


def at_mention_recent_committers(base_url, api_url, repo, pr_number, commenting_user, github_token):
    """
    @Mention recent committers
    :param base_url:
    :param api_url:
    :param repo: owner/repo
    :param pr_number:
    :param commenting_user:
    :param github_token:
    :return:
    """
    # Do not remind/spam too frequently
    last_reminder_age = get_last_reminder_age(api_url, repo, pr_number, commenting_user)
    if last_reminder_age is not None and REMINDER_INTERVAL_SECONDS > last_reminder_age:
        return

    recent_committers = get_recent_committers(api_url, repo)
    comment = ' '.join(['@' + rc for rc in recent_committers])
    if not comment_on_issue(api_url, repo, pr_number, comment, github_token):
        pr_url = '%s%s/pulls/%d' % (base_url, repo, pr_number)
        logger.error('Failed to @mention committers "%s" on PR %s', comment, pr_url)
    else:
        logger.info('@ mentioned recent committers: "%s".', comment)


def get_last_reminder_age(api_url, repo, pr_number, commenting_user):
    """
    Get the age in seconds since the last @mention comment/reminder.
    Return None to indicate error or that no reminder has been posted.
    :param api_url:
    :param repo:
    :param pr_number:
    :param commenting_user:
    :return: Number of seconds ago
    """
    r = requests.get('%srepos/%s/issues/%d/comments' % (api_url, repo, pr_number))
    if r.status_code != requests.codes.ok:
        logger.error('Could not get comments from repo "%s" and issue #%d. Returning -1.', repo, pr_number)
        return None
    comments = json.loads(r.text)

    for c in comments[::-1]:
        if c['user']['login'] == commenting_user and c['body'].startswith('@'):
            return (datetime.datetime.now() -
                    datetime.datetime.strptime(c['created_at'], '%Y-%m-%dT%H:%M:%SZ')).total_seconds()
    return None


def parse_commit_message_file(file_path):
    """
    Parse commit message title and body from file.
    :param file_path:
    :return:
    """
    with open(file_path) as f:
        commit_lines = f.readlines()
        commit_msg_title = commit_lines[0]
        commit_msg = ''.join(commit_lines)
    return commit_msg_title, commit_msg


def list_repos(api_url, token):
    """
    Return a list of all the user's repos
    :param api_url:
    :param token:
    :return: a list of repo names
    """
    repo_names = []

    r = requests.get('%suser/repos' % api_url, auth=HTTPBasicAuth(token, 'x-oauth-basic'))
    repos = json.loads(r.text)
    logger.info('User has %s repos' % len(repos))

    for repo in repos:
        repo_names.append(repo['name'])

    return repo_names


def remind_prs(base_url, api_url, pr_branch, username, token):
    """
    For all this user's open PRs, comment on them with @ mentions as a reminder
    :param base_url:
    :param api_url:
    :param pr_branch:
    :param username:
    :param token:
    :return:
    """
    repos = list_repos(api_url, token)

    for repo in repos:
        fork_owner = get_fork_owner(api_url, username, repo, token)
        pull_reqs = get_pull_requests(api_url, fork_owner, repo, branch=username + ':' + pr_branch)
        if not isinstance(pull_reqs, list) or len(pull_reqs) < 1:
            continue
        at_mention_recent_committers(base_url, api_url, fork_owner + '/' + repo, pull_reqs[0]['number'],
                                     username, token)


def get_fork_owner(api_url, fork_owner, repo, token):
    """
    Get the username of the parent repo of the forked repo
    :param api_url:
    :param fork_owner: The username of the user who owns the forked repo
    :param repo:
    :param token:
    :return: The name of the owner of the parent repo. None if the repo is not a fork.
    """
    r = requests.get('%srepos/%s/%s' % (api_url, fork_owner, repo), auth=HTTPBasicAuth(token, 'x-oauth-basic'))
    repo = json.loads(r.text)
    if 'parent' in repo:
        return repo['parent']['owner']['login']
    return None


if __name__ == '__main__':
    main()
