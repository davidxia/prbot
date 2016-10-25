package com.davidxia.prbot.cli;

import static net.sourceforge.argparse4j.impl.Arguments.fileType;
import static net.sourceforge.argparse4j.impl.Arguments.storeTrue;

import com.google.common.base.Throwables;

import java.io.File;
import java.nio.file.Path;
import java.text.DateFormat;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

import net.sourceforge.argparse4j.ArgumentParsers;
import net.sourceforge.argparse4j.inf.Argument;
import net.sourceforge.argparse4j.inf.ArgumentParser;
import net.sourceforge.argparse4j.inf.ArgumentParserException;
import net.sourceforge.argparse4j.inf.Namespace;

/**
 * Handles parsing commandline arguments related to GitHub.
 */
class GitHubParser {

  private static final String DEFAULT_DOMAIN = "github.com";
  private static final String DEFAULT_API_URL = "https://api.github.com/";
  private static final String DEFAULT_BASE_URI = "https://" + DEFAULT_DOMAIN + "/";
  //  private static final int RESULTS_PER_PAGE = 100;
  //  private static final String CLONE_DIR = "repos";
  //  DEFAULT_PUSHED_DATE = (date.today() + relativedelta(months=-1)).strftime('%Y-%m-%d')
  //  MAX_CMD_RETRIES = 10
  //  CLONE_RETRY_INTERVAL_SEC = 10
  //  REMINDER_INTERVAL_SECONDS = 7 * 24 * 60 * 60
  //  MAX_GITHUB_RESULTS_PAGE = 10  # Only the first 1000 search results are available

  private final Namespace options;

  private final Argument languageArg;
  private final Argument pushedDateArg;
  private final Argument deleteForksArg;
  private final Argument atMentionCommittersArg;
  private final Argument domainArg;
  private final Argument apiUrlArg;
  private final Argument githubTokenArg;
  private final Argument forkOwnerArg;
  private final Argument commitMessageFileArg;

  @SuppressWarnings("JavadocMethod")
  GitHubParser(final String... args) throws ArgumentParserException {

    final ArgumentParser parser = ArgumentParsers.newArgumentParser("prbot")
        .defaultHelp(true)
        .description("TBA");

    languageArg = parser.addArgument("--language")
        .type(String.class)
        .help("Searches repositories based on the language they're written in.");

    deleteForksArg = parser.addArgument("--delete-forks")
        .type(Boolean.class)
        .action(storeTrue())
        .help("Delete your existing repository forks. This makes sure your fork is synced with the "
              + "base repository and that your pull request doesn't have unintended commits.");

    atMentionCommittersArg = parser.addArgument("--at-mention-committers")
        .type(Boolean.class)
        .action(storeTrue())
        .help("@ mention recent committers.");

    domainArg = parser.addArgument("--domain")
        .type(String.class)
        .setDefault(DEFAULT_DOMAIN)
        .help("The GitHub or GitHub Enterprise domain. Defaults to " + DEFAULT_DOMAIN);

    apiUrlArg = parser.addArgument("--api-url")
        .type(String.class)
        .setDefault(DEFAULT_API_URL)
        .help("The GitHub or GitHub Enterprise domain. Defaults to " + DEFAULT_API_URL);

    githubTokenArg = parser.addArgument("--github-token")
        .type(String.class)
        .setDefault((String) null)
        .help("Optional cluster ID to ensure we are connected to the right cluster");

    forkOwnerArg = parser.addArgument("--fork-owner")
        .type(String.class)
        .required(true)
        .help("The owner of the git forks.");

    commitMessageFileArg = parser.addArgument("--commit-message-file")
        .type(String.class)
        .type(fileType().verifyExists().verifyCanRead())
        .help("File containing the Git commit message.");

    pushedDateArg = parser.addArgument("--pushed-date")
        .type(String.class)
        .help("Filters repositories based on date they were last updated. "
              + "Must be in the format YYYY-MM-DD.");

    try {
      this.options = parser.parseArgs(args);
    } catch (ArgumentParserException e) {
      parser.handleError(e);
      throw e;
    }
  }

  public String getDomain() {
    return options.getString(domainArg.getDest());
  }

  public Boolean getAtMentionCommitters() {
    return options.getBoolean(atMentionCommittersArg.getDest());
  }

  public Path getCommitMessageFile() {
    final File plugin = options.get(commitMessageFileArg.getDest());
    return plugin != null ? plugin.toPath() : null;
  }

  public String getApiUrl() {
    return options.getString(apiUrlArg.getDest());
  }

  public Date getPushedDate() {
    final DateFormat format = new SimpleDateFormat("YYYY-MM-DD", Locale.ENGLISH);
    try {
      return format.parse(options.getString(pushedDateArg.getDest()));
    } catch (ParseException e) {
      throw Throwables.propagate(e);
    }
  }

  public String getLanguage() {
    return options.getString(languageArg.getDest());
  }

  public String getGithubTokenArg() {
    return options.getString(githubTokenArg.getDest());
  }

  public String getForkOwner() {
    return options.getString(forkOwnerArg.getDest());
  }

  public Boolean getDeleteForks() {
    return options.getBoolean(deleteForksArg.getDest());
  }
}
