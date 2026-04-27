from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass
class UrbanoptDockerRunner:
    """Run URBANopt CLI commands in Docker against local esbe_2026 files."""

    image_tag: str = "urbanopt-cli:1.2-ubuntu22"
    repo_root: Path = Path(__file__).resolve().parents[1]
    mount_subdir: str = "esbe_2026"

    @property
    def dockerfile(self) -> Path:
        return self.repo_root / "docker" / "urbanopt-cli" / "Dockerfile"

    @property
    def mount_source(self) -> Path:
        return self.repo_root / self.mount_subdir

    @property
    def mount_target(self) -> Path:
        return Path("/workspace") / self.mount_subdir

    def _gem_developer_key_env_args(self) -> list[str]:
        gem_key = os.getenv("GEM_DEVELOPER_KEY")
        if gem_key:
            return ["-e", f"GEM_DEVELOPER_KEY={gem_key}"]

        print("GEM_DEVELOPER_KEY is not set; continuing without it but REopt will not work.")
        return []

    def build_image(self) -> subprocess.CompletedProcess[str]:
        cmd = [
            "docker",
            "build",
            "-t",
            self.image_tag,
            "-f",
            str(self.dockerfile),
            str(self.repo_root),
        ]
        return subprocess.run(cmd, check=False, text=True)

    def run_uo(
        self,
        uo_args: Sequence[str],
        working_dir: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if not self.mount_source.exists():
            raise FileNotFoundError(f"Missing mount source: {self.mount_source}")

        target_workdir = self.mount_target if working_dir is None else self.mount_target / working_dir
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self.mount_source}:{self.mount_target}",
            "-w",
            str(target_workdir),
            *self._gem_developer_key_env_args(),
            self.image_tag,
            "uo",
            *uo_args,
        ]
        return subprocess.run(cmd, check=False, text=True, capture_output=True)

    def run_shell(self, command: str, working_dir: str | None = None) -> subprocess.CompletedProcess[str]:
        if not self.mount_source.exists():
            raise FileNotFoundError(f"Missing mount source: {self.mount_source}")

        target_workdir = self.mount_target if working_dir is None else self.mount_target / working_dir
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self.mount_source}:{self.mount_target}",
            "-w",
            str(target_workdir),
            *self._gem_developer_key_env_args(),
            self.image_tag,
            "bash",
            "-lc",
            command,
        ]
        return subprocess.run(cmd, check=False, text=True, capture_output=True)


def _print_process_result(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _parse_uo_args(args: Iterable[str]) -> list[str]:
    return [arg for arg in args]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run URBANopt CLI in Docker")
    parser.add_argument("--image-tag", default="urbanopt-cli:1.2-ubuntu22")
    parser.add_argument("--mount-subdir", default="esbe_2026")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build", help="Build the URBANopt Docker image")

    run_parser = subparsers.add_parser("run", help="Run a uo command")
    run_parser.add_argument("uo_args", nargs=argparse.REMAINDER, help="Arguments to pass to uo")
    run_parser.add_argument("--working-dir", default=None, help="Relative dir inside mounted esbe_2026")

    shell_parser = subparsers.add_parser("shell", help="Run a shell command in the container")
    shell_parser.add_argument("shell_command", help="Shell command executed with bash -lc")
    shell_parser.add_argument("--working-dir", default=None, help="Relative dir inside mounted esbe_2026")

    parsed = parser.parse_args()
    runner = UrbanoptDockerRunner(image_tag=parsed.image_tag, mount_subdir=parsed.mount_subdir)

    if parsed.command == "build":
        result = runner.build_image()
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        print(f"Built {parsed.image_tag}")
        return

    if parsed.command == "run":
        args = _parse_uo_args(parsed.uo_args)
        if not args:
            args = ["--help"]
        result = runner.run_uo(args, working_dir=parsed.working_dir)
        _print_process_result(result)
        return

    if parsed.command == "shell":
        result = runner.run_shell(parsed.shell_command, working_dir=parsed.working_dir)
        _print_process_result(result)
        return

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
