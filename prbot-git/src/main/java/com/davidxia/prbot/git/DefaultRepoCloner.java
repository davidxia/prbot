package com.davidxia.prbot.git;

import static java.util.concurrent.CompletableFuture.supplyAsync;

import com.google.common.base.Throwables;
import java.io.File;
import java.util.concurrent.CompletionStage;
import org.eclipse.jgit.api.CloneCommand;
import org.eclipse.jgit.api.Git;
import org.eclipse.jgit.api.errors.GitAPIException;

public class DefaultRepoCloner implements RepoCloner {

  private DefaultRepoCloner() {
    // Prevent instantion
  }

  public static DefaultRepoCloner create() {
    return new DefaultRepoCloner();
  }

  @Override
  public CompletionStage<Void> cloneRepo(final String cloneUri, final File cloneDir) {
    return supplyAsync(() -> {
      final CloneCommand command = Git.cloneRepository()
          .setDirectory(cloneDir)
          .setURI(cloneUri);

      Git git = null;
      try {
        git = command.call();
        return null;
      } catch (GitAPIException e) {
        throw Throwables.propagate(e);
      } finally {
        if (git != null) {
          git.close();
        }
      }
    });
  }
}
