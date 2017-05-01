package com.davidxia.prbot.github;

import static java.util.concurrent.CompletableFuture.supplyAsync;

import com.google.common.base.Throwables;
import java.io.IOException;
import java.net.MalformedURLException;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.Executor;
import org.kohsuke.github.GHContent;
import org.kohsuke.github.GHRepository;
import org.kohsuke.github.GHRepositorySearchBuilder;
import org.kohsuke.github.GitHub;
import org.kohsuke.github.PagedSearchIterable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class RepoClient implements RecentRepoGetter, RepoSearcher, RepoForker, RepoDeleter {

  private static final Logger LOG = LoggerFactory.getLogger(RepoClient.class);

  private final GitHub gitHub;
  private final Executor executor;
  private final UrlContentSearcher urlContentSearcher;

  private RepoClient(final GitHub gitHub, final Executor executor) {
    this.gitHub = gitHub;
    this.executor = executor;
  }

  public static RepoClient create(final GitHub gitHub, final Executor executor) {
    return new RepoClient(gitHub, executor);
  }

  @Override
  public CompletionStage<Void> deleteRepo(final String fullRepoName) {
    return supplyAsync(() -> {
      try {
        gitHub.getRepository(fullRepoName).delete();
        LOG.info("Successfully deleted your repo {}.", fullRepoName);
        return null;
      } catch (IOException e) {
        LOG.warn("Couldn't delete your repo {}: {}", fullRepoName, e);
        throw Throwables.propagate(e);
      }
    }, executor);
  }

  @Override
  public CompletionStage<GHRepository> forkRepo(final String fullRepoName) {
    return supplyAsync(() -> {
      try {
        return gitHub.getRepository(fullRepoName).fork();
      } catch (IOException e) {
        throw Throwables.propagate(e);
      }
    }, executor);
  }

  @Override
  public CompletionStage<PagedSearchIterable<GHContent>> searchRepo(final String fullRepoName,
                                                                    final String query) {
    return supplyAsync(() -> {
      final PagedSearchIterable<GHContent> file = gitHub.searchContent()
          .in("file")
          .repo(fullRepoName)
          .q(query)
          .list();
    }, executor);
    contentIterableStage.thenApply(contentIterable -> {
      for (final GHContent content : contentIterable) {
        LOG.info("HTML URL " + content.getHtmlUrl());
        final String masterDownloadUrl;
        try {
          masterDownloadUrl = Utils.masterDownloadUrl(content.getHtmlUrl());
        } catch (MalformedURLException e) {
          throw new IllegalStateException(e);
        }

        LOG.info("MASTER DOWNLOAD URL " + masterDownloadUrl);

        try {
          if (isStringInUrlContent(query, masterDownloadUrl)) {
            return true;
          }
        } catch (IOException e) {
          LOG.warn("Could not get request content for URL {}. Skipping.", masterDownloadUrl);
        }
      }

      return false;
    });
  }

  @Override
  public CompletionStage<PagedSearchIterable<GHRepository>> getRecentRepos(
      final String pushedDate) {
    return supplyAsync(() -> gitHub.searchRepositories()
        .pushed(">" + pushedDate)
        .sort(GHRepositorySearchBuilder.Sort.UPDATED)
        .list(), executor);
  }
}
