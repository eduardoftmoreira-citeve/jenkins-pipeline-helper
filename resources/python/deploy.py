#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Dict, Set

from deploylib.command import CommandRunner
from deploylib.config import load_application_config, load_platform_config
from deploylib.docker import DockerClient
from deploylib.engine import DeploymentEngine
from deploylib.environment import normalize_branch, resolve_environment
from deploylib.model import ProjectSpec
from deploylib.review import review_open_pull_request


def progress(message: str) -> None:
    print(f"[deploy {datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def print_deploy_summary(project: ProjectSpec, state: Dict[str, Any], engine: DeploymentEngine) -> None:
    environment = state.get("environment", {})
    print("")
    print("=== Deployment summary ===")
    print(f"Project: {project.name}")
    print(f"Branch: {environment.get('branch', 'unknown')}")
    print(f"Environment: {environment.get('name', 'unknown')} ({environment.get('kind', 'unknown')})")
    print(f"Network: {state.get('network', 'unknown')}")

    resources = state.get("resources", {})
    if resources:
        print("Infrastructure:")
        for resource in resources.values():
            container = resource.get("container", "unknown")
            image = resource.get("image")
            detail = f" [{image}]" if image else ""
            print(f"  - {resource.get('name', 'unknown')} ({resource.get('type', 'unknown')}): {container}{detail}")

    services = state.get("services", {})
    if services:
        print("Services:")
        for service in services.values():
            container = service.get("container", "unknown")
            image = service.get("image")
            detail = f" [{image}]" if image else ""
            print(f"  - {service.get('name', 'unknown')} ({service.get('type', 'unknown')}): {container}{detail}")
            if service.get("route"):
                print(f"    App live at: {engine.router.public_url(service['route'])}")
    print("==========================")


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

    review = commands.add_parser("review", help="Generate and publish an Ollama pull-request review")
    review.add_argument("--workspace", required=True)
    review.add_argument("--platform-config", required=True)
    review.add_argument("--repo-url", required=True)
    review.add_argument("--branch", required=True, help="Source branch from the normal multibranch build")
    review.add_argument("--dry-run", action="store_true", help="Generate a review without posting to GitHub")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        workspace = Path(args.workspace).resolve()
        if not workspace.is_dir():
            raise FileNotFoundError(f"Workspace does not exist: {workspace}")
        platform = load_platform_config(Path(args.platform_config).resolve())

        if args.command == "review":
            result = review_open_pull_request(
                settings=platform.review,
                workspace=workspace,
                repo_url=args.repo_url,
                branch=args.branch,
                dry_run=args.dry_run,
            )
            print(result.message)
            if result.review_text:
                print("\n--- Ollama review ---\n" + result.review_text)
            if result.comment_url:
                print(f"GitHub comment: {result.comment_url}")
            return 0

        app_raw = load_application_config(workspace)
        project = ProjectSpec.from_dict(app_raw)
        engine = DeploymentEngine(platform, DockerClient(CommandRunner(debug=args.debug)), reporter=progress)

        if args.command == "deploy":
            environment = resolve_environment(args.branch)
            state = engine.deploy(project, environment, workspace, args.build_number)
            print_deploy_summary(project, state, engine)
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
