package com.davidxia.prbot.github;

import com.google.common.base.Throwables;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.ExecutionException;
import org.hamcrest.CustomTypeSafeMatcher;
import org.hamcrest.Description;
import org.hamcrest.Matcher;

class FutureMatchers {

  static Matcher<CompletionStage<?>> completedSuccessfully() {
    return new CustomTypeSafeMatcher<CompletionStage<?>>(
        "a CompletionStage that completed successfully") {
      @Override
      protected boolean matchesSafely(final CompletionStage<?> stage) {
        final CompletableFuture<?> f = stage.toCompletableFuture();
        return f.isDone() && !f.isCancelled() && !f.isCompletedExceptionally();
      }

      @Override
      public void describeMismatchSafely(final CompletionStage<?> stage,
                                         final Description mismatchDescription) {
        mismatchDescription.appendText("CompletionStage didn't complete successfully");
      }
    };
  }

  static <T extends Throwable> Matcher<CompletionStage<?>> completedExceptionallyWith(
      final T th) {

    return new CustomTypeSafeMatcher<CompletionStage<?>>(
        "a CompletionStage that completed exceptionally") {
      @Override
      protected boolean matchesSafely(final CompletionStage<?> stage) {
        final CompletableFuture<?> f = stage.toCompletableFuture();
        try {
          f.get();
        } catch (InterruptedException e) {
          return false;
        } catch (ExecutionException e) {
          final Throwable rootCause = Throwables.getRootCause(e);
          return th.getClass().isAssignableFrom(rootCause.getClass())
                 && th.getMessage().equals(rootCause.getMessage());
        }
        return false;
      }

      @Override
      public void describeMismatchSafely(final CompletionStage<?> stage,
                                         final Description mismatchDescription) {
        mismatchDescription.appendText("CompletionStage didn't complete successfully");
      }
    };
  }
}
