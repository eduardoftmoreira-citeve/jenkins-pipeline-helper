import os

class Configuration:
    _PATHS = {
        'backup_dir': '/home/emoreira/cicd-poc/backups',
        'nginx_locations': '/home/users/cgomes/nginx/locations'
    }
    
    _CONTAINERS = {
        'nginx': 'nginx-proxy',
        'jenkins': 'jenkins-server'
    }
    
    _PORT_ALLOCATION = {
        'search_start': 10000,
        'search_range': 1000
    }
    
    _HEALTH_CHECK = {
        'timeout': 60,
        'interval': 5,
        'expected_status': 200
    }
    
    _LOGGING = {
        'info': '📣 INFO:',
        'warning': '⚠️ WARNING:',
        'fail': '❌ FAILED:',
        'debug': '🪲 DEBUG:',
        'success': '✅ SUCCESS:'
    }
    
    _TAGS = {
        'pilot': 'piloto-cicd'
    }
    
    @staticmethod
    def get_backup_dir():
        return Configuration._PATHS['backup_dir']
    
    @staticmethod
    def get_nginx_locations():
        return Configuration._PATHS['nginx_locations']
    
    @staticmethod
    def get_nginx_container():
        return Configuration._CONTAINERS['nginx']
    
    @staticmethod
    def get_jenkins_container():
        return Configuration._CONTAINERS['jenkins']
    
    @staticmethod
    def get_port_search_start():
        return Configuration._PORT_ALLOCATION['search_start']
    
    @staticmethod
    def get_port_search_range():
        return Configuration._PORT_ALLOCATION['search_range']
    
    @staticmethod
    def get_health_timeout():
        return Configuration._HEALTH_CHECK['timeout']
    
    @staticmethod
    def get_health_interval():
        return Configuration._HEALTH_CHECK['interval']
    
    @staticmethod
    def get_health_expected_status():
        return Configuration._HEALTH_CHECK['expected_status']
    
    @staticmethod
    def get_log_info():
        return Configuration._LOGGING['info']
    
    @staticmethod
    def get_log_warning():
        return Configuration._LOGGING['warning']
    
    @staticmethod
    def get_log_fail():
        return Configuration._LOGGING['fail']
    
    @staticmethod
    def get_log_debug():
        return Configuration._LOGGING['debug']
    
    @staticmethod
    def get_log_success():
        return Configuration._LOGGING['success']
    
    @staticmethod
    def get_pilot_tag():
        return Configuration._TAG
        
    #retrieve jenkins env variables
    @staticmethod
    def get_env(key, default=None):
        return os.environ.get(key, default)