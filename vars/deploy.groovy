#!/usr/bin/env groovy

def call(Map params = [:]) {
    try {
        def repoUrl = scm.userRemoteConfigs[0]?.url ?: ''
        def configFile = params.file ?: 'app-config.yaml'
        
        sh """
            cd ${env.WORKSPACE}
            python3 ${env.WORKSPACE}/python/main.py \
                --branch '${env.BRANCH_NAME}' \
                --build-number '${env.BUILD_NUMBER}' \
                --change-id '${env.CHANGE_ID}' \
                --change-target '${env.CHANGE_TARGET}' \
                --workspace '${env.WORKSPACE}' \
                --repo-url '${repoUrl}' \
                --config-file '${configFile}'
        """
        
        echo "✅ Deployment completed successfully!"
        
    } catch (Exception e) {
        def authorEmail = sh(
            script: "git log -1 --format='%ae'",
            returnStdout: true
        ).trim()
        
        def recipient = authorEmail ?: "devops@citeve.pt"
        
        emailext(
            to: recipient,
            subject: "❌ Pipeline Failed: ${env.JOB_NAME} [${env.CLEAN_BRANCH}]",
            body: """
                <h2>Build Failed</h2>
                <p><b>Project:</b> ${env.JOB_NAME}</p>
                <p><b>Branch:</b> ${env.CLEAN_BRANCH}</p>
                <p><b>Build Number:</b> ${env.BUILD_NUMBER}</p>
                <p><a href="${env.BUILD_URL}">View Console Output</a></p>
            """
        )
        
        throw e
    }
}