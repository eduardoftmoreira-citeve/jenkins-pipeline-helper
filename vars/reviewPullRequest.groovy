#!/usr/bin/env groovy

/**
 * Review the branch's open same-repository pull request, if one exists.
 *
 * This runs in an ordinary Jenkins multibranch *branch* build. It asks GitHub
 * whether BRANCH_NAME has exactly one open pull request, then delegates the
 * diff and comment work to the Python reviewer. It never creates a separate
 * Jenkins PR build and never deploys infrastructure.
 *
 * Examples:
 *   reviewPullRequest()
 *   reviewPullRequest(dryRun: true)
 */
def call(Map options = [:]) {
    def branch = (options.get('branch', env.BRANCH_NAME ?: '') ?: '').toString().trim()
    if (!branch) {
        echo 'Skipping Ollama review: BRANCH_NAME is unavailable in this build.'
        return
    }

    def repoUrl = (options.get('repoUrl', '') ?: '').toString().trim()
    if (!repoUrl) {
        repoUrl = scm.userRemoteConfigs[0]?.url ?: ''
    }
    if (!repoUrl) {
        error('Cannot determine the repository URL for branch pull-request review.')
    }

    def platformConfigOverride = (options.get('platformConfig', '') ?: '').toString().trim()
    def dryRun = options.get('dryRun', false) as boolean
    def engineDir = "${env.WORKSPACE}/.jenkins-deploy"
    copyEngine(engineDir, engineFiles())
    def platformConfig = platformConfigOverride ?: "${engineDir}/platform-config.yaml"

    def invokeReview = {
        withEnv([
            "DEPLOY_ENGINE=${engineDir}",
            "DEPLOY_WORKSPACE=${env.WORKSPACE}",
            "DEPLOY_PLATFORM_CONFIG=${platformConfig}",
            "DEPLOY_REPO_URL=${repoUrl}",
            "DEPLOY_BRANCH=${branch}",
            "DEPLOY_DRY_RUN=${dryRun ? '1' : '0'}"
        ]) {
            sh '''
                set -eu
                set -- review \
                  --workspace "$DEPLOY_WORKSPACE" \
                  --platform-config "$DEPLOY_PLATFORM_CONFIG" \
                  --repo-url "$DEPLOY_REPO_URL" \
                  --branch "$DEPLOY_BRANCH"
                if [ "$DEPLOY_DRY_RUN" = "1" ]; then
                  set -- "$@" --dry-run
                fi
                python3 "$DEPLOY_ENGINE/deploy.py" "$@"
            '''
        }
    }

    // github-PAT is also the existing checkout credential. It is a Jenkins
    // Username/Password credential: its password is the classic GitHub PAT.
    // Every branch build needs it, including dry-run, to ask GitHub whether an
    // open pull request exists for the source branch.
    withCredentials([
        usernamePassword(
            credentialsId: 'github-PAT',
            usernameVariable: 'GITHUB_USERNAME',
            passwordVariable: 'GITHUB_TOKEN'
        )
    ]) {
        invokeReview()
    }
}

private List engineFiles() {
    return [
        'deploy.py', 'requirements.txt',
        'deploylib/__init__.py', 'deploylib/util.py', 'deploylib/environment.py',
        'deploylib/model.py', 'deploylib/config.py', 'deploylib/command.py',
        'deploylib/docker.py', 'deploylib/state.py', 'deploylib/router.py',
        'deploylib/backup.py', 'deploylib/review.py', 'deploylib/engine.py',
        'deploylib/providers/__init__.py', 'deploylib/providers/base.py',
        'deploylib/providers/mongo.py', 'deploylib/providers/redis.py',
        'deploylib/providers/node.py'
    ]
}

private void copyEngine(String engineDir, List files) {
    sh "rm -rf '${engineDir}' && mkdir -p '${engineDir}/deploylib/providers'"
    files.each { file ->
        writeFile file: "${engineDir}/${file}", text: libraryResource("python/${file}")
    }
    writeFile file: "${engineDir}/platform-config.yaml", text: libraryResource("platform-config.yaml")
}
