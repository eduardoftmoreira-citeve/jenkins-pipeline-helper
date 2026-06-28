#represents the different services/containers of a project
class Component:
    def __init__(self, name, config):
        self.name = name
        self.type = config.get('type')
        self.image = config.get('image', 'default')
        self.port = config.get('port')
        self.build_command = config.get('build_command')
        self.health_check = config.get('health_check', {})
        self.env = config.get('env', {})
        self.depends_on = config.get('depends_on', [])
        self.data_volume = config.get('data_volume', False)
        self.volumes = config.get('volumes', [])
        self.container_name = None
        self.network = None

    def get_health_path(self):
        return self.health_check.get('path', '/health')
    
    def get_health_status_code(self):
        return self.health_check.get('status_code', 200)
    
    def get_health_timeout(self):
        return self.health_check.get('timeout', 60)
    
    def has_build_command(self):
        return bool(self.build_command)
    
    def is_infrastructure(self):
        return self.type in ['mongo', 'postgres', 'mysql', 'redis']


#represents the project itself, containing all project components and the project environment
class Project:
    def __init__(self, config):
        self.name = config.get('project_name')
        self.environment = config.get('environment', 'development')
        self.components = []

    def add_component(self, component):
        self.components.append(component)
    
    def get_component(self, name):
        for component in self.components:
            if component.name == name:
                return component
        return None
    
    def get_services_by_type(self, service_type):
        return [c for c in self.components if c.type == service_type]