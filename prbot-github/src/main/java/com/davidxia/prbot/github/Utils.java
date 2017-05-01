package com.davidxia.prbot.github;

import static java.lang.String.format;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.regex.Pattern;

public class Utils {

  /**
   * Return a master branch HTML URL.
   * Given an htmlUrl of https://github.com/foo/bar/blob/93d1bc/path/to/file.txt
   * return              https://github.com/raw/foo/bar/master/path/to/file.txt
   */
  public static String masterDownloadUrl(final String htmlUrl) throws MalformedURLException {
    final URL url = new URL(htmlUrl);

    final Pattern p = Pattern.compile("blob/[a-f0-9]+?/");
    final String s = p.matcher(htmlUrl).replaceFirst("master/");

    final String baseUrl =
        url.getPort() > 0
        ? format("^%s://%s:%d/", url.getProtocol(), url.getHost(), url.getPort())
        : format("^%s://%s/", url.getProtocol(), url.getHost());

    final Pattern p2 = Pattern.compile(baseUrl);
    return p2.matcher(s).replaceFirst(baseUrl.substring(1) + "raw/");
  }
}
