# PR Bot

This simple script is used to scan **Maven projects** in GitHub or GitHub Enterprise for outdated
dependencies and open pull requests to update them.


## Prerequisites

* git installed
* python modules in `requirements.txt` installed
* a GitHub or GitHub Enterprise account
* [an access token for that account with "repo" and "delete_repo" Oauth scopes enabled][1]


## Usage:

When you run `prbot.py`, you specify a pom artifact ID and a desired version. The script will
use GitHub's search API to find recently updated Maven repos whose pom.xml have that artifact ID
as a dependency. If that dependency's version is less than the desired version you specified,
the script will fork the repo and open a pull request.

```
python prbot.py --language java <pom artifactID> \
    <desired version> <commit_message_file> <username that is opening the PR> \
    <access token> [--delete-forks] [--at-mention-committers] [-v]
```

The script can also @mention recent committers and remind them by commenting on the PR
if they haven't merged it.

The commit message file should be formatted like below. The second line should be blank.

```
Commit title

Rest of commit message
```

For example:

```
python prbot.py --language java helios-testing 0.8.380 commit_message.sample davidxia \
    <access token> --delete-forks --at-mention-committers -v
```

See `prbot.py -h` for more info.

  [1]: https://help.github.com/articles/creating-an-access-token-for-command-line-use/

