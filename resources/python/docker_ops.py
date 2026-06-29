import subprocess
from config import Configuration
from utils import build_env_vars, run_command

class DockerOps:
    
    def create_network(self, name):
        """Create Docker network if it doesn't exist"""
        run_command(f"docker network create {name} 2>/dev/null || true", check=False)
    
    def connect_to_network(self, network, container):
        """Connect container to network"""
        run_command(f"docker network connect {network} {container} 2>/dev/null || true", check=False)
    
    def start_container(self, component, network):
        """Start a container from a component"""
        container_name = component.container_name or f"{component.name}-{component.type}"

        if 'shared' in container_name and self.container_exists(container_name):
            print(f"{Configuration.get_log_info()} Shared container {container_name} already exists, skipping start")
            return container_name

        env_vars = build_env_vars(component.env)
        port_mapping = f"-p {component.port}:{component.port}" if component.port else ""
        volume_mount = f"-v {component.name}_data:/data" if component.data_volume else ""
        
        self.stop_container(container_name)
        
        cmd = f"""
            docker run -d \\
                --name {container_name} \\
                --network {network} \\
                --restart unless-stopped \\
                {port_mapping} \\
                {volume_mount} \\
                {env_vars} \\
                {component.image}
        """
        run_command(cmd, check=True)
        return container_name
    
    def rescue_container(self, component):
        """Attempt to rescue an unhealthy container"""
        max_retries = Configuration.get_max_retries()
        wait_time = Configuration.get_wait_time()
        
        container_name = component.container_name or f"{component.name}-{component.type}"
        current_status = self.get_container_status(container_name)
        
        print(f"{Configuration.get_log_info()} Attempting to rescue: {container_name} (status: {current_status})")
        
        for attempt in range(1, max_retries + 1):
            print(f"   Attempt {attempt}/{max_retries}...")
            
            run_command(f"docker restart {container_name} 2>/dev/null || true", check=False)
            time.sleep(wait_time)
            
            if self.is_container_healthy(component):
                print(f"{Configuration.get_log_success()} Container {container_name} successfully rescued on attempt {attempt}!")
                return True
            
            if attempt == max_retries - 1:
                print(f"{Configuration.get_log_warning()} Restart didn't work, trying stop + start...")
                self.stop_container(container_name)
                self.start_container(component, component.network)
                time.sleep(wait_time)
                
                if self.is_container_healthy(component):
                    print(f"{Configuration.get_log_success()} Container {container_name} rescued via stop + start!")
                    return True
    
        print(f"{Configuration.get_log_fail()} Failed to rescue {container_name} after {max_retries} attempts")
        return False
    
    def check_and_rescue_containers(self, project, branch):
        """Check all containers for a specific branch and rescue if needed"""
        rescued = []
        
        for component in project.components:
            if not component.has_health_check():
                continue
            
            container_name = f"{project.name}-{component.name}-{branch}"
            component.container_name = container_name
            
            if not self.container_exists(container_name):
                print(f"{Configuration.get_log_warning()} Container {container_name} is missing, starting it...")
                self.start_container(component, component.network)
                rescued.append(container_name)
            
            elif not self.is_container_healthy(component):
                print(f"{Configuration.get_log_warning()} Container {container_name} is unhealthy, attempting rescue...")
                if self.rescue_container(component):
                    rescued.append(container_name)
        
        return rescued

    def stop_container(self, container_name):
        """Stop and remove a container by name"""
        run_command(f"docker stop {container_name} 2>/dev/null || true", check=False)
        run_command(f"docker rm -f {container_name} 2>/dev/null || true", check=False)
    
    def remove_container(self, container_name):
        """Remove a container by name (force)"""
        run_command(f"docker rm -f {container_name} 2>/dev/null || true", check=False)
    
    def container_exists(self, container_name):
        """Check if a container exists"""
        result = subprocess.run(
            f"docker ps -a --format '{{{{.Names}}}}' | grep -x '{container_name}' || true",
            shell=True, capture_output=True, text=True
        )
        return bool(result.stdout.strip())
    
    def get_container_status(self, container_name):
        """Get container status (running, stopped, etc.)"""
        result = subprocess.run(
            f"docker inspect -f '{{{{.State.Status}}}}' {container_name} 2>/dev/null || echo 'missing'",
            shell=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    
    def get_all_containers(self, prefix):
        """Get all containers with a given prefix"""
        result = subprocess.run(
            f"docker ps -a --format '{{{{.Names}}}}' | grep '^{prefix}' || true",
            shell=True, capture_output=True, text=True
        )
        return [c for c in result.stdout.strip().split('\n') if c]
    
    def build_container(self, component):
        """Build a container from source."""
        if component.has_build_command():
            print(f"{Configuration.get_log_info()} Running build commands...")
            
            # Split multi-line commands by \n
            commands = [c.strip() for c in component.build_command.split('\n') if c.strip()]
            
            for cmd in commands:
                print(f"{Configuration.get_log_info()} Running: {cmd}")
                try:
                    # ✅ Use shell=True and capture more output
                    import subprocess
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"{Configuration.get_log_fail()} Command failed with exit code: {result.returncode}")
                        print(f"STDOUT: {result.stdout}")
                        print(f"STDERR: {result.stderr}")
                        raise Exception(f"Command failed: {cmd}\nStdout: {result.stdout}\nStderr: {result.stderr}")
                    else:
                        print(f"STDOUT: {result.stdout}")
                        if result.stderr:
                            print(f"STDERR: {result.stderr}")
                except Exception as e:
                    print(f"{Configuration.get_log_fail()} Command failed: {cmd}")
                    raise
            
            print(f"{Configuration.get_log_success()} Build commands completed")
            
            # Run docker build
            run_command(f"docker build -t {component.image} .", check=True)
    
    def is_container_healthy(self, component):
        """Check if container is healthy based on type"""
        checker_name = Configuration.get_health_checker(component.type)
        
        if checker_name == 'default_health_check' and component.type not in Configuration._HEALTH_CHECKERS:
            print(f"⚠️ Warning: No health checker registered for type '{component.type}'. Using default (assume healthy).")
        
        checker = getattr(HealthOps, checker_name, HealthOps.default_health_check)
        return checker(component)
    
    def prune_images(self):
        """Prune dangling images"""
        run_command("docker image prune -f || true", check=False)
