package com.davidxia.prbot.github;

import java.util.concurrent.CompletionStage;
import org.kohsuke.github.GHRepository;

/**
 * Forks repos.
 */
public interface RepoForker {

  CompletionStage<GHRepository> forkRepo(String fullRepoName);
}
