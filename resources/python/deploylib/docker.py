from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .command import CommandResult, CommandRunner


class DockerClient:
    def __init__(self, runner: CommandRunner):
        self.runner = runner

    def ensure_network(self, name: str) -> None:
        if self.runner.run(["docker", "network", "inspect", name], check=False).returncode != 0:
            self.runner.run(["docker", "network", "create", name])

    def remove_network(self, name: str) -> None:
        self.runner.run(["docker", "network", "rm", name], check=False)

    def connect_network(self, network: str, container: str) -> None:
        self.runner.run(["docker", "network", "connect", network, container], check=False)

    def disconnect_network(self, network: str, container: str) -> None:
        self.runner.run(["docker", "network", "disconnect", "-f", network, container], check=False)

    def container_exists(self, name: str) -> bool:
        return self.runner.run(["docker", "container", "inspect", name], check=False).returncode == 0

    def running(self, name: str) -> bool:
        result = self.runner.run(["docker", "inspect", "--format", "{{.State.Running}}", name], check=False)
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    def container_image(self, name: str) -> Optional[str]:
        result = self.runner.run(["docker", "inspect", "--format", "{{.Config.Image}}", name], check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def remove_container(self, name: str) -> None:
        self.runner.run(["docker", "rm", "-f", name], check=False)

    def restart_container(self, name: str) -> None:
        self.runner.run(["docker", "restart", name])

    def remove_volume(self, name: str) -> None:
        self.runner.run(["docker", "volume", "rm", name], check=False)

    def build_image(self, tag: str, dockerfile: str, context: str, build_args: Dict[str, str]) -> None:
        args: List[str] = ["docker", "build", "--tag", tag, "--file", dockerfile]
        for key, value in sorted(build_args.items()):
            args.extend(["--build-arg", f"{key}={value}"])
        args.append(context)
        self.runner.run(args)

    def run_container(
        self,
        *,
        name: str,
        image: str,
        network: str,
        labels: Dict[str, str],
        environment: Dict[str, str],
        volumes: Iterable[str] = (),
        command: Sequence[str] = (),
        restart_policy: Optional[str] = "unless-stopped",
    ) -> None:
        self.remove_container(name)
        args: List[str] = ["docker", "run", "-d", "--name", name, "--network", network]
        if restart_policy:
            args.extend(["--restart", restart_policy])
        for key, value in sorted(labels.items()):
            args.extend(["--label", f"{key}={value}"])
        for key, value in sorted(environment.items()):
            args.extend(["--env", f"{key}={value}"])
        for volume in volumes:
            args.extend(["--volume", volume])
        args.append(image)
        args.extend(command)
        self.runner.run(args)

    def exec(
        self,
        container: str,
        command: Sequence[str],
        *,
        environment: Optional[Dict[str, str]] = None,
        input_text: Optional[str] = None,
        check: bool = True,
    ) -> CommandResult:
        args: List[str] = ["docker", "exec", "-i"]
        for key, value in sorted((environment or {}).items()):
            args.extend(["--env", f"{key}={value}"])
        args.append(container)
        args.extend(command)
        return self.runner.run(args, input_text=input_text, check=check)

    def exec_to_file(self, container: str, command: Sequence[str], destination: Path, *, check: bool = True) -> CommandResult:
        args: List[str] = ["docker", "exec", "-i", container]
        args.extend(command)
        return self.runner.run_to_file(args, destination, check=check)

    def copy_to_container(self, container: str, source: Path, target: str) -> None:
        self.runner.run(["docker", "cp", str(source), f"{container}:{target}"])

    def http_status(self, network: str, image: str, url: str) -> Optional[int]:
        result = self.runner.run(
            [
                "docker", "run", "--rm", "--network", network, image,
                "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", url,
            ],
            check=False,
        )
        try:
            return int(result.stdout.strip())
        except ValueError:
            return None

    def prune_dangling_images(self) -> None:
        self.runner.run(["docker", "image", "prune", "-f"], check=False)
