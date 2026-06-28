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

def call(Map params = [:]) {
    // No more Configuration.instance - access static fields directly
    
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
                        // ✅ Use Configuration.LOGGING directly
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
            
            // ... rest of stages
        }
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

// ... rest of helper functions