package com.davidxia.prbot.github;

import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.MatcherAssert.assertThat;

import org.junit.Test;

public class UtilsTest {

  @Test
  public void testMasterDownloadUrlNoPort() throws Exception {
    final String htmlUrl = "https://github.com/foo/bar/blob/93d1bc/path/to/file.txt";
    final String expectedUrl = "https://github.com/raw/foo/bar/master/path/to/file.txt";
    assertThat(Utils.masterDownloadUrl(htmlUrl), equalTo(expectedUrl));

    final String htmlUrl2 = "https://ghe.mydomain.net/spotify/helios/blob/ea5e46dc0//pom.xml";
    final String expectedUrl2 = "https://ghe.mydomain.net/raw/spotify/helios/master//pom.xml";
    assertThat(Utils.masterDownloadUrl(htmlUrl2), equalTo(expectedUrl2));
  }

  @Test
  public void testMasterDownloadUrlWithPort() throws Exception {
    final String htmlUrl = "https://github.com:5801/foo/bar/blob/93d1bc/path/to/file.txt";
    final String expectedUrl = "https://github.com:5801/raw/foo/bar/master/path/to/file.txt";
    assertThat(Utils.masterDownloadUrl(htmlUrl), equalTo(expectedUrl));

    final String htmlUrl2 = "https://ghe.mydomain.net:5801/spotify/helios/blob/ea5e46dc0//pom.xml";
    final String expectedUrl2 = "https://ghe.mydomain.net:5801/raw/spotify/helios/master//pom.xml";
    assertThat(Utils.masterDownloadUrl(htmlUrl2), equalTo(expectedUrl2));
  }

}