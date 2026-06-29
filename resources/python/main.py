#!/usr/bin/env python3
import sys
import json
import argparse
import traceback
import subprocess
import yaml
from config import Configuration
from models import Project, Component
from docker_ops import DockerOps
from nginx_ops import NginxOps
from cleanup_ops import CleanupOps
from github_ops import GitHubOps
from ollama_ops import OllamaOps
from utils import (
    is_authorized_branch,
    detect_environment,
    allocate_port,
    wait_for_health,
    clean_branch,
    get_config_file,
    load_config,
    get_database_container_name
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--branch', required=True)
    parser.add_argument('--build-number', required=True)
    parser.add_argument('--change-id', default='')
    parser.add_argument('--change-target', default='')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--repo-url', required=True)
    parser.add_argument('--config-file', default=None, help='Override automatic config detection')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()
    
    if args.debug:
        print("DEBUGGING ENABLED")
        print(f"Args: {args}")

    branch = clean_branch(args.branch)
    environment = detect_environment(branch)
    
    try:
        config = load_config(branch, args.config_file)
        
        is_pr = bool(args.change_id)
        is_scheduled = False
        
        project = Project(config)
        for name, service_config in config['services'].items():
            project.add_component(Component(name, service_config))
        
        print(f"{Configuration.get_log_info()} Deploying {project.name}")
        print(f"{Configuration.get_log_info()} Branch: {branch}")
        print(f"{Configuration.get_log_info()} Environment: {environment}")
        print(f"{Configuration.get_log_info()} Config file: {args.config_file if args.config_file else get_config_file(branch)}")
        print(f"{Configuration.get_log_info()} PR: {is_pr}")
        
        docker = DockerOps()
        nginx = NginxOps()
        cleanup = CleanupOps()
        github = GitHubOps(args.repo_url)
        ollama = OllamaOps()
        
        if not is_authorized_branch(branch):
            print(f"{Configuration.get_log_fail()} Branch '{branch}' not authorized.")
            sys.exit(1)
        
        project.branch = branch
        project.port = allocate_port(project)
        
        for component in project.components:
            if component.is_infrastructure():
                component.container_name = get_database_container_name(project, component, branch)
            else:
                component.container_name = f"{project.name}-{component.name}-{branch}"
            component.network = project.net_name
        
        if not is_pr:
            print(f"{Configuration.get_log_info()} Cleaning up orphaned resources...")
            cleanup.cleanup_orphaned(project, args.repo_url)
        
        if not is_pr:
            print(f"{Configuration.get_log_info()} Setting up infrastructure...")
            docker.create_network(project.net_name)
            docker.connect_to_network(project.net_name, Configuration.get_nginx_container())
            
            for component in project.components:
                if component.is_infrastructure():
                    docker.start_container(component, project.net_name)
        
        if not is_pr:
            print(f"{Configuration.get_log_info()} Building components...")
            for component in project.components:
                if component.has_build_command():
                    docker.build_container(component)
        
        if not is_pr:
            print(f"{Configuration.get_log_info()} Deploying components...")
            for component in project.components:
                if component.is_deployable():
                    docker.start_container(component, project.net_name)
        
        if not is_pr:
            print(f"{Configuration.get_log_info()} Running health checks...")
            for component in project.components:
                if component.has_health_check():
                    wait_for_health(component, docker)
                    print(f"{Configuration.get_log_success()} {component.name} is healthy")
        
        if not is_pr:
            print(f"{Configuration.get_log_info()} Configuring proxy...")
            nginx.deploy_config(project, branch)
            print(f"{Configuration.get_log_success()} App live at: dev.citeve.pt/{Configuration.get_pilot_tag()}/{project.name}/{branch}/")
        
        if is_pr and args.change_target:
            print(f"{Configuration.get_log_info()} Running AI Code Review...")
            diff = ollama.get_diff(args.change_target, args.repo_url)
            if diff:
                review = ollama.review_diff(diff)
                github.post_pr_comment(args.change_id, review)
        
        if is_scheduled and branch in ['main', 'master']:
            print(f"{Configuration.get_log_info()} Running scheduled health check...")
            cleanup.scheduled_health_check(project, branch)
        
        docker.prune_images()
        
        print(f"{Configuration.get_log_success()} Pipeline completed successfully!")
    
    except Exception as e:
        print("ERROR ON PIPELINE EXECUTION")

        if args.debug:
            print("=" * 60)
            traceback.print_exc()
            print("=" * 60)
        else:
            print(f"Error: {e}")
            print("Run with --debug for full traceback")
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"{Configuration.get_log_fail()} Error: {e}")
        sys.exit(1)