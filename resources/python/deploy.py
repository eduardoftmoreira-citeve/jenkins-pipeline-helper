#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Set

from deploylib.command import CommandRunner
from deploylib.config import load_application_config, load_platform_config
from deploylib.docker import DockerClient
from deploylib.engine import DeploymentEngine
from deploylib.environment import normalize_branch, resolve_environment
from deploylib.model import ProjectSpec


def active_branches(repo_url: str) -> Set[str]:
    if not repo_url:
        raise ValueError("--repo-url is required for cleanup")
    remote = repo_url
    token = os.environ.get("GITHUB_TOKEN")
    if token and remote.startswith("https://") and "@" not in remote.split("//", 1)[1]:
        remote = "https://x-access-token:" + token + "@" + remote[len("https://"):]
    result = subprocess.run(["git", "ls-remote", "--heads", remote], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Unable to list remote branches: {result.stderr.strip() or result.stdout.strip()}")
    branches: Set[str] = set()
    for line in result.stdout.splitlines():
        if "refs/heads/" in line:
            branches.add(normalize_branch(line.rsplit("refs/heads/", 1)[1]))
    return branches


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Provider-based Docker deployment engine")
    root.add_argument("--debug", action="store_true", help="Show tracebacks on failure")
    commands = root.add_subparsers(dest="command", required=True)

    deploy = commands.add_parser("deploy", help="Build and deploy the application")
    deploy.add_argument("--branch", required=True)
    deploy.add_argument("--build-number", required=True)
    deploy.add_argument("--workspace", required=True)
    deploy.add_argument("--platform-config", required=True)

    cleanup = commands.add_parser("cleanup", help="Remove feature/bugfix deployments whose branches no longer exist")
    cleanup.add_argument("--workspace", required=True)
    cleanup.add_argument("--platform-config", required=True)
    cleanup.add_argument("--repo-url", required=True)

    maintenance = commands.add_parser("maintenance", help="Run a provider-neutral maintenance operation")
    maintenance.add_argument("--operation", choices=("backup", "restore"), required=True)
    maintenance.add_argument("--branch", required=True, help="Environment branch, such as main or staging")
    maintenance.add_argument("--workspace", required=True)
    maintenance.add_argument("--platform-config", required=True)
    maintenance.add_argument("--archive", help="Required for restore")
    maintenance.add_argument("--confirm-environment", help="Required for destructive restore")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        workspace = Path(args.workspace).resolve()
        if not workspace.is_dir():
            raise FileNotFoundError(f"Workspace does not exist: {workspace}")
        app_raw = load_application_config(workspace)
        project = ProjectSpec.from_dict(app_raw)
        platform = load_platform_config(Path(args.platform_config).resolve())
        engine = DeploymentEngine(platform, DockerClient(CommandRunner(debug=args.debug)))

        if args.command == "deploy":
            environment = resolve_environment(args.branch)
            state = engine.deploy(project, environment, workspace, args.build_number)
            print(f"Deployed {project.name} to {environment.name}")
            for service in state.get("services", {}).values():
                if service.get("route"):
                    print(f"Route: {service['route']}")
            return 0

        if args.command == "cleanup":
            count = engine.cleanup_orphans(project, active_branches(args.repo_url))
            print(f"Removed {count} orphaned ephemeral environment(s) for {project.name}")
            return 0

        environment = resolve_environment(args.branch)
        results = engine.maintain(
            project,
            environment,
            operation=args.operation,
            archive=Path(args.archive) if args.archive else None,
            confirmation=args.confirm_environment,
        )
        if args.operation == "backup":
            for result in results:
                verification = "verified" if result["verified_restore"] else "checksum-only"
                print(f"Backup [{result['provider']}/{result['resource']}, {verification}]: {result['archive']}")
        else:
            for result in results:
                print(f"Restored [{result['provider']}/{result['resource']}]: {result['archive']}")
        return 0
    except Exception as exc:
        print(f"Deployment operation failed: {exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
