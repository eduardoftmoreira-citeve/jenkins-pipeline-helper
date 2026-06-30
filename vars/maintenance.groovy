#!/usr/bin/env groovy

/**
 * Run a provider-neutral maintenance operation for the application in this job.
 *
 * Supported operations today: backup and restore. Providers decide whether they
 * support an operation; Jenkins never names a specific infrastructure type.
 *
 * Examples:
 *   maintenance(operation: 'backup', branch: 'main')
 *   maintenance(
 *     operation: 'restore',
 *     branch: 'main',
 *     archive: '/home/users/cicd/backups/mongo/pps7-api/prod/mongo/20260630T021500Z.archive.gz',
 *     confirmEnvironment: 'prod'
 *   )
 */
def call(Map options = [:]) {
    def operation = options.get('operation', '').toString().trim()
    if (!(operation in ['backup', 'restore'])) {
        error("maintenance requires operation: 'backup' or 'restore'.")
    }

    def branch = options.get('branch', env.BRANCH_NAME ?: '').toString().trim()
    if (!branch) {
        error('maintenance requires a branch, for example maintenance(operation: "backup", branch: "main").')
    }

    def archive = options.get('archive', '').toString().trim()
    def confirmation = options.get('confirmEnvironment', '').toString().trim()
    if (operation == 'restore' && (!archive || !confirmation)) {
        error('maintenance restore requires archive and confirmEnvironment.')
    }

    def platformConfigOverride = options.get('platformConfig', '').toString().trim()
    def engineDir = "${env.WORKSPACE}/.jenkins-deploy"
    copyEngine(engineDir, engineFiles())
    def platformConfig = platformConfigOverride ?: "${engineDir}/platform-config.yaml"

    withEnv([
        "DEPLOY_ENGINE=${engineDir}",
        "DEPLOY_WORKSPACE=${env.WORKSPACE}",
        "DEPLOY_PLATFORM_CONFIG=${platformConfig}",
        "DEPLOY_OPERATION=${operation}",
        "DEPLOY_BRANCH=${branch}",
        "DEPLOY_ARCHIVE=${archive}",
        "DEPLOY_CONFIRM_ENVIRONMENT=${confirmation}"
    ]) {
        sh '''
            set -eu
            set -- maintenance \
              --operation "$DEPLOY_OPERATION" \
              --branch "$DEPLOY_BRANCH" \
              --workspace "$DEPLOY_WORKSPACE" \
              --platform-config "$DEPLOY_PLATFORM_CONFIG"
            if [ "$DEPLOY_OPERATION" = "restore" ]; then
              set -- "$@" --archive "$DEPLOY_ARCHIVE" --confirm-environment "$DEPLOY_CONFIRM_ENVIRONMENT"
            fi
            python3 "$DEPLOY_ENGINE/deploy.py" "$@"
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
