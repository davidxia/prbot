package com.davidxia.prbot.github;

import java.util.concurrent.CompletionStage;

// TODO (dxia) Rewrite this javadoc.
@FunctionalInterface
public interface RepoContentFinder {

  CompletionStage<Boolean> findContentInRepo(String query, String fullRepoName);

}
