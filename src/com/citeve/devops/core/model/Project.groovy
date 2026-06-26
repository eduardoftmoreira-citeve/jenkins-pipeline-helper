package com.citeve.devops.core.model

class Project {
    String name
    String type
    String netName
    String environment
    String branch
    String port
    Map config
    List<Component> components
    
    Project(Map config) {
        this.name = config.name
        this.type = config.type ?: 'fullstack'
        this.netName = config.netName ?: "${name}-net"
        this.environment = config.environment ?: 'development'
        this.config = config
        this.components = []
    }
    
    void addComponent(Component component) {
        components << component
    }
    
    Component findComponent(String name) {
        components.find { it.name == name }
    }
    
    List<Component> getDatabaseComponents() {
        components.findAll { it.isDatabase() }
    }
    
    List<Component> getApiComponents() {
        components.findAll { it.type == 'api' }
    }
}