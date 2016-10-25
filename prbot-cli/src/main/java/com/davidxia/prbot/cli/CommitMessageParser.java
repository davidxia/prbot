package com.davidxia.prbot.cli;

import com.google.common.annotations.VisibleForTesting;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

class CommitMessageParser {

  private CommitMessageParser() {
  }

  static CommitMessage parseCommitMessage(final Path commitMessageFile) throws IOException {
    return parseCommitMessage(new String(Files.readAllBytes(commitMessageFile)));
  }

  @VisibleForTesting
  static CommitMessage parseCommitMessage(final String string) {
    return CommitMessage.create(string.substring(0, string.indexOf('\n')),
                                string.substring(string.indexOf('\n') + 1, string.length()).trim());
  }
}
