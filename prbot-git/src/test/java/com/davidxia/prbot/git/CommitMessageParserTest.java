package com.davidxia.prbot.git;

import static com.davidxia.prbot.git.CommitMessageParser.parseCommitMessage;
import static com.google.common.base.Charsets.UTF_8;
import static com.google.common.io.Resources.getResource;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.MatcherAssert.assertThat;

import com.google.common.io.Resources;
import org.junit.Test;

public class CommitMessageParserTest {

  @Test
  public void testParseCommitMessage() throws Exception {
    final CommitMessage msg = parseCommitMessage(
        Resources.toString(getResource("commit_message"), UTF_8));
    assertThat(msg.subject(), equalTo("commit message subject"));
    assertThat(msg.body(), equalTo("commit message body\nbody line 2"));
  }
}