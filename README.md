# PR Bot

This script creates pull requests to find and replace strings in Github or
Github Enterprise for outdated dependencies and open pull requests to update
them. It can also create PRs to update **Maven projects**'s dependencies.


## Prerequisites

* git installed
* python modules in `requirements.txt` installed
* a GitHub or GitHub Enterprise account
* [an access token for that account with "repo" and "delete_repo" Oauth scopes enabled][1]
  * configure git to [cache your password][git-cache-password]
  * log into github.com with your username and access token


## Usage:

**Warning: Be careful when running the bot. If you use the `--delete-forks` switch you might unintentionally delete
repos. You should create a separate GitHub account specifically for this bot.**

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
python prbot2.py --no-pushed 'old-string' 'new-string' commit_message prbot \
    <access token> --at-mention-committers
```

or

```
python prbot.py --language java helios-testing 0.8.380 commit_message.example davidxia \
    <access token> --delete-forks --at-mention-committers -v
```

### Using a different SSH key

If you generated a new SSH key for a bot account, add the public key to the bot's github account
and put the private key on the machine which runs the script and modify `~/.ssh/config`.

```
Host github.com
  IdentityFile ~/.ssh/id_rsa.prbot
  IdentitiesOnly yes
```

### Usage with GitHub Enterprise

The script defaults to using github.com. If you have an Enterprise installation, specify
`--domain` and `--api-url`.

See `prbot.py -h` for more info.

  [1]: https://help.github.com/articles/creating-an-access-token-for-command-line-use/
  [git-cache-password]: https://help.github.com/articles/caching-your-github-password-in-git/#platform-linux
