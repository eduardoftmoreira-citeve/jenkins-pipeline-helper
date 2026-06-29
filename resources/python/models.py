#!/usr/bin/env python3
"""
Data models for the deployment pipeline.
"""

import os

from config import Configuration


class Project:
    """Represents a project with multiple components."""
    
    def __init__(self, config):
        self.name = config.get('project_name') or config.get('name')
        self.environment = config.get('environment', 'development')
        self.components = []
        self.branch = None
        self.port = None
        self.net_name = f"{self.name}-net" if self.name else None
    
    def add_component(self, component):
        """Add a component to the project."""
        self.components.append(component)
    
    def get_component(self, name):
        """Get a component by name."""
        for component in self.components:
            if component.name == name:
                return component
        return None
    
    def get_network_name(self):
        """Get the network name for the project."""
        return self.net_name
    
    def get_services_by_type(self, service_type):
        """Get all components of a specific type."""
        return [c for c in self.components if c.type == service_type]


class Component:
    """Represents a single component/service in the project."""
    
    def __init__(self, name, config):
        self.name = name
        self.type = config.get('type', '')
        self.image = config.get('image', 'default')
        self.port = config.get('port')
        self.build_command = config.get('build_command', '')
        self.health_check = config.get('health_check', {})
        self.env = config.get('env', {})
        self.depends_on = config.get('depends_on', [])
        self.data_volume = config.get('data_volume', False)
        self.volumes = config.get('volumes', [])
        self.source_dir = config.get('source_dir', '.')
        self.container_name = None
        self.network = None
        self.environment = config.get('environment', {})
        self.ports = config.get('ports', [])
        
    def get_health_path(self):
        return self.health_check.get('path', '/health')
    
    def get_health_status_code(self):
        return self.health_check.get('status_code', 200)
    
    def get_health_timeout(self):
        return self.health_check.get('timeout', 60)
    
    def has_health_check(self):
        return bool(self.health_check)
        
    def has_build_command(self):
        """Check if this component has a build command."""
        return bool(self.build_command and self.build_command.strip())
        
    def is_infrastructure(self):
        """Check if this is an infrastructure component."""
        return self.type in Configuration.get_infrastructure_types()
    
    def is_deployable(self):
        """Check if this component should be deployed."""
        return not self.is_infrastructure()
    
    def is_nodejs(self):
        """Check if this component is a Node.js project."""
        if 'npm' in self.build_command or 'node' in self.build_command:
            return True
        
        package_json = os.path.join(self.source_dir, 'package.json')
        if os.path.exists(package_json):
            return True
        
        if self.type and 'node' in self.type.lower():
            return True
        
        return False