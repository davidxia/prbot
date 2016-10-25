package com.davidxia.prbot.cli;

import static com.davidxia.prbot.cli.CommitMessageParser.parseCommitMessage;
import static com.google.common.base.Charsets.UTF_8;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.MatcherAssert.assertThat;

import com.google.common.io.Resources;

import org.junit.Test;

public class CommitMessageParserTest {

  @Test
  public void testParseCommitMessage() throws Exception {
    final CommitMessage msg =
        parseCommitMessage(Resources.toString(Resources.getResource("commit_message"), UTF_8));
    assertThat(msg.commitMessageSubject(), equalTo("commit message subject"));
    assertThat(msg.commitMessageBody(), equalTo("commit message body\nbody line 2"));
  }
}