package com.citeve.devops.core.adapters.docker

import com.citeve.devops.core.ports.NetworkPort

class DockerNetworkAdapter implements NetworkPort {
    
    void createNetwork(String name) {
        sh "docker network create ${name} 2>/dev/null || true"
    }
    
    void deleteNetwork(String name) {
        sh "docker network rm ${name} 2>/dev/null || true"
    }
    
    boolean networkExists(String name) {
        def result = sh(
            script: "docker network inspect ${name} 2>/dev/null && echo 'exists' || echo 'missing'",
            returnStdout: true
        ).trim()
        return result == 'exists'
    }
    
    void connectToNetwork(String network, String container) {
        sh "docker network connect ${network} ${container} 2>/dev/null || true"
    }
}