#!/usr/bin/env groovy

def call(Map params = [:]) {
    try {
        echo "checkpoint #1"

        def configFile = params.file ?: 'app-config.yaml'
        def config = readYaml(file: configFile)
        def configJson = groovy.json.JsonOutput.toJson(config)
        
        def repoUrl = scm.userRemoteConfigs[0]?.url ?: ''
        
        echo "checkpoint #2"
        
        sh """
            echo "=== Starting Python script ==="
            python3 ${env.WORKSPACE}/python/main.py \
                --config '${configJson}' \
                --branch '${env.BRANCH_NAME}' \
                --build-number '${env.BUILD_NUMBER}' \
                --change-id '${env.CHANGE_ID}' \
                --change-target '${env.CHANGE_TARGET}' \
                --workspace '${env.WORKSPACE}' \
                --repo-url '${repoUrl}'
            echo "=== Python script finished ==="
        """
        
        echo "✅ Deployment completed successfully!"
        
    } catch (Exception e) {
        notifyFailure()
        throw e
    }
}

def notifyFailure() {
    def authorEmail = sh(script: "cd ${env.WORKSPACE} && git log -1 --format='%ae'",, returnStdout: true).trim()
    def recipient = authorEmail ?: "emoreira@citeve.pt"
    
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
}