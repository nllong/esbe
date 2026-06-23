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


@dataclass(frozen=True)
class UploadSpec:
    local_path: str
    remote_path: str


@dataclass(frozen=True)
class PatchSpec:
    uploads: list[UploadSpec]
    remote_command: str


VMS = [
    VM("student1@esbe.energy", "34.69.192.155"),
    # VM("student1@esbe.energy", "35.224.206.182"),
    # VM("student2@esbe.energy", "35.202.198.241"),
    # VM("student3@esbe.energy", "35.226.125.148"),
    # VM("student4@esbe.energy", "35.239.23.172"),
    # VM("student5@esbe.energy", "35.253.176.235"),
    # VM("student6@esbe.energy", "35.253.123.186"),
    # VM("student7@esbe.energy", "34.136.109.74"),
    # VM("student8@esbe.energy", "136.111.160.227"),
    # VM("student9@esbe.energy", "34.28.147.108"),
    # VM("student10@esbe.energy", "34.10.156.142"),
    # VM("student11@esbe.energy", "34.30.59.25"),
    # VM("student12@esbe.energy", "34.172.127.247"),
    # VM("student13@esbe.energy", "35.239.185.248"),
    # VM("student14@esbe.energy", "35.202.91.37"),
    # VM("student15@esbe.energy", "34.173.82.101"),
    # VM("student16@esbe.energy", "34.42.133.43"),
    # VM("student17@esbe.energy", "35.254.21.13"),
    # VM("student18@esbe.energy", "34.16.69.1"),
    # VM("student19@esbe.energy", "146.148.41.252"),
    # VM("student20@esbe.energy", "136.114.90.10"),
    # VM("student21@esbe.energy", "34.16.101.27"),
    # VM("student22@esbe.energy", "23.251.145.106"),
    # VM("student23@esbe.energy", "34.71.192.82"),
    # VM("student24@esbe.energy", "34.10.220.243"),
    # VM("student25@esbe.energy", "136.115.151.172"),
    # VM("student26@esbe.energy", "34.58.230.131"),
    # VM("student27@esbe.energy", "34.67.145.168"),
    # VM("student28@esbe.energy", "136.119.120.171"),
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
    "reset-and-pull-esbe-repo": (
        "cd /mnt/data/uo/esbe && git reset --hard HEAD && git pull"
    ),
    "fix-coincident-reopt-ownership": (
        "if [ -d /mnt/data/uo/coincident/reopt ]; then "
        "sudo chown -R tr406:tr406 /mnt/data/uo/coincident/reopt && "
        "echo 'fixed ownership for /mnt/data/uo/coincident/reopt'; "
        "else "
        "echo '/mnt/data/uo/coincident/reopt not found, skipped'; "
        "fi"
    ),
    "move-backup-files": (
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
    "install-zip": "sudo apt update && sudo NEEDRESTART_MODE=a DEBIAN_FRONTEND=noninteractive apt install -y zip unzip",
    "copy-set-window-glazing-measure": PatchSpec(
        uploads=[
            UploadSpec(
                "/Users/nlong/working/openstudio/openstudio-mcp/measures/custom/set_simple_glazing.zip",
                "/tmp/set_simple_glazing.zip",
            )
        ],
        remote_command=(
            "for d in /mnt/data/uo/pat-morris/measures /mnt/data/uo/pat-lhs/measures /mnt/data/uo/pat-nsga/measures; do "
            'sudo mkdir -p "$d" && '
            'sudo cp /tmp/set_simple_glazing.zip "$d/" && '
            'sudo unzip -o "$d/set_simple_glazing.zip" -d "$d" && '
            'sudo chown -R tr406:tr406 "$d/set_simple_glazing" "$d/set_simple_glazing.zip"; '
            "done"
        ),
    ),
    "copy-set-wwr-measure": PatchSpec(
        uploads=[
            UploadSpec(
                "/Users/nlong/working/openstudio/openstudio-mcp/measures/custom/SetWindowToWallRatioByFacade.zip",
                "/tmp/SetWindowToWallRatioByFacade.zip",
            )
        ],
        remote_command=(
            "for d in /mnt/data/uo/pat-morris/measures /mnt/data/uo/pat-lhs/measures /mnt/data/uo/pat-nsga/measures; do "
            'sudo mkdir -p "$d" && '
            'sudo cp /tmp/SetWindowToWallRatioByFacade.zip "$d/" && '
            'sudo unzip -o "$d/SetWindowToWallRatioByFacade.zip" -d "$d" && '
            'sudo chown -R tr406:tr406 "$d/SetWindowToWallRatioByFacade" "$d/SetWindowToWallRatioByFacade.zip"; '
            "done"
        ),
    ),
    "copy-cop-single-speed-measure": PatchSpec(
        uploads=[
            UploadSpec(
                "/Users/nlong/working/openstudio/openstudio-mcp/measures/custom/SetCOPforSingleSpeedDXCoolingUnits.zip",
                "/tmp/SetCOPforSingleSpeedDXCoolingUnits.zip",
            )
        ],
        remote_command=(
            "for d in /mnt/data/uo/pat-morris/measures /mnt/data/uo/pat-lhs/measures /mnt/data/uo/pat-nsga/measures; do "
            'sudo mkdir -p "$d" && '
            'sudo cp /tmp/SetCOPforSingleSpeedDXCoolingUnits.zip "$d/" && '
            'sudo unzip -o "$d/SetCOPforSingleSpeedDXCoolingUnits.zip" -d "$d" && '
            'sudo chown -R tr406:tr406 "$d/SetCOPforSingleSpeedDXCoolingUnits" "$d/SetCOPforSingleSpeedDXCoolingUnits.zip"; '
            "done"
        ),
    ),
    "copy-cop-two-speed-measure": PatchSpec(
        uploads=[
            UploadSpec(
                "/Users/nlong/working/openstudio/openstudio-mcp/measures/custom/SetCOPforTwoSpeedDXCoolingUnits.zip",
                "/tmp/SetCOPforTwoSpeedDXCoolingUnits.zip",
            )
        ],
        remote_command=(
            "for d in /mnt/data/uo/pat-morris/measures /mnt/data/uo/pat-lhs/measures /mnt/data/uo/pat-nsga/measures; do "
            'sudo mkdir -p "$d" && '
            'sudo cp /tmp/SetCOPforTwoSpeedDXCoolingUnits.zip "$d/" && '
            'sudo unzip -o "$d/SetCOPforTwoSpeedDXCoolingUnits.zip" -d "$d" && '
            'sudo chown -R tr406:tr406 "$d/SetCOPforTwoSpeedDXCoolingUnits" "$d/SetCOPforTwoSpeedDXCoolingUnits.zip"; '
            "done"
        ),
    ),
    "fix-set-window-glazing-permissions": (
        "for d in /mnt/data/uo/pat-morris/measures /mnt/data/uo/pat-lhs/measures /mnt/data/uo/pat-nsga/measures; do "
        'if [ -e "$d/set_simple_glazing" ] || [ -e "$d/set_simple_glazing.zip" ]; then '
        'sudo chown -R tr406:tr406 "$d/set_simple_glazing" "$d/set_simple_glazing.zip" 2>/dev/null || true; '
        'echo "fixed ownership in $d"; '
        "else "
        'echo "set_simple_glazing not found in $d, skipped"; '
        "fi; "
        "done"
    ),
    "deploy-coincident-optimized-measures": PatchSpec(
        uploads=[
            # New measures from zip
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/measures/new_measures_1.zip",
                "/tmp/new_measures_1.zip",
            ),
            # Updated mapper files
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/BaselineOptimized.rb",
                "/tmp/BaselineOptimized.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/base_optimized_workflow.osw",
                "/tmp/base_optimized_workflow.osw",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Office1.rb",
                "/tmp/Office1.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Office2.rb",
                "/tmp/Office2.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Office3.rb",
                "/tmp/Office3.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Office4.rb",
                "/tmp/Office4.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Office6.rb",
                "/tmp/Office6.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Restaurant1.rb",
                "/tmp/Restaurant1.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Restaurant2.rb",
                "/tmp/Restaurant2.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Restaurant3.rb",
                "/tmp/Restaurant3.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Restaurant4.rb",
                "/tmp/Restaurant4.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/School1.rb",
                "/tmp/School1.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Mall1.rb",
                "/tmp/Mall1.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/mappers/Hotel1.rb",
                "/tmp/Hotel1.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/test_activities/class_version/coincident/classproject_optimized.csv",
                "/tmp/classproject_optimized.csv",
            ),
        ],
        remote_command=(
            "set -e; "
            "echo '[1/5] Creating destination directory...'; "
            "sudo mkdir -p /mnt/data/uo/coincident/measures /mnt/data/uo/coincident/mappers; "
            "echo '[2/5] Extracting new measures...'; "
            "sudo unzip -o /tmp/new_measures_1.zip -d /mnt/data/uo/coincident/measures; "
            "echo '[3/5] Copying mapper files...'; "
            "for mapper in BaselineOptimized.rb Office1.rb Office2.rb Office3.rb Office4.rb Office6.rb "
            "Restaurant1.rb Restaurant2.rb Restaurant3.rb Restaurant4.rb School1.rb Mall1.rb Hotel1.rb; do "
            'if [ -f "/tmp/$mapper" ]; then '
            'sudo cp "/tmp/$mapper" /mnt/data/uo/coincident/mappers/; '
            'echo "  ✓ copied $mapper"; '
            "else "
            'echo "  ⚠ $mapper not found in /tmp"; '
            "fi; "
            "done; "
            "echo '[4/5] Fixing permissions...'; "
            "if [ -f /tmp/base_optimized_workflow.osw ]; then "
            "sudo cp /tmp/base_optimized_workflow.osw /mnt/data/uo/coincident/mappers/base_optimized_workflow.osw; "
            "echo '  ✓ copied base_optimized_workflow.osw'; "
            "else "
            "echo '  ⚠ base_optimized_workflow.osw not found in /tmp'; "
            "fi; "
            "if [ -f /tmp/classproject_optimized.csv ]; then "
            "sudo cp /tmp/classproject_optimized.csv /mnt/data/uo/coincident/classproject_optimized.csv; "
            "echo '  ✓ copied classproject_optimized.csv'; "
            "else "
            "echo '  ⚠ classproject_optimized.csv not found in /tmp'; "
            "fi; "
            "sudo chown -R tr406:tr406 /mnt/data/uo/coincident/measures /mnt/data/uo/coincident/mappers; "
            "sudo chmod -R u+rwX,g+rX,o-rwx /mnt/data/uo/coincident/measures /mnt/data/uo/coincident/mappers; "
            "echo '[5/5] Validating deployment...'; "
            "test -d /mnt/data/uo/coincident/measures && echo '  ✓ measures directory exists' || echo '  ✗ measures directory missing'; "
            "test -d /mnt/data/uo/coincident/mappers && echo '  ✓ mappers directory exists' || echo '  ✗ mappers directory missing'; "
            "test -f /mnt/data/uo/coincident/mappers/base_optimized_workflow.osw && echo '  ✓ base_optimized_workflow.osw exists' || echo '  ✗ base_optimized_workflow.osw missing'; "
            "test -f /mnt/data/uo/coincident/classproject_optimized.csv && echo '  ✓ classproject_optimized.csv exists' || echo '  ✗ classproject_optimized.csv missing'; "
            "find /mnt/data/uo/coincident/measures -maxdepth 1 -type d -name 'SetWindowToWallRatio*' | wc -l | xargs -I {} echo '  ✓ Found {} directional WWR measures'; "
            "ls -1 /mnt/data/uo/coincident/mappers/*.rb 2>/dev/null | wc -l | xargs -I {} echo '  ✓ Found {} mapper files'; "
            "echo 'Deployment complete.'; "
        ),
    ),
    "deploy-coincident-optimized-flex-mappers": PatchSpec(
        uploads=[
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Hotel1Flex.rb",
                "/tmp/Hotel1Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Mall1Flex.rb",
                "/tmp/Mall1Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Office1Flex.rb",
                "/tmp/Office1Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Office2Flex.rb",
                "/tmp/Office2Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Office3Flex.rb",
                "/tmp/Office3Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Office4Flex.rb",
                "/tmp/Office4Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Office6Flex.rb",
                "/tmp/Office6Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Restaurant1Flex.rb",
                "/tmp/Restaurant1Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Restaurant2Flex.rb",
                "/tmp/Restaurant2Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Restaurant3Flex.rb",
                "/tmp/Restaurant3Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/Restaurant4Flex.rb",
                "/tmp/Restaurant4Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/mappers/School1Flex.rb",
                "/tmp/School1Flex.rb",
            ),
            UploadSpec(
                "/Users/nlong/working/urban-analysis/coincident/classproject_optimized_flex.csv",
                "/tmp/classproject_optimized_flex.csv",
            ),
        ],
        remote_command=(
            "set -e; "
            "echo '[1/4] Creating destination directory...'; "
            "sudo mkdir -p /mnt/data/uo/coincident/mappers; "
            "echo '[2/4] Copying Flex mapper files...'; "
            "for mapper in Hotel1Flex.rb Mall1Flex.rb Office1Flex.rb Office2Flex.rb Office3Flex.rb Office4Flex.rb Office6Flex.rb "
            "Restaurant1Flex.rb Restaurant2Flex.rb Restaurant3Flex.rb Restaurant4Flex.rb School1Flex.rb; do "
            'if [ -f "/tmp/$mapper" ]; then '
            'sudo cp "/tmp/$mapper" /mnt/data/uo/coincident/mappers/; '
            'echo "  copied $mapper"; '
            "else "
            'echo "  missing /tmp/$mapper"; '
            "fi; "
            "done; "
            "echo '[3/4] Copying optimized flex scenario CSV...'; "
            "if [ -f /tmp/classproject_optimized_flex.csv ]; then "
            "sudo cp /tmp/classproject_optimized_flex.csv /mnt/data/uo/coincident/classproject_optimized_flex.csv; "
            "echo '  copied classproject_optimized_flex.csv'; "
            "else "
            "echo '  missing /tmp/classproject_optimized_flex.csv'; "
            "fi; "
            "echo '[4/4] Fixing permissions and validating...'; "
            "sudo chown -R tr406:tr406 /mnt/data/uo/coincident/mappers /mnt/data/uo/coincident/classproject_optimized_flex.csv 2>/dev/null || true; "
            "sudo chmod -R u+rwX,g+rX,o-rwx /mnt/data/uo/coincident/mappers; "
            "sudo chmod u+rw,g+r,o-rwx /mnt/data/uo/coincident/classproject_optimized_flex.csv 2>/dev/null || true; "
            "test -f /mnt/data/uo/coincident/classproject_optimized_flex.csv && echo '  ok classproject_optimized_flex.csv' || echo '  missing classproject_optimized_flex.csv'; "
            "ls -1 /mnt/data/uo/coincident/mappers/*Flex.rb 2>/dev/null | wc -l | xargs -I {} echo '  found {} Flex mapper files'; "
            "echo 'Flex mapper deployment complete.'; "
        ),
    ),
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

    def run_all(
        self, remote_command: str, uploads: list[UploadSpec] | None = None
    ) -> list[RemoteResult]:
        results: list[RemoteResult] = []
        uploads = uploads or []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.workers
        ) as executor:
            futures = [
                executor.submit(self.run_one, vm, remote_command, uploads)
                for vm in self.vms
            ]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                self.print_result(result)
                results.append(result)

        passed = sum(result.ok for result in results)
        failed = len(results) - passed
        print(f"\nSummary: {passed} OK, {failed} failed")
        return results

    def run_one(
        self,
        vm: VM,
        remote_command: str,
        uploads: list[UploadSpec] | None = None,
    ) -> RemoteResult:
        target = f"{self.ssh_user}@{vm.ip}"
        ssh_options = [
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
            ssh_options.extend(["-i", self.key_file])

        uploads = uploads or []
        for upload in uploads:
            scp_command = [
                "scp",
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
                scp_command.extend(["-i", self.key_file])
            scp_command.extend([upload.local_path, f"{target}:{upload.remote_path}"])

            scp_result = subprocess.run(
                scp_command,
                capture_output=True,
                text=True,
                timeout=self.timeout + 5,
                check=False,
            )

            if scp_result.returncode != 0:
                message = (scp_result.stderr or scp_result.stdout).strip().splitlines()
                return RemoteResult(
                    vm,
                    False,
                    message[-1] if message else f"scp exited {scp_result.returncode}",
                )

        command = ssh_options + [target, remote_command]

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
                if isinstance(command, PatchSpec):
                    uploads = ", ".join(
                        f"{upload.local_path} -> {upload.remote_path}"
                        for upload in command.uploads
                    )
                    print(f"  {name}: upload [{uploads}] then {command.remote_command}")
                else:
                    print(f"  {name}: {command}")
            print("\nRun a patch with:")
            print("  python3 vm_management/verify_ssh_access.py patch <patch-name>")
            return 0
        selected_patch = PATCHES[args.name]
        if isinstance(selected_patch, PatchSpec):
            results = runner.run_all(
                selected_patch.remote_command,
                selected_patch.uploads,
            )
        else:
            results = runner.run_all(selected_patch)
    elif args.action == "run":
        results = runner.run_all(args.command)
    else:
        parser.error(f"unknown action: {args.action}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
