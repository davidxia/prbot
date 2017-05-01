package com.davidxia.prbot.github;

import java.util.concurrent.CompletionStage;
import org.kohsuke.github.GHContent;
import org.kohsuke.github.PagedSearchIterable;

/**
 * Searches a repo for a query string and returns results.
 */
@FunctionalInterface
public interface RepoSearcher {

  CompletionStage<PagedSearchIterable<GHContent>> searchRepo(final String fullRepoName,
                                                             final String query);

}
