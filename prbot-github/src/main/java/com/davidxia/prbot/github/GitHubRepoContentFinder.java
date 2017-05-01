package com.davidxia.prbot.github;

import java.io.IOException;
import java.net.MalformedURLException;
import java.util.concurrent.CompletionStage;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import org.kohsuke.github.GHContent;
import org.kohsuke.github.PagedSearchIterable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * More abstraction on top of {@link RepoSearcher} that checks the master branch of the repo
 * has the query string. Main purpose of checking master is that the search API may yield
 * outdated results. Prevent program from doing extra work of cloning only to find query isn't
 * present.
 */
public class GitHubRepoContentFinder implements RepoContentFinder, UrlContentSearcher {

  private static final Logger LOG = LoggerFactory.getLogger(GitHubRepoContentFinder.class);

  private final RepoSearcher repoSearcher;
  private final OkHttpClient httpClient;

  private GitHubRepoContentFinder(final RepoSearcher repoSearcher,
                                  final OkHttpClient httpClient) {
    this.repoSearcher = repoSearcher;
    this.httpClient = httpClient;
  }

  public static GitHubRepoContentFinder create(final RepoSearcher repoSearcher,
                                               final OkHttpClient httpClient) {
    return new GitHubRepoContentFinder(repoSearcher, httpClient);
  }

  @Override
  public CompletionStage<Boolean> findContentInRepo(final String query, final String fullRepoName) {
    final CompletionStage<PagedSearchIterable<GHContent>> contentIterableStage =
        repoSearcher.searchRepo(fullRepoName, query);
    return contentIterableStage.thenApply(contentIterable -> {
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
  public boolean isStringInUrlContent(final String str, final String url) throws IOException {
    final Request request = new Request.Builder()
        .url(url)
        .build();

    final Response response = httpClient.newCall(request).execute();

    if (response.code() != 200) {
      return false;
    }

    final String content = response.body().string();
    return content.contains(str);
  }
}
