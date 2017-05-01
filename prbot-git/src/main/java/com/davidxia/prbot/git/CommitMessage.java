package com.davidxia.prbot.git;

import com.google.auto.value.AutoValue;

@AutoValue
public abstract class CommitMessage {

  public static CommitMessage create(final String subject, final String body) {
    return new AutoValue_CommitMessage(subject, body);
  }

  public abstract String subject();

  public abstract String body();
}
