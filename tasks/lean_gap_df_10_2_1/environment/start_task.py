#!/usr/bin/env python3
"""Initialize one generated Annals task without overwriting an existing proof.

    python3 /opt/annals-challenge/start_task.py annals_<problem_id>

The immutable task copy supplies the starter and trusted bridge. The image's
canonical Lake project supplies the Mathlib-only dependency configuration.
Only Submission.lean and Submission/**.lean are later collected for grading.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

TASKS = Path("/opt/annals-challenge/tasks")
LEAN_ENV = Path("/opt/lean-env")
WORKSPACE = Path("/workspace")
TASK_ID = re.compile(r"(?:annals|lean_gap)_[a-z0-9_]+\Z")
PROJECT_FILES = ("lakefile.lean", "lake-manifest.json", "lean-toolchain")
REQUIRED_FILES = ("Challenge.lean", "Solution.lean", "Submission.lean")
OPTIONAL_FILES = ("ChallengeDeps.lean", "config.json", "holes.json", "README.md")


def start_task(task_id: str, workspace: Path = WORKSPACE,
               tasks: Path = TASKS, lean_env: Path = LEAN_ENV) -> bool:
    """Return True when initialized, False for an already initialized task."""
    if not TASK_ID.fullmatch(task_id):
        raise ValueError(f"invalid task id: {task_id!r}")
    source = tasks / task_id
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"unknown task: {task_id}")
    for name in REQUIRED_FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"task is missing its regular {name} file")
    for name in PROJECT_FILES:
        if not (lean_env / name).is_file():
            raise ValueError(f"image is missing {lean_env / name}")
    packages = lean_env / ".lake" / "packages"
    if not packages.is_dir():
        raise ValueError(f"image is missing {packages}")

    marker = workspace / ".annals-task"
    if marker.exists():
        current = marker.read_text().strip()
        if current == task_id and (workspace / "Submission.lean").is_file():
            return False
        raise ValueError(f"workspace is already initialized for {current!r}")
    if any((workspace / name).exists() or (workspace / name).is_symlink()
           for name in ("Submission.lean", "Submission", "lakefile.toml")):
        raise ValueError("workspace has an existing submission or Lake project; use a fresh workspace")

    files = [*REQUIRED_FILES, *(n for n in OPTIONAL_FILES if (source / n).is_file())]
    helper_dir = source / "Submission"
    if helper_dir.is_symlink():
        raise ValueError("task starter directory must not be a symlink")
    if helper_dir.is_dir():
        for path in sorted(helper_dir.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"task starter contains a symlink: {path.name}")
            if path.is_file():
                if path.suffix != ".lean":
                    raise ValueError(f"unexpected starter file: {path.name}")
                files.append(str(path.relative_to(source)))
    for name in files:
        if (source / name).is_symlink():
            raise ValueError(f"task file must not be a symlink: {name}")

    workspace.mkdir(parents=True, exist_ok=True)
    lake = workspace / ".lake"
    if lake.is_symlink():
        raise ValueError("workspace .lake must not be a symlink")
    lake.mkdir(exist_ok=True)
    link = lake / "packages"
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or link.resolve() != packages.resolve():
            raise ValueError("workspace already has different Lake packages")
    else:
        link.symlink_to(packages.resolve(), target_is_directory=True)
    for name in PROJECT_FILES:
        shutil.copyfile(lean_env / name, workspace / name)
    for name in files:
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    marker.write_text(task_id + "\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    args = parser.parse_args()
    try:
        created = start_task(args.task_id)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot initialize task: {error}\n")
    print(f"{'Initialized' if created else 'Already initialized'} {args.task_id} in {WORKSPACE}")


if __name__ == "__main__":
    main()
