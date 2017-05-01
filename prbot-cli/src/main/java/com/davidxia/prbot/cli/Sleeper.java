package com.davidxia.prbot.cli;

import java.time.Duration;
import java.util.function.Function;

/**
 * Takes an arbitrary type, sleeps for a specified {@link Duration}, then returns it.
 */
@FunctionalInterface
public interface Sleeper {

  <T> Function<T, T> sleep(Duration duration);
}
