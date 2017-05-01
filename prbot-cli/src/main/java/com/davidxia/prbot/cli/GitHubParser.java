package com.davidxia.prbot.cli;

import static net.sourceforge.argparse4j.impl.Arguments.fileType;
import static net.sourceforge.argparse4j.impl.Arguments.storeTrue;

import java.io.File;
import java.nio.file.Path;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
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
  private static final String DEFAULT_API_ENDPOINT = "https://api.github.com";
  private static final String DEFAULT_PUSHED_DATE;
  private static final DateArgumentType DATE_ARGUMENT_TYPE = DateArgumentType.create("yyyy-MM-dd");

  static {
    final Calendar cal = Calendar.getInstance();
    cal.add(Calendar.MONTH, -1);
    final SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd");
    DEFAULT_PUSHED_DATE = dateFormat.format(cal.getTime());
  }
  //  private static final int RESULTS_PER_PAGE = 100;
  //  private static final String CLONE_DIR = "repos";
  //  MAX_CMD_RETRIES = 10
  //  CLONE_RETRY_INTERVAL_SEC = 10
  //  REMINDER_INTERVAL_SECONDS = 7 * 24 * 60 * 60
  //  MAX_GITHUB_RESULTS_PAGE = 10  # Only the first 1000 search results are available

  private final Namespace options;

  private final Argument domainArg;
  private final Argument apiEndpointArg;
  private final Argument forkOwnerArg;
  private final Argument githubTokenArg;
  private final Argument languageArg;
  private final Argument pushedDateArg;
  private final Argument deleteForksArg;
  private final Argument atMentionCommittersArg;
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

    apiEndpointArg = parser.addArgument("--api-endpoint")
        .type(String.class)
        .setDefault(DEFAULT_API_ENDPOINT)
        .help("The GitHub or GitHub Enterprise domain. Defaults to " + DEFAULT_API_ENDPOINT);

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
        .required(true)
        .help("File containing the Git commit message.");

    pushedDateArg = parser.addArgument("--pushed-date")
        .type(DATE_ARGUMENT_TYPE)
        .setDefault(DEFAULT_PUSHED_DATE)
        .help("Filters repositories based on date they were last updated. "
              + "Must be in the format yyyy-MM-dd. Defaults to one month ago.");

    try {
      this.options = parser.parseArgs(args);
    } catch (ArgumentParserException e) {
      parser.handleError(e);
      throw e;
    }
  }

  String getDomain() {
    return options.getString(domainArg.getDest());
  }

  Boolean getAtMentionCommitters() {
    return options.getBoolean(atMentionCommittersArg.getDest());
  }

  Path getCommitMessageFile() {
    final File plugin = options.get(commitMessageFileArg.getDest());
    return plugin != null ? plugin.toPath() : null;
  }

  String getApiEndpoint() {
    return options.getString(apiEndpointArg.getDest());
  }

  String getPushedDate() {
    final Date date = options.get(pushedDateArg.getDest());
    return DATE_ARGUMENT_TYPE.getDateFormat().format(date);
  }

  String getLanguage() {
    return options.getString(languageArg.getDest());
  }

  String getGithubTokenArg() {
    return options.getString(githubTokenArg.getDest());
  }

  String getForkOwner() {
    return options.getString(forkOwnerArg.getDest());
  }

  Boolean getDeleteForks() {
    return options.getBoolean(deleteForksArg.getDest());
  }
}
