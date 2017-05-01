package com.davidxia.prbot.github;

import static com.davidxia.prbot.github.FutureMatchers.completedExceptionallyWith;
import static com.davidxia.prbot.github.FutureMatchers.completedSuccessfully;
import static org.hamcrest.CoreMatchers.is;
import static org.junit.Assert.*;
import static org.mockito.Matchers.anyString;
import static org.mockito.Mockito.when;

import com.davidxia.prbot.git.CommitMessage;
import com.google.common.util.concurrent.MoreExecutors;
import java.io.IOException;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.Executor;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.kohsuke.github.GHPullRequest;
import org.kohsuke.github.GHPullRequestQueryBuilder;
import org.kohsuke.github.GHRepository;
import org.kohsuke.github.GHUser;
import org.kohsuke.github.GitHub;
import org.kohsuke.github.PagedIterable;
import org.mockito.Mock;
import org.mockito.runners.MockitoJUnitRunner;

// TODO (david) All these tests are brittle. Requires knowledge of implementation of sut.
@RunWith(MockitoJUnitRunner.class)
public class PrClientTest {

  @Mock private GHPullRequest pr;
  @Mock private GHUser ghUser;
  @Mock private GHRepository repo;
  @Mock private GHPullRequestQueryBuilder prQueryBuilder;
  @Mock private GitHub gitHub;

  private PrClient sut;

  @Before
  public void setup() {
    final Executor executor = MoreExecutors.directExecutor();
    sut = PrClient.create(gitHub, executor);
  }

  @Test
  public void isSameNo() throws Exception {
    when(ghUser.getLogin()).thenReturn("user");
    when(pr.getUser()).thenReturn(ghUser);
    when(pr.getTitle()).thenReturn("best pr evar");
    when(pr.getBody()).thenReturn("some message");

    final boolean same = sut.isSame(
        "user", CommitMessage.create("best pr evar", "some message"), pr);
    assertThat(same, is(true));
  }

  @Test
  public void isSameYes() throws Exception {
    when(ghUser.getLogin()).thenReturn("user");
    when(pr.getUser()).thenReturn(ghUser);
    when(pr.getTitle()).thenReturn("best pr evar");
    when(pr.getBody()).thenReturn("another message");

    final boolean same = sut.isSame(
        "user", CommitMessage.create("best pr evar", "some message"), pr);
    assertThat(same, is(false));
  }

  @Test
  public void listPrsSuccess() throws Exception {
    when(repo.queryPullRequests()).thenReturn(prQueryBuilder);
    when(gitHub.getRepository(anyString())).thenReturn(repo);
    final CompletionStage<PagedIterable<GHPullRequest>> stage = sut.listPrs("my/repo");
    assertThat(stage, completedSuccessfully());
  }

  @Test
  public void listPrsFailure() throws Exception {
    final IOException ex = new IOException("not found");
    when(gitHub.getRepository(anyString())).thenThrow(ex);
    final CompletionStage<PagedIterable<GHPullRequest>> stage = sut.listPrs("my/repo");
    assertThat(stage, completedExceptionallyWith(ex));
  }

  @Test
  public void findMatchingPrSuccess() throws Exception {

  }

}