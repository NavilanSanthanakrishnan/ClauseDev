#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path("/Users/navilan/Documents/ClauseAIProd")
SOURCE_DIR = REPO_ROOT / "clauseainaviprod"
TARGET_REPO = REPO_ROOT / "ClauseDev"
TARGET_DIR = TARGET_REPO / "clauseainaviprod"

EXCLUDES = {
    ".git",
    "node_modules",
    "frontend/node_modules",
    "frontend/dist",
    "backend/.venv",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tsbuildinfo",
    "vite.config.js",
    "vite.config.d.ts",
}


def is_excluded(relative_path: str) -> bool:
    normalized = relative_path.strip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    for pattern in EXCLUDES:
        if "/" in pattern and (normalized == pattern or normalized.startswith(f"{pattern}/")):
            return True
        if pattern in parts:
            return True
        if fnmatch.fnmatch(normalized, pattern):
            return True
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def copy_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)

    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source).as_posix()
        if is_excluded(relative):
            continue

        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    for path in sorted(target.rglob("*"), reverse=True):
        relative = path.relative_to(target).as_posix()
        if is_excluded(relative):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
            continue
        if (source / relative).exists():
            continue
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
        else:
            path.unlink()


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(TARGET_REPO), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync clauseainaviprod into the ClauseDev GitHub repo.")
    parser.add_argument("--commit", help="Commit message for the synced changes.")
    parser.add_argument("--push", action="store_true", help="Push after committing.")
    args = parser.parse_args()

    copy_tree(SOURCE_DIR, TARGET_DIR)
    print(f"Synced {SOURCE_DIR} -> {TARGET_DIR}")

    if args.commit:
        run_git("add", "clauseainaviprod")
        status = run_git("status", "--short")
        if not status:
            print("No git changes to commit.")
            return
        commit_output = run_git("commit", "-m", args.commit)
        print(commit_output)
        if args.push:
            push_output = run_git("push", "origin", "main")
            print(push_output)


if __name__ == "__main__":
    main()
