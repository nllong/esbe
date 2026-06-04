#!/usr/bin/env python3
"""Run SSH checks and small patches across the ESBE student VMs."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class VM:
    user: str
    ip: str


@dataclass(frozen=True)
class RemoteResult:
    vm: VM
    ok: bool
    message: str


VMS = [
    VM("student1@esbe.energy", "35.224.206.182"),
    VM("student2@esbe.energy", "35.202.198.241"),
    VM("student3@esbe.energy", "35.226.125.148"),
    VM("student4@esbe.energy", "35.239.23.172"),
    VM("student5@esbe.energy", "35.253.176.235"),
    VM("student6@esbe.energy", "35.253.123.186"),
    VM("student7@esbe.energy", "34.136.109.74"),
    VM("student8@esbe.energy", "136.111.160.227"),
    VM("student9@esbe.energy", "34.28.147.108"),
    VM("student10@esbe.energy", "34.10.156.142"),
    VM("student11@esbe.energy", "34.30.59.25"),
    VM("student12@esbe.energy", "34.172.127.247"),
    VM("student13@esbe.energy", "35.239.185.248"),
    VM("student14@esbe.energy", "35.202.91.37"),
    VM("student15@esbe.energy", "34.173.82.101"),
    VM("student16@esbe.energy", "34.42.133.43"),
    VM("student17@esbe.energy", "35.254.21.13"),
    VM("student18@esbe.energy", "34.16.69.1"),
    VM("student19@esbe.energy", "146.148.41.252"),
    VM("student20@esbe.energy", "136.114.90.10"),
    VM("student21@esbe.energy", "34.16.101.27"),
    VM("student22@esbe.energy", "23.251.145.106"),
    VM("student23@esbe.energy", "34.71.192.82"),
    VM("student24@esbe.energy", "34.10.220.243"),
    VM("student25@esbe.energy", "136.115.151.172"),
    VM("student26@esbe.energy", "34.58.230.131"),
    VM("student27@esbe.energy", "34.67.145.168"),
    VM("student28@esbe.energy", "136.119.120.171"),
]


SSH_USER = "tr406"

DEFAULT_TIMEOUT_SECONDS = 5 * 60


PATCHES = {
    "copy-baseline": (
        "cp /mnt/data/uo/diverse/mappers/Baseline.rb /mnt/data/uo/coincident/mappers/"
    ),
    "backup-and-disable-pmv": (
        "sudo mkdir -p /mnt/data/uo/coincident/mappers/_archive /mnt/data/uo/diverse/mappers/_archive && "
        "cp /mnt/data/uo/coincident/mappers/Baseline.rb "
        "/mnt/data/uo/coincident/mappers/_archive/Baseline_backup_20260603.rb && "
        "cp /mnt/data/uo/diverse/mappers/Baseline.rb "
        "/mnt/data/uo/diverse/mappers/_archive/Baseline_backup_20260603.rb && "
        "perl -pi -e \"s/OpenStudio::Extension\\.set_measure_argument\\(osw, 'PredictedMeanVote', '__SKIP__', false\\)/OpenStudio::Extension.set_measure_argument(osw, 'PredictedMeanVote', '__SKIP__', true)/g\" "
        "/mnt/data/uo/coincident/mappers/Baseline.rb "
        "/mnt/data/uo/diverse/mappers/Baseline.rb"
    ),
    "install-gedit": "sudo apt update && sudo NEEDRESTART_MODE=a DEBIAN_FRONTEND=noninteractive apt install -y gedit",
    "set-firefox-default-browser": "xdg-settings set default-web-browser firefox.desktop",
    "move_backup_files": (
        "sudo mkdir -p /mnt/data/uo/coincident/mappers/_archive /mnt/data/uo/diverse/mappers/_archive && "
        "if [ -f /mnt/data/uo/coincident/mappers/Baseline_backup_20260603.rb ]; then "
        "sudo mv /mnt/data/uo/coincident/mappers/Baseline_backup_20260603.rb /mnt/data/uo/coincident/mappers/_archive/ && "
        "echo 'coincident backup moved'; "
        "else echo 'coincident backup not found, skipped'; fi && "
        "if [ -f /mnt/data/uo/diverse/mappers/Baseline_backup_20260603.rb ]; then "
        "sudo mv /mnt/data/uo/diverse/mappers/Baseline_backup_20260603.rb /mnt/data/uo/diverse/mappers/_archive/ && "
        "echo 'diverse backup moved'; "
        "else echo 'diverse backup not found, skipped'; fi"
    ),
    "install-zip": "sudo apt update && sudo NEEDRESTART_MODE=a DEBIAN_FRONTEND=noninteractive apt install -y zip",
}


WHO_CONNECTED_COMMAND = (
    "if /usr/bin/who | grep -q .; then "
    "/usr/bin/who; "
    "else "
    "printf 'no active login sessions\\n'; "
    "fi"
)


class VMRunner:
    def __init__(
        self,
        vms: list[VM],
        ssh_user: str,
        key_file: str | None,
        timeout: int,
        workers: int,
    ) -> None:
        self.vms = vms
        self.ssh_user = ssh_user
        self.key_file = os.path.expanduser(key_file) if key_file else None
        self.timeout = timeout
        self.workers = workers

    def run_all(self, remote_command: str) -> list[RemoteResult]:
        results: list[RemoteResult] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.workers
        ) as executor:
            futures = [
                executor.submit(self.run_one, vm, remote_command) for vm in self.vms
            ]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                self.print_result(result)
                results.append(result)

        passed = sum(result.ok for result in results)
        failed = len(results) - passed
        print(f"\nSummary: {passed} OK, {failed} failed")
        return results

    def run_one(self, vm: VM, remote_command: str) -> RemoteResult:
        target = f"{self.ssh_user}@{vm.ip}"
        command = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.timeout}",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "PasswordAuthentication=no",
        ]

        if self.key_file:
            command.extend(["-i", self.key_file])

        command.extend([target, remote_command])

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.timeout + 5,
            check=False,
        )

        if result.returncode == 0:
            return RemoteResult(vm, True, result.stdout.strip() or "done")

        message = (result.stderr or result.stdout).strip().splitlines()
        return RemoteResult(
            vm,
            False,
            message[-1] if message else f"ssh exited {result.returncode}",
        )

    @staticmethod
    def print_result(result: RemoteResult) -> None:
        status = "OK" if result.ok else "FAIL"
        lines = result.message.splitlines() or [""]
        print(f"{status:4} {result.vm.user:25} {result.vm.ip:15} {lines[0]}")
        for line in lines[1:]:
            print(f"{'':4} {'':25} {'':15} {line}")
        print(f"{'':4} {'':25} {'':15} ssh -i ~/.ssh/uo_esbe {SSH_USER}@{result.vm.ip}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--key",
        default="~/.ssh/uo_esbe",
        help="Private key path.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="SSH timeout in seconds (default: 300 = 5 minutes).",
    )
    parser.add_argument("--workers", type=int, default=8, help="Parallel SSH checks.")
    subparsers = parser.add_subparsers(dest="action")

    subparsers.add_parser(
        "verify", help="Confirm SSH access and print remote hostname."
    )
    subparsers.add_parser(
        "who", help="Print who output on each VM to show connected users."
    )

    patch_parser = subparsers.add_parser("patch", help="Run a named remote patch.")
    patch_parser.add_argument("name", nargs="?", choices=sorted(PATCHES))

    run_parser = subparsers.add_parser("run", help="Run an arbitrary remote command.")
    run_parser.add_argument("command")

    args = parser.parse_args()

    runner = VMRunner(VMS, SSH_USER, args.key, args.timeout, args.workers)

    if args.action in (None, "verify"):
        results = runner.run_all("printf 'ok:%s\\n' \"$(hostname)\"")
    elif args.action == "who":
        results = runner.run_all(WHO_CONNECTED_COMMAND)
    elif args.action == "patch":
        if args.name is None:
            print("Available patches:")
            for name, command in sorted(PATCHES.items()):
                print(f"  {name}: {command}")
            print("\nRun a patch with:")
            print("  python3 vm_management/verify_ssh_access.py patch <patch-name>")
            return 0
        results = runner.run_all(PATCHES[args.name])
    elif args.action == "run":
        results = runner.run_all(args.command)
    else:
        parser.error(f"unknown action: {args.action}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
