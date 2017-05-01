package com.davidxia.prbot.github;

import java.util.concurrent.CompletionStage;
import org.kohsuke.github.GHRepository;
import org.kohsuke.github.PagedSearchIterable;

@FunctionalInterface
public interface RecentRepoGetter {

  /**
   * Get repos that have recently been pushed.
   * @param pushedDate A String for filtering repos based on last pushed date.
   */
  CompletionStage<PagedSearchIterable<GHRepository>> getRecentRepos(final String pushedDate);

}
