package com.davidxia.prbot.cli;

import com.google.common.base.Throwables;
import java.time.Duration;
import java.util.function.Function;

/**
 * An implementation of {@link Sleeper} that calls {@link Thread#sleep(long)}.
 */
public class ThreadSleeper implements Sleeper {

  private ThreadSleeper() {
    // Prevent instantiation
  }

  static ThreadSleeper create() {
    return new ThreadSleeper();
  }

  @Override
  public <T> Function<T, T> sleep(final Duration duration) {
    return f -> {
      try {
        Thread.sleep(duration.toMillis());
      } catch (InterruptedException e) {
        throw Throwables.propagate(e);
      }
      return f;
    };
  }
}

