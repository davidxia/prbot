package com.davidxia.prbot.cli;

import static java.util.concurrent.CompletableFuture.completedFuture;
import static org.hamcrest.CoreMatchers.is;
import static org.junit.Assert.assertThat;

import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import org.junit.Test;

public class ThreadSleeperTest {

  @Test
  public void sleep() throws Exception {
    final ThreadSleeper sut = ThreadSleeper.create();
    final CompletionStage<Void> stage = completedFuture(null);
    final CompletionStage<Void> awakeStage = stage.thenApplyAsync(sut.sleep(Duration.ofSeconds(1)));
    final CompletableFuture<Void> awakeFuture = awakeStage.toCompletableFuture();

    assertThat(awakeFuture.isDone(), is(false));
    Thread.sleep(Duration.ofSeconds(2).toMillis());
    assertThat(awakeFuture.isDone(), is(true));
  }

}