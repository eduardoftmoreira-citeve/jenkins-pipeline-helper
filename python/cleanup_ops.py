import subprocess
from config import Configuration
from docker_ops import DockerOps
from nginx_ops import NginxOps
from utils import run_command

class CleanupOps:
    
    def __init__(self):
        self.docker = DockerOps()
        self.nginx = NginxOps()
    
    def _get_active_branches(self, repo_url):
        token = Configuration.get_env('GITHUB_TOKEN')
        
        if token:
            repo_url = repo_url.replace('https://', f'https://{token}@')
        
        result = subprocess.run(
            f"git ls-remote --heads {repo_url}",
            shell=True, capture_output=True, text=True
        )
        
        branches = []
        for line in result.stdout.split('\n'):
            if 'refs/heads/' in line:
                branch = line.split('refs/heads/')[-1]
                branches.append(branch)
        return branches
    
    def _extract_branch(self, container_name):
        parts = container_name.split('-')
        return '-'.join(parts[2:])
    
    def _cleanup_mongo_database(self, container_name, db_name):
        run_command(
            f"docker exec {container_name} mongosh --eval \"db.getSiblingDB('{db_name}').dropDatabase()\" 2>/dev/null || true",
            check=False
        )
    
    def _cleanup_postgres_database(self, container_name, db_name):
        run_command(
            f"docker exec {container_name} dropdb -U postgres {db_name} 2>/dev/null || true",
            check=False
        )
    
    def cleanup_orphaned(self, project, repo_url):
        print(f"{Configuration.get_log_info()} Checking for orphaned resources...")
        
        active_branches = self._get_active_branches(repo_url)
        containers = self.docker.get_all_containers(f"{project.name}-")
        
        for container in containers:
            if not container:
                continue
            
            parts = container.split('-')
            branch = '-'.join(parts[2:])
            
            if branch not in active_branches:
                if 'shared' in container:
                    print(f"{Configuration.get_log_warning()} Dropping orphaned database for branch '{branch}' from shared container")
                    
                    if 'mongo' in container:
                        db_name = f"{project.name}_{branch.replace('-', '_')}"
                        self._cleanup_mongo_database(container, db_name)
                    
                    elif 'postgres' in container:
                        db_name = f"{project.name}_{branch.replace('-', '_')}"
                        self._cleanup_postgres_database(container, db_name)
                    
                    continue
                
                print(f"{Configuration.get_log_warning()} Removing orphaned container: {container}")
                self.docker.remove_container(container)
                
                if 'mongo' in container:
                    db_name = f"{project.name}_{branch.replace('-', '_')}"
                    self._cleanup_mongo_database(container, db_name)
                
                if 'postgres' in container:
                    db_name = f"{project.name}_{branch.replace('-', '_')}"
                    self._cleanup_postgres_database(container, db_name)
                
                self.nginx.remove_config(project, branch)
        
        self.nginx.reload()
        self.docker.prune_images()
        
        print(f"{Configuration.get_log_success()} Cleanup completed")
    
    def scheduled_health_check(self, project, branch):
        print(f"{Configuration.get_log_info()} Running scheduled health check for {project.name}/{branch}")
        
        rescued = self.docker.check_and_rescue_containers(project, branch)
        
        if rescued:
            print(f"{Configuration.get_log_success()} Rescued containers: {', '.join(rescued)}")
        else:
            print(f"{Configuration.get_log_info()} All containers are healthy")
        
        nginx_status = self.nginx.get_nginx_container_status()
        if nginx_status != 'running':
            print(f"{Configuration.get_log_warning()} Nginx is not running, attempting to restart...")
            self.nginx.reload()
        
        return rescued