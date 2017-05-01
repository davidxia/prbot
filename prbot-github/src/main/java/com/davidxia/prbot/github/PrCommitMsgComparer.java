package com.davidxia.prbot.github;

import com.davidxia.prbot.git.CommitMessage;
import org.kohsuke.github.GHPullRequest;

// TODO (david) write javadoc
/**
 * TBD.
 */
@FunctionalInterface
public interface PrCommitMsgComparer {

  boolean isSame(String user, CommitMessage commitMessage, GHPullRequest pullRequest);
}
