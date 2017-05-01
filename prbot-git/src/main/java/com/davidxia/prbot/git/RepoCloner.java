package com.davidxia.prbot.git;

import java.io.File;
import java.util.concurrent.CompletionStage;

/**
 * Clones repos.
 */
public interface RepoCloner {

  CompletionStage<Void> cloneRepo(String cloneUri, File cloneDir);

}
