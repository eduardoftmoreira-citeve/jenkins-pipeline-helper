package com.citeve.devops.core.model

class Component {
    String name
    String type
    String image
    int port
    String buildCommand
    Map env
    Map healthCheck
    int replicas
    boolean dataVolume
    String containerName
    String network
    
    Component(Map config) {
        this.name = config.name
        this.type = config.type ?: 'api'
        this.image = config.image ?: "${type}:latest"
        this.port = config.port ?: getDefaultPort()
        this.buildCommand = config.buildCommand
        this.env = config.env ?: [:]
        this.healthCheck = config.healthCheck ?: [path: '/health', timeout: 60, interval: 5]
        this.replicas = config.replicas ?: 1
        this.dataVolume = config.dataVolume ?: false
    }
    
    private int getDefaultPort() {
        switch(type) {
            case 'api': return 3000
            case 'mongo': case 'mongodb': return 27017
            case 'redis': return 6379
            case 'postgres': return 5432
            case 'mysql': return 3306
            case 'frontend': return 80
            case 'elasticsearch': return 9200
            default: return 8080
        }
    }
    
    boolean isDatabase() {
        return type in ['mongo', 'mongodb', 'postgres', 'mysql']
    }
    
    boolean isInfrastructure() {
        return type in ['mongo', 'mongodb', 'redis', 'postgres', 'mysql']
    }
    
    boolean hasBuild() {
        return buildCommand != null && !buildCommand.isEmpty()
    }
    
    boolean isDeployable() {
        return type != 'mongo' && type != 'mongodb' && type != 'redis'
    }
    
    boolean hasHealthCheck() {
        return healthCheck != null && healthCheck.path != null
    }
    
    int getHealthTimeout() {
        return healthCheck.timeout ?: 60
    }
    
    int getHealthInterval() {
        return healthCheck.interval ?: 5
    }
    
    String getHealthEndpoint() {
        return healthCheck.path ?: '/health'
    }
}