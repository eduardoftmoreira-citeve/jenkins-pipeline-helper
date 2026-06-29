#!/usr/bin/env python3
"""
Node.js operations for building Node.js applications.
"""

import shutil
import subprocess
import os

from config import Configuration


class NodeOps:
    """Handles Node.js installation and build operations."""
    
    def ensure_nodejs(self):
        """Check if Node.js is installed, install if not."""
        if shutil.which('node') and shutil.which('npm'):
            node_version = subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip()
            npm_version = subprocess.run(['npm', '--version'], capture_output=True, text=True).stdout.strip()
            print(f"{Configuration.get_log_info()} Node.js found: {node_version}, npm: {npm_version}")
            return True
        
        print(f"{Configuration.get_log_info()} Node.js not found. Installing...")
        
        try:
            subprocess.run(['apt-get', 'update', '-qq'], check=True)
            subprocess.run(['apt-get', 'install', '-y', '-qq', 'curl', 'ca-certificates', 'gnupg2'], check=True)
            
            setup_script = subprocess.run(
                ['curl', '-fsSL', 'https://deb.nodesource.com/setup_20.x'],
                capture_output=True,
                check=True
            )
            subprocess.run(['bash'], input=setup_script.stdout, check=True)
            
            subprocess.run(['apt-get', 'install', '-y', '-qq', 'nodejs'], check=True)
            
            node_version = subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip()
            print(f"{Configuration.get_log_success()} Node.js installed: {node_version}")
            return True
            
        except Exception as e:
            print(f"{Configuration.get_log_fail()} Failed to install Node.js: {e}")
            return False
    
    def build_node_project(self, component, project_path):
        """Build a Node.js project: npm install + npm run build."""
        if not component.is_nodejs():
            return True
        
        print(f"{Configuration.get_log_info()} Building Node.js project: {component.name}")
        
        if not self.ensure_nodejs():
            raise Exception("Node.js is required but could not be installed")
        
        package_json = os.path.join(project_path, 'package.json')
        if not os.path.exists(package_json):
            print(f"{Configuration.get_log_warn()} No package.json found, skipping npm install")
            return True
        
        print(f"{Configuration.get_log_info()} Running npm install...")
        subprocess.run(['npm', 'install'], cwd=project_path, check=True)
        
        if component.has_build_command():
            print(f"{Configuration.get_log_info()} Running build...")
            subprocess.run(['npm', 'run', 'build'], cwd=project_path, check=True)
        
        print(f"{Configuration.get_log_success()} Node.js project built: {component.name}")
        return True
