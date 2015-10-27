#!/usr/bin/env python

"""Create pull requests to search and replace strings in GitHub repos."""

import argparse
from contextlib import contextmanager
from datetime import date
import datetime
import os
import json
import logging
import re
import urllib
import operator
import subprocess
import shutil
import time

from dateutil.relativedelta import relativedelta
import requests
from requests.auth import HTTPBasicAuth


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
REMINDER_INTERVAL_SECONDS = 2 * 24 * 60 * 60

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
    parser.add_argument('--delete-forks', action='store_true',
                        help='Delete your existing repository forks. This makes sure your fork '
                             'is synced with the base repository and that your pull '
                             'request doesn\'t have unintended commits.')
    parser.add_argument('--at-mention-committers', action='store_true', help='@ mention recent committers.')
    parser.add_argument('--domain',
                        help='The GitHub or GitHub Enterprise domain. Defaults to %s.' % DEFAULT_DOMAIN)
    parser.add_argument('--api-url',
                        help='The API URL of GitHub or GitHub Enterprise. Defaults to %s.' % DEFAULT_API_URL)
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Increase output verbosity.')
    parser.add_argument('old', help='Old string to replace.')
    parser.add_argument('new', help='Replacement string.')
    parser.add_argument('commit_message_file', help='File containing the Git commit message.')
    parser.add_argument('fork_owner', help='The owner of the git forks.')
    parser.add_argument('github_token', help='The personal access token of the owner of the git forks.')

    args = parser.parse_args()

    if args.verbosity > 0:
        logger.setLevel(logging.DEBUG)

    # if args.domain is not None:
    base_url = base_url_from_domain(args.domain) if args.domain is not None else DEFAULT_BASE_URL
    ssh_uri = ssh_uri_from_domain(args.domain) if args.domain is not None else DEFAULT_SSH_URI
    api_url = args.api_url if args.api_url is not None else DEFAULT_API_URL

    try:
        commit_msg_title, commit_msg = parse_commit_message_file(args.commit_message_file)
    except IOError as e:
        exit('Specify the path to a file containing the commit message.\n%s' % e)

    recently_pushed_repos = get_recently_pushed_repos(api_url, args.language, args.pushed_date)
    logger.info('Number of repos recently pushed: %d', len(recently_pushed_repos))

    remove_dir(CLONE_DIR)

    # search for the old string in each repo
    for repo in recently_pushed_repos:
        raw_url = find_outdated_string(base_url, api_url, repo, args.old)
        if raw_url is None:
            continue

        repo_parts = repo.split('/')
        repo_owner = repo_parts[0]
        repo_name = repo_parts[1]
        pr_branch = branch_name(commit_msg_title)

        # See if there's already an open pull request for the repo with the same title
        # TODO (dxia) We are assuming any pull request for this repo from this fork owner is the relevant one.
        pull_reqs = get_pull_requests(api_url, repo_owner, repo_name, args.fork_owner + ':' + pr_branch)
        if len(pull_reqs) > 0:
            logger.info('Already an open pull request for %s/%s from %s/%s:%s. See %s. Skipping.',
                        repo_owner, repo_name, args.fork_owner, repo_name, pr_branch,
                        pull_reqs[0]['html_url'])
            if args.at_mention_committers:
                at_mention_recent_committers(base_url, api_url, repo, pull_reqs[0]['number'], args.fork_owner,
                                             args.github_token)
            continue

        # Fork repo
        forked_repo = '%s/%s' % (args.fork_owner, repo_name)

        if args.delete_forks:
            logger.info('Deleting your fork %s if it exists.', forked_repo)
            if delete_repo(api_url, args.fork_owner, repo_name, args.github_token):
                logger.info('Successfully deleted your fork "%s/%s".', args.fork_owner, repo_name)

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

        with open(repo_file_path) as f:
            text = f.read()

        if args.old not in text:
            continue
        logger.info('File "%s" on master branch of repo %s has old string "%s". Editing...',
                    file_path, repo, args.old)

        new_text = text.replace(args.old, args.new)
        with open(repo_file_path, 'w') as f:
            f.write(new_text)

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
    m = re.search(r'master/+(.+)$', github_master_file_url)
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
    return True if r.status_code == requests.codes.no_content else False


def get_recently_pushed_repos(api_url, lang=None, pushed_date=None):
    """
    Get a list of repos in the form of 'owner/repo' that were recently pushed, i.e. updated.
    :param api_url:
    :param lang:
    :param pushed_date:
    :return:
    """
    if pushed_date:
        query_str = 'pushed:>%s' % pushed_date
    else:
        query_str = 'pushed:>%s' % DEFAULT_PUSHED_DATE
    if lang:
        query_str += '+language:%s' % lang

    r = requests.get('%ssearch/repositories?q=%s&sort=updated&per_page=%d'
                     % (api_url, urllib.quote(query_str, '/+'), RESULTS_PER_PAGE))

    results = json.loads(r.text)

    total_count = results['total_count']
    total_pages = total_count / RESULTS_PER_PAGE
    if total_count % RESULTS_PER_PAGE > 0:
        total_pages += 1

    curr_page = 1
    recently_pushed_repos = []

    for item in results['items']:
        recently_pushed_repos.append(item['full_name'])

    while curr_page < total_pages:
        curr_page += 1
        r = requests.get('%ssearch/repositories?q=%s&sort=updated&per_page=%d&page=%d'
                         % (api_url, urllib.quote('language:java+pushed:>2015-06-01', '/+'),
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
    return True if r.status_code == requests.codes.created else False


def pull_request_title(string):
    """
    Create a GitHub pull request title from a string.
    :param string:
    :return:
    """
    return string[:50]


def branch_name(string):
    """
    Create a git branch name from a string.
    :param string:
    :return:
    """
    return re.sub(r'\s+', '-', string)[:15]


def find_outdated_string(base_url, api_url, repo, old):
    """
    Search GitHub in the repo for the old string.
    Return None if we cannot find it.
    Otherwise return a string of the raw file's URL.
    :param base_url:
    :param api_url:
    :param repo:
    :param old:
    :return:
    """
    logger.info('Scanning repo %s...', repo)

    result = search_in_repo(api_url, repo, old)

    # Skip if no matches.
    if len(result['items']) < 1:
        return None

    html_url = result['items'][0]['html_url']
    raw_url = html_url_to_raw_url(base_url, html_url)
    text = requests.get(raw_url).text
    if old in text:
        # We found an outdated string
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
    :param repo:
    :param repo:
    :param pr_number:
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
    Get the age in days of the last @mention comment/reminder. Return None to indicate error or that no reminder has
    been posted.
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
            return (datetime.datetime.strptime(c['created_at'], '%Y-%m-%dT%H:%M:%SZ') - datetime.datetime.now()).seconds
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


if __name__ == '__main__':
    main()
