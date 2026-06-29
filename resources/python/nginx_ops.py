import subprocess
import os
from config import Configuration
from utils import run_command

class NginxOps:
    
    def deploy_config(self, project, branch):
        """Deploy Nginx proxy configuration"""
        conf_name = f"{Configuration.get_pilot_tag()}-{project.name}-{branch}.conf"
        
        api_component = project.get_component('api')
        port = api_component.port if api_component else 3000
        container_name = f"{project.name}-api-{branch}"
        base_path = f"/{Configuration.get_pilot_tag()}/{project.name}/{branch}"
        
        config_content = f"""
            location ^~ {base_path}/ {{
                proxy_pass http://{container_name}:{port}/;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_set_header X-Forwarded-Prefix {base_path};
            }}
        """
        
        locations_dir = Configuration.get_nginx_locations()
        config_path = os.path.join(locations_dir, conf_name)
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        nginx_container = Configuration.get_nginx_container()
        
        test_result = subprocess.run(
            f"docker exec {nginx_container} nginx -t 2>/dev/null",
            shell=True
        )
        
        if test_result.returncode == 0:
            run_command(f"docker exec {nginx_container} nginx -s reload", check=True)
            print(f"{Configuration.get_log_success()} Proxy configured: {base_path}")
        else:
            if os.path.exists(config_path):
                os.remove(config_path)
            print(f"{Configuration.get_log_fail()} Invalid Nginx configuration")
            raise Exception("Invalid Nginx configuration")
    
    def remove_config(self, project, branch):
        """Remove Nginx proxy configuration"""
        conf_name = f"{Configuration.get_pilot_tag()}-{project.name}-{branch}.conf"
        locations_dir = Configuration.get_nginx_locations()
        config_path = os.path.join(locations_dir, conf_name)
        
        if os.path.exists(config_path):
            os.remove(config_path)
            print(f"{Configuration.get_log_info()} Removed config: {conf_name}")
    
    def reload(self):
        """Reload Nginx"""
        nginx_container = Configuration.get_nginx_container()
        run_command(f"docker exec {nginx_container} nginx -s reload 2>/dev/null || true", check=False)
        print(f"{Configuration.get_log_info()} Nginx reloaded")
    
    def get_nginx_container_status(self):
        """Get Nginx container status"""
        nginx_container = Configuration.get_nginx_container()
        result = subprocess.run(
            f"docker inspect -f '{{{{.State.Status}}}}' {nginx_container} 2>/dev/null || echo 'missing'",
            shell=True, capture_output=True, text=True
        )
        return result.stdout.strip()