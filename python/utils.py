import re
import subprocess
import time
from config import Configuration

#
def clean_branch(raw_branch):
    branch = raw_branch.split('/')[-1]
    return re.sub(r'[^a-zA-Z0-9-]', '-', branch.replace('/', '-'))

def is_authorized_branch(branch):
    """Check if branch is authorized for deployment"""
    if branch in Configuration.get_static_branches():
        return True
    
    for prefix in Configuration.get_prefix_branches():
        if branch.startswith(prefix):
            return True
    
    return False

def detect_environment(branch):
    """Detect environment from branch name"""
    if branch in ['main', 'master']:
        return 'production'
    elif branch == 'staging':
        return 'staging'
    elif branch == 'develop':
        return 'development'
    else:
        return 'development'  # feature branches → development

def get_config_file(branch):
    """Return the appropriate config file name for the branch"""
    if branch == 'main':
        return 'app-config.prod.yaml'
    elif branch == 'staging':
        return 'app-config.staging.yaml'
    elif branch == 'develop':
        return 'app-config.dev.yaml'
    else:
        return 'app-config.yaml'

def allocate_port(project):
    """Find an available port starting from search_start"""
    start_port = Configuration.get_port_search_start()
    max_range = Configuration.get_port_search_range()
    
    # If API has no port specified, find one
    api_component = project.get_component('api')
    if not api_component:
        return ''
    
    container_name = f"{project.name}-api-{project.branch}"
    
    # Check for sticky port
    try:
        result = subprocess.run(
            f"docker inspect -f '{{{{(index (index .HostConfig.PortBindings \\\"3000/tcp\\\") 0).HostPort}}}}' {container_name} 2>/dev/null || echo ''",
            shell=True, capture_output=True, text=True
        )
        sticky_port = result.stdout.strip()
        if sticky_port:
            return sticky_port
    except:
        pass
    
    # Find new port
    for port in range(start_port, start_port + max_range + 1):
        docker_used = subprocess.run(
            f"docker ps -a --format '{{{{.Ports}}}}' | grep ':{port}->' || true",
            shell=True, capture_output=True, text=True
        ).stdout.strip()
        
        system_used = subprocess.run(
            f"ss -tuln 2>/dev/null | grep ':{port} ' || netstat -tuln 2>/dev/null | grep ':{port} ' || true",
            shell=True, capture_output=True, text=True
        ).stdout.strip()
        
        if not docker_used and not system_used:
            return str(port)
    
    raise Exception(f"No available ports in range {start_port} to {start_port + max_range}")

def wait_for_health(component, docker_ops):
    """Wait for container to be healthy"""
    timeout = component.get_health_timeout()
    interval = 5
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if docker_ops.is_container_healthy(component):
            return True
        time.sleep(interval)
    
    raise Exception(f"Health check timeout for {component.name}")

def build_env_vars(env_dict):
    """Convert dict to Docker env vars string"""
    return ' '.join([f"-e {k}={v}" for k, v in env_dict.items()])

def get_container_ip(container_name):
    """Get container IP address"""
    try:
        result = subprocess.run(
            f"docker inspect -f '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {container_name}",
            shell=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except:
        return None

def run_command(cmd, check=True):
    """Run a shell command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise Exception(f"Command failed: {cmd}\nError: {result.stderr}")
    return result.stdout.strip()

def merge_configs(base_config, override_config):
    """Merge two config dictionaries"""
    merged = base_config.copy()
    for key, value in override_config.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged