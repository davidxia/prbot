package com.davidxia.prbot.github;

import java.util.concurrent.CompletionStage;
import org.kohsuke.github.GHPullRequest;
import org.kohsuke.github.PagedIterable;

/**
 * List open PRs for a repo.
 */
@FunctionalInterface
public interface PrLister {

  CompletionStage<PagedIterable<GHPullRequest>> listPrs(String fullRepoName);

}
