pipeline {
    agent any
    
    stages {
        stage('Generate Jobs') {
            steps {
                git(
                    url: 'https://github.com/eduardoftmoreira-citeve/jenkins-pipeline-helper.git',
                    branch: 'main',
                    credentialsId: 'github-PAT'
                )
                jobDsl targets: 'dsl/jobs.groovy'
            }
        }
    }
}