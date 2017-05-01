package com.davidxia.prbot.github;

import static com.davidxia.prbot.github.FutureMatchers.completedExceptionallyWith;
import static com.davidxia.prbot.github.FutureMatchers.completedSuccessfully;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.mockito.Matchers.anyString;
import static org.mockito.Mockito.when;

import com.google.common.util.concurrent.MoreExecutors;
import java.io.IOException;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.Executor;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.kohsuke.github.GHRepository;
import org.kohsuke.github.GitHub;
import org.mockito.Mock;
import org.mockito.runners.MockitoJUnitRunner;

@RunWith(MockitoJUnitRunner.class)
public class RepoClientTest {

  @Mock private GHRepository repo;
  @Mock private GitHub gitHub;

  private RepoClient sut;

  @Before
  public void setup() {
    final Executor executor = MoreExecutors.directExecutor();
    sut = RepoClient.create(gitHub, executor);
  }

  @Test
  public void deleteRepoSuccess() throws Exception {
    when(gitHub.getRepository(anyString())).thenReturn(repo);
    final CompletionStage<Void> stage = sut.deleteRepo("my/repo");
    assertThat(stage, completedSuccessfully());
  }

  @Test
  public void deleteRepoFailure() throws Exception {
    final IOException ex = new IOException("not found");
    when(gitHub.getRepository(anyString())).thenThrow(ex);
    final CompletionStage<Void> stage = sut.deleteRepo("my/repo");
    assertThat(stage, completedExceptionallyWith(ex));
  }

  @Test
  public void forkRepoSuccess() throws Exception {
    when(gitHub.getRepository(anyString())).thenReturn(repo);
    final CompletionStage<GHRepository> stage = sut.forkRepo("my/repo");
    assertThat(stage, completedSuccessfully());
  }

  @Test
  public void forkRepoFailure() throws Exception {
    final IOException ex = new IOException("not found");
    when(gitHub.getRepository(anyString())).thenThrow(ex);
    final CompletionStage<GHRepository> stage = sut.forkRepo("my/repo");
    assertThat(stage, completedExceptionallyWith(ex));
  }
}