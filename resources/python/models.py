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
        
        for name, infra_config in config.get('infrastructure', {}).items():
            component = Component(name, infra_config)
            component.is_infrastructure = True
            self.components.append(component)
        
        for name, service_config in config.get('services', {}).items():
            component = Component(name, service_config)
            component.is_infrastructure = False
            self.components.append(component)
    
    def add_component(self, component):
        self.components.append(component)
    
    def get_component(self, name):
        for component in self.components:
            if component.name == name:
                return component
        return None
    
    def get_network_name(self):
        return self.net_name
    
    def get_infrastructure(self):
        return [c for c in self.components if c.is_infrastructure]
    
    def get_applications(self):
        return [c for c in self.components if not c.is_infrastructure]
    
    def get_services_by_type(self, service_type):
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
        self.host_port = None
        self.is_infrastructure = False
    
    def get_health_path(self):
        return self.health_check.get('path', '/health')
    
    def get_health_status_code(self):
        return self.health_check.get('status_code', 200)
    
    def get_health_timeout(self):
        return self.health_check.get('timeout', 60)
    
    def has_health_check(self):
        return bool(self.health_check)
    
    def has_build_command(self):
        return bool(self.build_command and self.build_command.strip())
    
    def is_deployable(self):
        return not self.is_infrastructure
    
    def is_nodejs(self):
        if 'npm' in self.build_command or 'node' in self.build_command:
            return True
        
        package_json = os.path.join(self.source_dir, 'package.json')
        if os.path.exists(package_json):
            return True
        
        if self.type and 'node' in self.type.lower():
            return True
        
        return False