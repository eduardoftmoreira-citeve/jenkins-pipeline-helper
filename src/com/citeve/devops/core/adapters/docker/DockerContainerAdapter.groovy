package com.citeve.devops.core.adapters.docker

import com.citeve.devops.core.model.Component
import com.citeve.devops.core.ports.ContainerPort

class DockerContainerAdapter implements ContainerPort {
    
    void startContainer(Component component, String network) {
        def containerName = component.containerName ?: "${component.name}-${component.type}"
        def envVars = buildEnvVars(component.env)
        def volumeMount = component.dataVolume ? "-v ${component.name}_data:/data" : ""
        def portMapping = component.port ? "-p ${component.port}:${component.port}" : ""
        
        sh """
            docker stop ${containerName} 2>/dev/null || true
            docker rm -f ${containerName} 2>/dev/null || true
            docker run -d \\
                --name ${containerName} \\
                --network ${network} \\
                --restart unless-stopped \\
                ${portMapping} \\
                ${volumeMount} \\
                ${envVars} \\
                ${component.image}
        """
    }
    
    void stopContainer(Component component) {
        def containerName = component.containerName ?: "${component.name}-${component.type}"
        sh "docker stop ${containerName} 2>/dev/null || true"
        sh "docker rm -f ${containerName} 2>/dev/null || true"
    }
    
    void restartContainer(Component component) {
        def containerName = component.containerName ?: "${component.name}-${component.type}"
        sh "docker restart ${containerName} 2>/dev/null || true"
    }
    
    void buildContainer(Component component) {
        if (component.buildCommand) {
            sh component.buildCommand
            sh "docker build -t ${component.image} ."
        }
    }
    
    boolean isContainerHealthy(Component component) {
        def containerName = component.containerName ?: "${component.name}-${component.type}"
        def endpoint = component.getHealthEndpoint()
        
        def status = sh(
            script: "curl -s -o /dev/null -w '%{http_code}' http://${containerName}:${component.port}${endpoint} || echo '000'",
            returnStdout: true
        ).trim()
        
        return status == '200'
    }
    
    String getContainerStatus(Component component) {
        def containerName = component.containerName ?: "${component.name}-${component.type}"
        return sh(
            script: "docker inspect -f '{{.State.Status}}' ${containerName} 2>/dev/null || echo 'missing'",
            returnStdout: true
        ).trim()
    }
    
    private String buildEnvVars(Map env) {
        return env.collect { key, value -> "-e ${key}=${value}" }.join(' ')
    }
}