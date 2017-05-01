package com.davidxia.prbot.github;

import com.davidxia.prbot.git.CommitMessage;
import java.util.Optional;
import java.util.concurrent.CompletionStage;
import org.kohsuke.github.GHPullRequest;

/**
 * Finds matching open pull requests.
 */
public interface MatchingPrFinder {

  CompletionStage<Optional<GHPullRequest>> findMatchingPr(String user,
                                                          String fullRepoName,
                                                          CommitMessage commitMessage);

}
