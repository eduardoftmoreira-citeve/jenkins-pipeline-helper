#!/usr/bin/env groovy

import com.citeve.devops.core.config.Configuration
import com.citeve.devops.core.model.Project
import com.citeve.devops.core.model.Component
import com.citeve.devops.core.ports.ContainerPort
import com.citeve.devops.core.ports.NetworkPort
import com.citeve.devops.core.ports.BackupPort
import com.citeve.devops.core.ports.ProxyPort
import com.citeve.devops.core.adapters.docker.DockerContainerAdapter
import com.citeve.devops.core.adapters.docker.DockerNetworkAdapter
import com.citeve.devops.core.adapters.nginx.NginxProxyAdapter
import com.citeve.devops.core.adapters.backup.MongoBackupAdapter

def loadConfiguration(Map params) {
    if (params.file) return readYaml(file: params.file)
    if (fileExists('app-config.yaml')) return readYaml(file: 'app-config.yaml')
    error "No configuration file found. Expected: app-config.yaml"
}

def buildProject(Map config) {
    def project = new Project(config.project)
    config.services.each { name, serviceConfig ->
        serviceConfig.name = name
        project.addComponent(new Component(serviceConfig))
    }
    return project
}

def getCleanBranch() {
    def raw = env.CHANGE_ID ? env.CHANGE_BRANCH : env.BRANCH_NAME
    return raw.split('/')[-1].replaceAll('/', '-').replaceAll('[^a-zA-Z0-9-]', '')
}

def isAuthorizedBranch(String branch) {
    return branch == 'main' || branch == 'master' || branch.startsWith('dev-poc')
}

def assignContainerNames(Project project) {
    project.components.each { component ->
        component.containerName = "${project.name}-${component.name}-${project.branch}"
        component.network = project.netName
    }
}

def allocatePort(Project project) {
    def apiComponent = project.findComponent('api')
    if (!apiComponent) return ''
    
    def containerName = "${project.name}-api-${project.branch}"
    def startPort = Configuration.PORTS.startPort
    def maxPortRange = Configuration.PORTS.maxPortRange
    
    def stickyPort = sh(
        script: "docker inspect -f '{{(index (index .HostConfig.PortBindings \"3000/tcp\") 0).HostPort}}' ${containerName} 2>/dev/null || echo ''",
        returnStdout: true
    ).trim()
    
    if (stickyPort) return stickyPort
    
    def newPort = sh(script: """
        PROBE=${startPort}
        while true; do
            DOCKER_USED=\$(docker ps -a --format '{{.Ports}}' | grep ":\$PROBE->" || true)
            SYSTEM_USED=\$(ss -tuln 2>/dev/null | grep ":\$PROBE " || netstat -tuln 2>/dev/null | grep ":\$PROBE " || true)
            if [ -z "\$DOCKER_USED" ] && [ -z "\$SYSTEM_USED" ]; then
                echo "\$PROBE"
                exit 0
            fi
            PROBE=\$((PROBE + 1))
            if [ "\$PROBE" -gt \$(( ${startPort} + ${maxPortRange} )) ]; then
                echo "FAILED"
                exit 1
            fi
        done
    """, returnStdout: true).trim()
    
    if (newPort == "FAILED") error "No available ports in range ${startPort} to ${startPort + maxPortRange}"
    return newPort
}

def waitForHealth(Component component, ContainerPort adapter) {
    timeout(component.getHealthTimeout()) {
        waitUntil {
            def healthy = adapter.isContainerHealthy(component)
            if (!healthy) sleep(component.getHealthInterval())
            return healthy
        }
    }
}

def detectBackupAdapter(Map config) {
    def databaseService = config.services.find { name, svc ->
        svc.type in ['mongo', 'mongodb']
    }
    
    return databaseService ? new MongoBackupAdapter() : null
}

def cleanupOrphaned(Project project) {
    withCredentials([usernamePassword(
        credentialsId: 'github-PAT',
        usernameVariable: 'GIT_USER',
        passwordVariable: 'GIT_PASS'
    )]) {
        sh """
            REPO_URL="https://\${GIT_PASS}@github.com/DEV-DTD-CITEVE/TEXPACT-WP2-PPS7.git"
            ACTIVE_BRANCHES=\$(git ls-remote --heads \$REPO_URL | awk -F'refs/heads/' '{print \$2}')
            API_PREFIX="${project.name}-api-"

            for container in \$(docker ps -a --format '{{.Names}}' | grep "\$API_PREFIX"); do
                BRANCH_NAME="\${container#\$API_PREFIX}"
                if ! echo "\$ACTIVE_BRANCHES" | grep -q "^\$BRANCH_NAME\$"; then
                    docker rm -f \$(docker stop "\$container") 2>/dev/null || true
                    REDIS_CONTAINER="${project.name}-redis-\${BRANCH_NAME}"
                    docker rm -f \$(docker stop "\$REDIS_CONTAINER") 2>/dev/null || true
                    rm -f ${Configuration.PATHS.nginxLocations}/${Configuration.TAGS.pilot}-${project.name}-\${BRANCH_NAME}.conf 2>/dev/null || true
                    docker exec ${Configuration.CONTAINERS.nginx} nginx -s reload 2>/dev/null || true
                fi
            done
        """
    }
}

def performCodeReview() {
    withCredentials([
        usernamePassword(
            credentialsId: 'github-PAT',
            usernameVariable: 'GIT_USER',
            passwordVariable: 'GIT_PASS'
        )
    ]) {
        sh "git fetch https://\${GIT_PASS}@github.com/DEV-DTD-CITEVE/TEXPACT-WP2-PPS7.git ${env.CHANGE_TARGET}"
    }
    
    def diff = sh(script: "git diff FETCH_HEAD...HEAD", returnStdout: true).trim()
    if (!diff) return
    
    def reviewResponse = sh(
        script: """
            curl -s http://192.168.54.202:11434/api/generate \\
                -d '{
                    "model": "qwen2.5-coder:7b",
                    "prompt": "You are a Senior Developer. Review this diff:\\n\\n${diff}",
                    "stream": false
                }'
        """,
        returnStdout: true
    )
    
    def reviewText = parseOllamaResponse(reviewResponse)
    
    withCredentials([
        usernamePassword(
            credentialsId: 'github-PAT',
            usernameVariable: 'GITHUB_USER',
            passwordVariable: 'GITHUB_TOKEN'
        )
    ]) {
        sh """
            curl -X POST \\
                -H "Authorization: Bearer \${GITHUB_TOKEN}" \\
                -H "Accept: application/vnd.github+json" \\
                ${Configuration.REPOS.github}issues/${env.CHANGE_ID}/comments \\
                -d '{"body": "${reviewText}"}'
        """
    }
}

def notifyFailure() {
    def authorEmail = sh(script: "git log -1 --format='%ae'", returnStdout: true).trim()
    def recipient = authorEmail ?: "devops@citeve.pt"
    
    emailext(
        to: recipient,
        subject: "${Configuration.LOGGING.fail} Pipeline Failed: ${env.JOB_NAME} [${env.CLEAN_BRANCH}]",
        body: """
            <h2>Build Failed</h2>
            <p><b>Project:</b> ${env.JOB_NAME}</p>
            <p><b>Branch:</b> ${env.CLEAN_BRANCH}</p>
            <p><b>Build Number:</b> ${env.BUILD_NUMBER}</p>
            <p><a href="${env.BUILD_URL}">View Console Output</a></p>
        """
    )
}

@NonCPS
def parseOllamaResponse(String jsonString) {
    def slurper = new groovy.json.JsonSlurper()
    return slurper.parseText(jsonString).response
}

def call(Map params = [:]) {
    def userConfig = loadConfiguration(params)
    def project = buildProject(userConfig)
    
    def containerAdapter = new DockerContainerAdapter()
    def networkAdapter = new DockerNetworkAdapter()
    def proxyAdapter = new NginxProxyAdapter()
    def backupAdapter = detectBackupAdapter(userConfig)
    
    pipeline {
        agent any
        
        triggers {
            cron('H 3 * * *')
        }
        
        environment {
            CLEAN_BRANCH = getCleanBranch()
            IS_PR_BUILD = (env.CHANGE_ID != null).toString()
            IS_SCHEDULED = (currentBuild.getBuildCauses().toString().contains('TimerTrigger')).toString()
        }
        
        stages {
            stage('Branch Validation') {
                steps {
                    script {
                        echo "${Configuration.LOGGING.info} Deploying ${project.name} [${project.environment}]"
                        
                        if (isAuthorizedBranch(env.CLEAN_BRANCH)) {
                            project.branch = env.CLEAN_BRANCH
                            project.port = allocatePort(project)
                            assignContainerNames(project)
                        } else {
                            error "${Configuration.LOGGING.fail} Branch '${env.CLEAN_BRANCH}' not authorized."
                        }
                    }
                }
            }
            
            stage('Cleanup') {
                when { expression { !env.IS_PR_BUILD.isTrue() } }
                steps {
                    script {
                        cleanupOrphaned(project)
                    }
                }
            }
            
            stage('Infrastructure') {
                when { expression { !env.IS_PR_BUILD.isTrue() } }
                steps {
                    script {
                        networkAdapter.createNetwork(project.netName)
                        networkAdapter.connectToNetwork(project.netName, Configuration.CONTAINERS.nginx)
                        
                        project.components.each { component ->
                            if (component.isInfrastructure()) {
                                containerAdapter.startContainer(component, project.netName)
                            }
                        }
                    }
                }
            }
            
            stage('Build') {
                when { expression { !env.IS_PR_BUILD.isTrue() } }
                steps {
                    script {
                        project.components.each { component ->
                            if (component.hasBuild()) {
                                containerAdapter.buildContainer(component)
                            }
                        }
                    }
                }
            }
            
            stage('Deploy') {
                when { expression { !env.IS_PR_BUILD.isTrue() } }
                steps {
                    script {
                        project.components.each { component ->
                            if (component.isDeployable()) {
                                containerAdapter.startContainer(component, project.netName)
                            }
                        }
                    }
                }
            }
            
            stage('Health Check') {
                when { expression { !env.IS_PR_BUILD.isTrue() } }
                steps {
                    script {
                        project.components.each { component ->
                            if (component.hasHealthCheck()) {
                                waitForHealth(component, containerAdapter)
                            }
                        }
                    }
                }
            }
            
            stage('Proxy Configuration') {
                when { expression { !env.IS_PR_BUILD.isTrue() } }
                steps {
                    script {
                        proxyAdapter.deployConfig(project, env.CLEAN_BRANCH)
                    }
                }
            }
            
            stage('Code Review') {
                when { expression { env.IS_PR_BUILD.isTrue() } }
                steps {
                    script {
                        performCodeReview()
                    }
                }
            }
            
            stage('Database Backup') {
                when { 
                    allOf {
                        expression { env.IS_SCHEDULED.isTrue() }
                        expression { env.BRANCH_NAME in ['main', 'master'] }
                        expression { backupAdapter != null } 
                    }
                }
                steps {
                    script {
                        backupAdapter.createBackup(project, Configuration.PATHS.backupDir)
                    }
                }
            }
        }
        
        post {
            failure {
                script {
                    notifyFailure()
                }
            }
            always {
                sh "docker image prune -f || true"
            }
        }
    }
}