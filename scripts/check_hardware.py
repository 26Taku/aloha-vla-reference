#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import yaml


REFERENCE_COMMIT = "a4336933f34192a3daa7e9fb52674284bb5ae48e"

REFERENCE_PACKAGES = {
    "lerobot": "0.6.0",
    "lerobot-robot-trossen": "0.1.0",
    "lerobot-teleoperator-trossen": "0.1.0",
    "trossen-arm": "1.10.0",
    "trossen-slate": "0.0.3",
    "pyrealsense2": "2.56.5.9235",
}


def print_result(status: str, message: str) -> None:
    print(f"[{status}] {message}")


def ping(ip: str) -> bool:
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def nearest_existing_path(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight check for the lab ALOHA reference setup."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--trossen-dir", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    args = parser.parse_args()

    failures = 0
    warnings = 0

    config_path = args.config.resolve()
    trossen_dir = args.trossen_dir.resolve()
    data_root = args.data_root.resolve()

    print("=== ALOHA Preflight Check ===")
    print()

    # ------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------
    print("Configuration")

    if not config_path.is_file():
        print_result("FAIL", f"Config file not found: {config_path}")
        return 1

    try:
        cfg = yaml.safe_load(config_path.read_text())
        robot_cfg = cfg["robot"]
        teleop_cfg = cfg["teleop"]
        print_result("OK", str(config_path))
    except Exception as exc:
        print_result("FAIL", f"Could not parse configuration: {exc}")
        return 1

    print()

    # ------------------------------------------------------------
    # Reference software
    # ------------------------------------------------------------
    print("Software")

    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info[:2] == (3, 12):
        print_result("OK", f"Python {py_version}")
    else:
        print_result("WARN", f"Python {py_version}; reference uses Python 3.12.x")
        warnings += 1

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=trossen_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

        if commit == REFERENCE_COMMIT:
            print_result("OK", f"Trossen commit {commit[:12]}")
        else:
            print_result(
                "WARN",
                f"Trossen commit {commit[:12]} "
                f"(reference: {REFERENCE_COMMIT[:12]})",
            )
            warnings += 1
    except Exception as exc:
        print_result("FAIL", f"Could not determine Trossen git commit: {exc}")
        failures += 1

    for package, expected in REFERENCE_PACKAGES.items():
        try:
            actual = version(package)
            if actual == expected:
                print_result("OK", f"{package} {actual}")
            else:
                print_result(
                    "WARN",
                    f"{package} {actual} (reference: {expected})",
                )
                warnings += 1
        except PackageNotFoundError:
            print_result("FAIL", f"{package} is not installed")
            failures += 1

    print()

    # ------------------------------------------------------------
    # Arm network reachability
    # ------------------------------------------------------------
    print("Arms")

    arms = [
        ("Leader Right", str(teleop_cfg["right_arm_ip_address"])),
        ("Leader Left", str(teleop_cfg["left_arm_ip_address"])),
        ("Follower Right", str(robot_cfg["right_arm_ip_address"])),
        ("Follower Left", str(robot_cfg["left_arm_ip_address"])),
    ]

    for name, ip in arms:
        if ping(ip):
            print_result("OK", f"{name:<15} {ip}")
        else:
            print_result("FAIL", f"{name:<15} {ip} unreachable")
            failures += 1

    print()

    # ------------------------------------------------------------
    # RealSense cameras
    # ------------------------------------------------------------
    print("Cameras")

    try:
        import pyrealsense2 as rs

        context = rs.context()
        detected = {}

        for device in context.query_devices():
            serial = device.get_info(rs.camera_info.serial_number)

            name = (
                device.get_info(rs.camera_info.name)
                if device.supports(rs.camera_info.name)
                else "RealSense"
            )

            firmware = (
                device.get_info(rs.camera_info.firmware_version)
                if device.supports(rs.camera_info.firmware_version)
                else "unknown"
            )

            detected[str(serial)] = {
                "name": name,
                "firmware": firmware,
            }

        expected_cameras = robot_cfg.get("cameras", {})

        for camera_name, camera_cfg in expected_cameras.items():
            serial = str(camera_cfg["serial_number_or_name"])

            if serial in detected:
                info = detected[serial]
                print_result(
                    "OK",
                    f"{camera_name:<18} {serial} "
                    f"({info['name']}, FW {info['firmware']})",
                )
            else:
                print_result(
                    "FAIL",
                    f"{camera_name:<18} {serial} not detected",
                )
                failures += 1

        expected_serials = {
            str(camera["serial_number_or_name"])
            for camera in expected_cameras.values()
        }

        extra_serials = set(detected) - expected_serials
        for serial in sorted(extra_serials):
            info = detected[serial]
            print_result(
                "WARN",
                f"Unexpected RealSense {serial} ({info['name']})",
            )
            warnings += 1

    except Exception as exc:
        print_result("FAIL", f"RealSense enumeration failed: {exc}")
        failures += 1

    print()

    # ------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------
    print("Storage")

    if data_root.exists() and data_root.is_dir():
        if os.access(data_root, os.W_OK):
            print_result("OK", f"Writable: {data_root}")
        else:
            print_result("FAIL", f"Not writable: {data_root}")
            failures += 1
    else:
        print_result("FAIL", f"Data directory does not exist: {data_root}")
        failures += 1

    disk_path = nearest_existing_path(data_root)
    usage = shutil.disk_usage(disk_path)
    free_gib = usage.free / (1024 ** 3)
    print_result("OK", f"Free space: {free_gib:.1f} GiB on {disk_path}")

    print()
    print("Summary")

    if failures:
        print_result(
            "FAIL",
            f"{failures} failure(s), {warnings} warning(s). "
            "Do not start data collection yet.",
        )
        return 1

    if warnings:
        print_result(
            "WARN",
            f"No hardware failures, but {warnings} warning(s) found.",
        )
        return 0

    print_result("READY", "Reference ALOHA setup is ready for operation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
