#!/usr/bin/env groovy

/**
 * Generate an Ollama review for a Jenkins multibranch pull-request build.
 *
 * The reviewer is intentionally separate from deploy(): it reads the Git diff,
 * calls the platform-configured Ollama endpoint, and creates or updates one
 * marked comment on the GitHub pull request. It never deploys infrastructure.
 *
 * Examples:
 *   reviewPullRequest(githubTokenCredentialId: 'github-PAT')
 *   reviewPullRequest(dryRun: true)
 */
def call(Map options = [:]) {
    def prNumber = (env.CHANGE_ID ?: '').toString().trim()
    def baseBranch = (options.get('baseBranch', env.CHANGE_TARGET ?: '') ?: '').toString().trim()
    if (!prNumber || !baseBranch) {
        echo 'Skipping Ollama review: this build is not a pull-request build or has no CHANGE_TARGET.'
        return
    }

    def allowForks = options.get('allowForks', false) as boolean
    if ((env.CHANGE_FORK ?: '').toString().trim() && !allowForks) {
        echo 'Skipping Ollama review for a fork pull request. Set allowForks: true only after reviewing Jenkins trust and credential exposure.'
        return
    }

    def repoUrl = (options.get('repoUrl', '') ?: '').toString().trim()
    if (!repoUrl) {
        repoUrl = scm.userRemoteConfigs[0]?.url ?: ''
    }
    if (!repoUrl) {
        error('Cannot determine the repository URL for pull-request review.')
    }

    def platformConfigOverride = (options.get('platformConfig', '') ?: '').toString().trim()


    def dryRun = options.get('dryRun', false) as boolean
    def engineDir = "${env.WORKSPACE}/.jenkins-deploy"
    copyEngine(engineDir, engineFiles())
    def platformConfig = platformConfigOverride ?: "${engineDir}/platform-config.yaml"
    def dryRun = options.get('dryRun', false) as boolean

    if (dryRun) {
        invokeReview()
    } else {
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
    def invokeReview = {
        withEnv([
            "DEPLOY_ENGINE=${engineDir}",
            "DEPLOY_WORKSPACE=${env.WORKSPACE}",
            "DEPLOY_PLATFORM_CONFIG=${platformConfig}",
            "DEPLOY_REPO_URL=${repoUrl}",
            "DEPLOY_PR_NUMBER=${prNumber}",
            "DEPLOY_BASE_BRANCH=${baseBranch}",
            "DEPLOY_DRY_RUN=${dryRun ? '1' : '0'}"
        ]) {
            sh '''
                set -eu
                set -- review \
                  --workspace "$DEPLOY_WORKSPACE" \
                  --platform-config "$DEPLOY_PLATFORM_CONFIG" \
                  --repo-url "$DEPLOY_REPO_URL" \
                  --pr-number "$DEPLOY_PR_NUMBER" \
                  --base-branch "$DEPLOY_BASE_BRANCH"
                if [ "$DEPLOY_DRY_RUN" = "1" ]; then
                  set -- "$@" --dry-run
                fi
                python3 "$DEPLOY_ENGINE/deploy.py" "$@"
            '''
        }
    }

    if (tokenCredentialId) {
        withCredentials([string(credentialsId: tokenCredentialId, variable: 'GITHUB_TOKEN')]) {
            invokeReview()
        }
    } else {
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
