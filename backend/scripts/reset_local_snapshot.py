"""Recreate the mutable local snapshot working copy from its golden dump."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.snapshot.yml"
SNAPSHOT_VERIFIER = REPO_ROOT / "backend" / "scripts" / "verify_local_snapshot.py"


def _compose_command() -> list[str]:
    docker = shutil.which("docker")
    if docker is not None:
        probe = subprocess.run(
            [docker, "compose", "version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            return [docker, "compose"]
    legacy = shutil.which("docker-compose")
    if legacy is not None:
        return [legacy]
    raise RuntimeError("Docker Compose is required to reset the local snapshot")


def build_restore_command(
    *,
    container_name: str,
    backup_path: Path,
    database_name: str,
    database_user: str,
) -> list[str]:
    return [
        "docker",
        "exec",
        "-i",
        container_name,
        "pg_restore",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        "--dbname",
        database_name,
        "--username",
        database_user,
        str(backup_path),
    ]


def _compose(*args: str, compose_command: list[str], check: bool = True, capture_output: bool = False):
    return subprocess.run(
        [*compose_command, "-f", str(COMPOSE_FILE), *args],
        cwd=str(REPO_ROOT),
        check=check,
        capture_output=capture_output,
        text=True,
    )


def _wait_for_postgres(container_name: str, database_name: str, database_user: str) -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        probe = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "pg_isready",
                "-U",
                database_user,
                "-d",
                database_name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("working snapshot PostgreSQL did not become ready")


def reset_local_snapshot(
    *,
    database_url: str,
    backup_path: Path,
    volume_name: str,
) -> None:
    if not backup_path.is_file():
        raise FileNotFoundError(f"golden snapshot backup is missing: {backup_path}")
    parsed = urlsplit(database_url)
    database_name = parsed.path.lstrip("/")
    database_user = parsed.username or "aethria"
    if database_name != "aethria_prod_snapshot":
        raise ValueError("database URL must target aethria_prod_snapshot")

    compose_command = _compose_command()
    container_name = ""
    try:
        _compose("down", "--remove-orphans", compose_command=compose_command, check=False)
        volume_exists = subprocess.run(
            ["docker", "volume", "inspect", volume_name],
            capture_output=True,
            text=True,
            check=False,
        ).returncode == 0
        if volume_exists:
            subprocess.run(["docker", "volume", "rm", volume_name], check=True)
        subprocess.run(["docker", "volume", "create", volume_name], check=True)
        _compose("up", "-d", "postgres", compose_command=compose_command)

        container_probe = _compose(
            "ps",
            "-q",
            "postgres",
            compose_command=compose_command,
            capture_output=True,
        )
        container_name = container_probe.stdout.strip()
        if not container_name:
            raise RuntimeError("working snapshot PostgreSQL container was not created")
        _wait_for_postgres(container_name, database_name, database_user)

        container_backup_path = "/tmp/golden.dump"
        subprocess.run(
            ["docker", "cp", str(backup_path), f"{container_name}:{container_backup_path}"],
            check=True,
        )
        subprocess.run(
            build_restore_command(
                container_name=container_name,
                backup_path=Path(container_backup_path),
                database_name=database_name,
                database_user=database_user,
            ),
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(SNAPSHOT_VERIFIER),
                "--database-url",
                database_url,
            ],
            cwd=str(REPO_ROOT),
            check=True,
            env={**os.environ, "DATABASE_URL": database_url},
        )
    except Exception:
        if container_name:
            _compose("stop", "postgres", compose_command=compose_command, check=False)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--backup-path", required=True, type=Path)
    parser.add_argument("--volume-name", required=True)
    args = parser.parse_args(argv)
    try:
        reset_local_snapshot(
            database_url=args.database_url,
            backup_path=args.backup_path,
            volume_name=args.volume_name,
        )
    except Exception as exc:
        print(f"local_snapshot_reset_failed: {exc}", file=sys.stderr)
        return 1
    print("Local snapshot working copy restored and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
