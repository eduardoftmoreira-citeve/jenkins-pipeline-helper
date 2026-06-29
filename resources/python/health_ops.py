import subprocess

class HealthOps:
    
    @staticmethod
    def http_health_check(component):
        """HTTP health check for APIs and frontends"""
        container_name = component.container_name or f"{component.name}-{component.type}"
        endpoint = component.get_health_path()
        status_code = component.get_health_status_code()
        
        try:
            result = subprocess.run(
                f"curl -s -o /dev/null -w '%{{http_code}}' http://{container_name}:{component.port}{endpoint} || echo '000'",
                shell=True, capture_output=True, text=True
            )
            return result.stdout.strip() == str(status_code)
        except:
            return False
    
    @staticmethod
    def mongo_health_check(component):
        """MongoDB health check"""
        container_name = component.container_name or f"{component.name}-{component.type}"
        result = subprocess.run(
            f"docker exec {container_name} mongosh --eval \"db.adminCommand('ping')\" 2>/dev/null || echo 'failed'",
            shell=True, capture_output=True, text=True
        )
        return 'failed' not in result.stdout
    
    @staticmethod
    def redis_health_check(component):
        """Redis health check"""
        container_name = component.container_name or f"{component.name}-{component.type}"
        result = subprocess.run(
            f"docker exec {container_name} redis-cli PING 2>/dev/null || echo 'failed'",
            shell=True, capture_output=True, text=True
        )
        return result.stdout.strip() == 'PONG'
    
    @staticmethod
    def default_health_check(component):
        """Default health check (assume healthy)"""
        return True