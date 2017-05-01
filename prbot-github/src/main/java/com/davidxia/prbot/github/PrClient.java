package com.davidxia.prbot.github;

import static java.util.concurrent.CompletableFuture.supplyAsync;

import com.davidxia.prbot.git.CommitMessage;
import com.google.common.base.Throwables;
import java.io.IOException;
import java.util.Optional;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.Executor;
import org.kohsuke.github.GHPullRequest;
import org.kohsuke.github.GHRepository;
import org.kohsuke.github.GitHub;
import org.kohsuke.github.PagedIterable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class PrClient implements PrLister, MatchingPrFinder, PrCommitMsgComparer {

  private static final Logger LOG = LoggerFactory.getLogger(PrClient.class);

  private final GitHub gitHub;
  private final Executor executor;

  private PrClient(final GitHub gitHub, final Executor executor) {
    this.gitHub = gitHub;
    this.executor = executor;
  }

  public static PrClient create(final GitHub gitHub, final Executor executor) {
    return new PrClient(gitHub, executor);
  }

  /**
   * Return true if the PR has the same user, head, and body as the username of the account being
   * used, the {@link CommitMessage#subject()}, and the {@link CommitMessage#body()}, respectively.
   * Otherwise, false.
   */
  @Override
  public boolean isSame(final String user,
                        final CommitMessage commitMessage,
                        final GHPullRequest pullRequest) {
    return user.equals(pullRequest.getUser().getLogin())
           && commitMessage.subject().equals(pullRequest.getTitle())
           && commitMessage.body().equals(pullRequest.getBody());
  }

  @Override
  public CompletionStage<PagedIterable<GHPullRequest>> listPrs(final String fullRepoName) {
    return supplyAsync(() -> {
      final GHRepository repo;
      try {
        repo = gitHub.getRepository(fullRepoName);
      } catch (IOException e) {
        throw Throwables.propagate(e);
      }
      return repo.queryPullRequests().list();
    }, executor);
  }

  @Override
  public CompletionStage<Optional<GHPullRequest>> findMatchingPr(
      final String user,
      final String fullRepoName,
      final CommitMessage commitMessage) {

    final CompletionStage<PagedIterable<GHPullRequest>> prIterableStage = listPrs(fullRepoName);
    return prIterableStage.thenApply(prIterable -> {
      for (final GHPullRequest pr : prIterable) {
        if (isSame(user, commitMessage, pr)) {
          LOG.info("Found a matching open PR: {}", pr);
          return Optional.of(pr);
        }
      }
      return Optional.empty();
    });
  }
}
