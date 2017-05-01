package com.davidxia.prbot.cli;

import com.google.common.base.Throwables;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import org.apache.commons.io.FileUtils;

class Utils {

  /**
   * Delete a directory and create a new one.
   */
  static void cleanDir(final Path path) {
    final File dir = path.toFile();

    try {
      FileUtils.deleteDirectory(dir);
    } catch (IOException e) {
      throw Throwables.propagate(e);
    }

    if (!dir.mkdir()) {
      throw new IllegalStateException("Couldn't create directory " + path.toString());
    }
  }

}
