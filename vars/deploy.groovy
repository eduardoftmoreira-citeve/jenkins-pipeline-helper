#!/usr/bin/env groovy

/** Deploy the application described by app-config.yaml. */
def call(Map options = [:]) {
    def debug = options.get('debug', false)
    def platformConfigOverride = options.get('platformConfig', '')
    def files = engineFiles()

    try {
        echo 'Deployment started'
        def engineDir = "${env.WORKSPACE}/.jenkins-deploy"
        copyEngine(engineDir, files)
        def platformConfig = platformConfigOverride ?: "${engineDir}/platform-config.yaml"
        withEnv([
            "DEPLOY_ENGINE=${engineDir}",
            "DEPLOY_BRANCH=${env.BRANCH_NAME ?: ''}",
            "DEPLOY_BUILD_NUMBER=${env.BUILD_NUMBER ?: ''}",
            "DEPLOY_WORKSPACE=${env.WORKSPACE}",
            "DEPLOY_PLATFORM_CONFIG=${platformConfig}",
            "DEPLOY_DEBUG=${debug ? '1' : '0'}"
        ]) {
            sh '''
                set -eu
                if [ "$DEPLOY_DEBUG" = "1" ]; then set -- --debug; else set --; fi
                python3 "$DEPLOY_ENGINE/deploy.py" "$@" deploy \
                  --branch "$DEPLOY_BRANCH" \
                  --build-number "$DEPLOY_BUILD_NUMBER" \
                  --workspace "$DEPLOY_WORKSPACE" \
                  --platform-config "$DEPLOY_PLATFORM_CONFIG"
            '''
        }
        echo 'Deployment completed'
    } catch (Exception exception) {
        echo "Deployment failed: ${exception.message}"
        throw exception
    }
}

private List engineFiles() {
    return [
        'deploy.py', 'requirements.txt',
        'deploylib/__init__.py', 'deploylib/util.py', 'deploylib/environment.py',
        'deploylib/model.py', 'deploylib/config.py', 'deploylib/command.py',
        'deploylib/docker.py', 'deploylib/state.py', 'deploylib/router.py',
        'deploylib/backup.py', 'deploylib/engine.py',
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
