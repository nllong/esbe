from __future__ import annotations

import os
import subprocess
from pathlib import Path

from urbanopt_des.uo_cli_wrapper import UOCliWrapper


class DockerUOCliWrapper(UOCliWrapper):
    """UOCliWrapper that routes uo commands through a Docker container.

    The host ``mount_subdir`` directory (default ``esbe_2026``) is mounted
    read/write into the container at ``/workspace/<mount_subdir>``.  Paths
    passed as ``working_dir`` are automatically translated from host to
    container equivalents so that all file I/O lands in the same place on
    both sides.
    """

    def __init__(
        self,
        working_dir: Path,
        uo_project: str,
        template_dir: Path,
        image_tag: str = "urbanopt-cli:1.2-ubuntu22",
        repo_root: Path | None = None,
        mount_subdir: str = "esbe_2026",
    ) -> None:
        super().__init__(working_dir, uo_project, template_dir)
        self.image_tag = image_tag
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]
        self.mount_subdir = mount_subdir

    # ------------------------------------------------------------------
    # Mount helpers
    # ------------------------------------------------------------------

    @property
    def _mount_source(self) -> Path:
        return self.repo_root / self.mount_subdir

    @property
    def _mount_target(self) -> Path:
        return Path("/workspace") / self.mount_subdir

    def _host_to_container_path(self, host_path: Path) -> Path:
        """Translate an absolute host path to its container equivalent."""
        try:
            rel = host_path.resolve().relative_to(self._mount_source.resolve())
            return self._mount_target / rel
        except ValueError:
            # Fallback: use the mount target root
            return self._mount_target

    # ------------------------------------------------------------------
    # Override the command runner
    # ------------------------------------------------------------------

    def _gem_developer_key_env_args(self) -> list[str]:
        gem_key = os.getenv("GEM_DEVELOPER_KEY")
        if gem_key:
            return ["-e", f"GEM_DEVELOPER_KEY={gem_key}"]

        print("GEM_DEVELOPER_KEY is not set; continuing without it.")
        return []

    @staticmethod
    def _redact_docker_cmd(cmd: list[str]) -> list[str]:
        redacted: list[str] = []
        for item in cmd:
            if item.startswith("GEM_DEVELOPER_KEY="):
                redacted.append("GEM_DEVELOPER_KEY=***")
            else:
                redacted.append(item)
        return redacted

    def _run_command(self, command: str) -> None:  # type: ignore[override]
        container_workdir = self._host_to_container_path(
            Path(self.working_dir).resolve()
        )

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self._mount_source}:{self._mount_target}",
            "-w",
            str(container_workdir),
            *self._gem_developer_key_env_args(),
            self.image_tag,
            "bash",
            "-c",
            command,
        ]

        with open(self.log_file, "a") as log:
            log.write(
                f"Running Docker command: {' '.join(self._redact_docker_cmd(docker_cmd))}\n"
            )
            result = subprocess.run(docker_cmd, capture_output=True, check=False)  # noqa: S603
            stdout = result.stdout.decode("utf-8")
            stderr = result.stderr.decode("utf-8")
            log.write(stdout)
            log.write(stderr)
            print(stdout)
            if stderr:
                print(stderr)
