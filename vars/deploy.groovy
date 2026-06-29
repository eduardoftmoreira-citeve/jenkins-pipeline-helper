#!/usr/bin/env groovy

def call(Map config = [:]) {
    def debug = config.get('debug',false)
    def enableNotifications = config.get('enableNotifications',true)

    try {
        echo "📣 Deploy started"

        def debugFlag = debug ? '--debug' : ''
        
        def repoUrl = scm.userRemoteConfigs[0]?.url ?: ''
        def configFile = params.file ?: 'app-config.yaml'
        
        // Copy Python files from library resources to workspace -- needed to include project files in python files' scope
        def pythonFiles = [
            'main.py',
            'config.py',
            'models.py',
            'utils.py',
            'docker_ops.py',
            'nginx_ops.py',
            'cleanup_ops.py',
            'github_ops.py',
            'ollama_ops.py',
            'health_ops.py',
            '__init__.py'
        ]
        
        sh "mkdir -p ${env.WORKSPACE}/python"
        
        pythonFiles.each { file ->
            def content = libraryResource("python/${file}")
            writeFile file: "${env.WORKSPACE}/python/${file}", text: content
        }
        
        echo "📣 Python files copied to workspace"
        
        sh """
            cd ${env.WORKSPACE}
            python3 ${env.WORKSPACE}/python/main.py \
                --branch '${env.BRANCH_NAME}' \
                --build-number '${env.BUILD_NUMBER}' \
                --change-id '${env.CHANGE_ID}' \
                --change-target '${env.CHANGE_TARGET}' \
                --workspace '${env.WORKSPACE}' \
                --repo-url '${repoUrl}' \
                --config-file '${configFile}' \
                ${debugFlag}
        """
        
        echo "✅ Deployment completed successfully!"
        
    } catch (Exception e) {
        echo "❌ Deployment failed!"
        echo "Error: ${e.getMessage()}"

        if (enableNotifications) {
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
}