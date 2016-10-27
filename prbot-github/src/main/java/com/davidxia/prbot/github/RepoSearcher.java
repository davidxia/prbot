package com.davidxia.prbot.github;

import java.util.List;
import java.util.concurrent.CompletionStage;

import org.eclipse.egit.github.core.SearchRepository;

public interface RepoSearcher {

  CompletionStage<List<SearchRepository>> searchRepos();

}
