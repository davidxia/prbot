package com.davidxia.prbot.github;

import java.io.IOException;

/**
 * Gets the content of a URL and searches for a string in it.
 */
@FunctionalInterface
public interface UrlContentSearcher {

  boolean isStringInUrlContent(String str, String url) throws IOException;
}
