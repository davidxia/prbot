package com.davidxia.prbot.cli;

import static com.davidxia.prbot.git.CommitMessageParser.parseCommitMessage;

import com.davidxia.prbot.git.CommitMessage;
import com.davidxia.prbot.git.DefaultRepoCloner;
import com.davidxia.prbot.git.RepoCloner;
import com.davidxia.prbot.github.GitHubRepoContentFinder;
import com.davidxia.prbot.github.PrClient;
import com.davidxia.prbot.github.RepoClient;
import com.davidxia.prbot.github.RepoContentFinder;
import com.google.common.base.Throwables;
import com.google.common.util.concurrent.ThreadFactoryBuilder;
import java.io.File;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import okhttp3.OkHttpClient;
import org.kohsuke.github.GHRepository;
import org.kohsuke.github.GitHub;
import org.kohsuke.github.GitHubBuilder;
import org.kohsuke.github.PagedIterator;
import org.kohsuke.github.PagedSearchIterable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Main {

  private static final Logger LOG = LoggerFactory.getLogger(Main.class);
  private static final Duration FORK_WAIT_INTERVAL = Duration.ofSeconds(10);
  private static final File CLONE_DIR = new File("repos");

  public static void main(String[] args) throws Exception {
    final GitHubParser parser = new GitHubParser(args);
    // GitHub.connectToEnterpriseAnonymously()
    final GitHub gitHub = new GitHubBuilder()
        .withEndpoint(parser.getApiEndpoint())
        .build();
    final ScheduledExecutorService gitHubExecutor = createGithubExecutor();
    final CommitMessage commitMessage = parseCommitMessage(parser.getCommitMessageFile());

    final RepoClient repoClient = RepoClient.create(gitHub, gitHubExecutor);
    final RepoCloner repoCloner = DefaultRepoCloner.create();
    final PrClient prClient = PrClient.create(gitHub, gitHubExecutor);

    final RepoContentFinder repoContentFinder =
        GitHubRepoContentFinder.create(repoClient, new OkHttpClient());


    final Sleeper sleeper = ThreadSleeper.create();

    final String query = "helios";

    final PagedSearchIterable<GHRepository> repos =
        repoClient.getRecentRepos(parser.getPushedDate()).toCompletableFuture().get();
    LOG.info("Recently pushed repos: {}", repos.getTotalCount());
    final PagedIterator<GHRepository> repoIterator = repos.iterator();

    Utils.cleanDir(Paths.get("repos"));

    int idx = 0;
    while (repoIterator.hasNext() && idx < 5) {
      final GHRepository repo = repoIterator.next();
      LOG.info("REPO {}", repo.getFullName());

      if (prClient.findMatchingPr(parser.getForkOwner(), repo.getFullName(), commitMessage)
          .toCompletableFuture()
          .get()
          .isPresent()) {
        continue;
      }

      if (!repoContentFinder.findContentInRepo(query, repo.getFullName())
          .toCompletableFuture()
          .get()) {
        continue;
      }

      // Fork the repo
      final String forkedRepoName = parser.getForkOwner() + "/" + repo.getName();
      final CompletionStage<Void> deleteRepoStage;
      if (parser.getDeleteForks()) {
        LOG.info("Deleting your fork {} if it exists.", forkedRepoName);
        deleteRepoStage = repoClient.deleteRepo(forkedRepoName);
      } else {
        deleteRepoStage = CompletableFuture.completedFuture(null);
      }

      final CompletionStage<GHRepository> clonedRepoStage = deleteRepoStage
          .thenCompose((vd) -> repoClient.forkRepo(repo.getFullName()))
          // Sleep to give GitHub enough time to fork.
          .thenApply(sleeper.sleep(FORK_WAIT_INTERVAL))
          .thenApply(forkedRepo -> {
            final String cloneUri = forkedRepo.gitHttpTransportUrl();
            try {
              repoCloner.cloneRepo(cloneUri, CLONE_DIR).toCompletableFuture().get();
              return forkedRepo;
            } catch (InterruptedException | ExecutionException e) {
              LOG.error("Failed to clone repo {} into dir {}.", cloneUri, CLONE_DIR);
              throw Throwables.propagate(e);
            }
          });

      clonedRepoStage
          .thenApply()

      idx++;
    }

  }

  private static ScheduledExecutorService createGithubExecutor() {
    final ThreadFactory threadFactory = new ThreadFactoryBuilder()
        .setDaemon(true)
        .setNameFormat("github-executor-%d")
        .build();
    return Executors.newScheduledThreadPool(16, threadFactory);
  }
}
