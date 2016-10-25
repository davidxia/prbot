package com.davidxia.prbot.cli;

import com.google.auto.value.AutoValue;

@AutoValue
abstract class CommitMessage {

  static CommitMessage create(final String commitMessageSubject, final String commitMessageBody) {
    return new AutoValue_CommitMessage(commitMessageSubject, commitMessageBody);
  }

  abstract String commitMessageSubject();

  abstract String commitMessageBody();
}
