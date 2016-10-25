package com.davidxia.prbot.cli;

import static com.davidxia.prbot.cli.CommitMessageParser.parseCommitMessage;

public class Main {

  public static void main(String[] args) throws Exception {
    final GitHubParser parser = new GitHubParser(args);
    final CommitMessage commitMessage = parseCommitMessage(parser.getCommitMessageFile());
    System.out.println("hi");
  }

}
