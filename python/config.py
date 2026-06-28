import os

class Configuration:
    _BRANCH_ALIASES = {
        'development': ['develop', 'dev', 'development'],
        'staging': ['staging', 'stage'],
        'production': ['main', 'master', 'prod', 'production']
    }

    _AUTHORIZED_BRANCHES = {
        'static': ['main', 'master', 'develop', 'staging'],
        'prefixes': ['feature/', 'hotfix/', 'bugfix/']
    }
    
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
        'expected_status': 200,
    }
    
    _HEALTH_CHECKERS = {
        'api': 'http_health_check',
        'frontend': 'http_health_check',
        'mongo': 'mongo_health_check',
        'redis': 'redis_health_check'
    }

    _RESCUE_CONFIG = {
        'max_retries': 3,
        'wait_time': 10,  # seconds
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

    _OLLAMA = {
        'url': 'http://192.168.54.202:11434/api/generate',
        'model': 'qwen2.5-coder:7b',
        'timeout': 120
    }
    
    @staticmethod
    def get_ollama_url():
        return Configuration._OLLAMA['url']
    
    @staticmethod
    def get_ollama_model():
        return Configuration._OLLAMA['model']
    
    @staticmethod
    def get_ollama_timeout():
        return Configuration._OLLAMA['timeout']
    
    @staticmethod
    def get_branch_aliases():
        return Configuration._BRANCH_ALIASES

    @staticmethod
    def get_authorized_branches():
        return Configuration._AUTHORIZED_BRANCHES

    @staticmethod
    def get_static_branches():
        return Configuration._AUTHORIZED_BRANCHES['static']

    @staticmethod
    def get_prefix_branches():
        return Configuration._AUTHORIZED_BRANCHES['prefixes']

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
        return Configuration._TAGS['pilot']

    @staticmethod
    def get_health_checker_type(component_type):
        return Configuration._HEALTH_CHECKERS.get(component_type, 'default')

    @staticmethod
    def get_health_checker_keys():
        """Get all registered health checker keys"""
        return Configuration._HEALTH_CHECKERS.keys()

    #retrieve jenkins env variables
    @staticmethod
    def get_env(key, default=None):
        return os.environ.get(key, default)

    @staticmethod
    def get_max_retries():
        return Configuration._RESCUE_CONFIG['max_retries']
    
    @staticmethod
    def get_wait_time():
        return Configuration._RESCUE_CONFIG['wait_time']