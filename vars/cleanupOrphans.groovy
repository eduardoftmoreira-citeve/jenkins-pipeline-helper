#!/usr/bin/env groovy

/** Run from a scheduled Jenkins job to remove orphaned feature and bugfix deployments. */
def call(Map options = [:]) {
    def platformConfigOverride = options.get('platformConfig', '')
    def repoUrl = scm.userRemoteConfigs[0]?.url ?: ''
    if (!repoUrl) {
        error('Cannot determine the repository URL for orphan cleanup.')
    }
    def files = engineFiles()
    def engineDir = "${env.WORKSPACE}/.jenkins-deploy"
    copyEngine(engineDir, files)
    def platformConfig = platformConfigOverride ?: "${engineDir}/platform-config.yaml"
    withEnv([
        "DEPLOY_ENGINE=${engineDir}",
        "DEPLOY_WORKSPACE=${env.WORKSPACE}",
        "DEPLOY_PLATFORM_CONFIG=${platformConfig}",
        "DEPLOY_REPO_URL=${repoUrl}"
    ]) {
        sh '''
            set -eu
            python3 "$DEPLOY_ENGINE/deploy.py" cleanup \
              --workspace "$DEPLOY_WORKSPACE" \
              --platform-config "$DEPLOY_PLATFORM_CONFIG" \
              --repo-url "$DEPLOY_REPO_URL"
        '''
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
