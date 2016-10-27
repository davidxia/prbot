package com.davidxia.prbot.github;

import static java.util.concurrent.CompletableFuture.supplyAsync;

import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableMap;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.Executor;

import org.eclipse.egit.github.core.SearchRepository;
import org.eclipse.egit.github.core.client.GitHubClient;
import org.eclipse.egit.github.core.service.RepositoryService;

class DefaultRepoSearcher implements RepoSearcher {

  private Executor executor;

  private DefaultRepoSearcher(final Executor executor) {
    this.executor = executor;
  }

  static DefaultRepoSearcher create(final Executor executor) {
    return new DefaultRepoSearcher(executor);
  }

  public CompletionStage<List<SearchRepository>> searchRepos() {
    GitHubClient client = new GitHubClient("github.mycompany.com");
    final RepositoryService repositoryService = new RepositoryService(client);

    return supplyAsync(() -> {
      try {
        return repositoryService.searchRepositories(
            ImmutableMap.of("sort", "updated", "order", "desc"));
      } catch (IOException e) {
        throw Throwables.propagate(e);
      }
    }, executor);
  }
}
