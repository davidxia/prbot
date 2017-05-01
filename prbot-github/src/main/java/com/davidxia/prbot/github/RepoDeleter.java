package com.davidxia.prbot.github;

import java.util.concurrent.CompletionStage;

/**
 * Deletes repos.
 */
public interface RepoDeleter {

  CompletionStage<Void> deleteRepo(final String fullRepoName);
}
