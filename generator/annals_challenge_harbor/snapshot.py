"""Build the shared Daytona snapshot from image/Dockerfile.

Harbor's auto-snapshot timeout is shorter than a Lean/Mathlib image build. Build
this once and pass --ek snapshot_template_name=<name> to Harbor. The name hashes
the complete build context, including every generated Annals task.

    python -m annals_challenge_harbor.snapshot [--print-name]
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

IMAGE_DIR = Path(__file__).parents[1] / "image"


def snapshot_name(image_dir: Path | None = None) -> str:
    image_dir = image_dir or IMAGE_DIR
    digest = hashlib.sha256()
    for path in sorted(image_dir.rglob("*")):
        relative = path.relative_to(image_dir)
        if any(p == "__pycache__" or (p.startswith(".") and p != ".dockerignore")
               for p in relative.parts):
            continue
        if path.name.endswith((".pyc", "~")):
            continue
        if path.is_symlink():
            raise ValueError(f"image context must not contain symlinks: {relative}")
        if path.is_file():
            digest.update(relative.as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return f"annals-challenge-lean-{digest.hexdigest()[:12]}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-name", action="store_true")
    args = parser.parse_args()
    name = snapshot_name()
    if args.print_name:
        print(name)
        return

    from daytona import CreateSnapshotParams, Daytona, Image, Resources

    client = Daytona()
    try:
        snapshot = client.snapshot.get(name)
    except Exception as error:
        # Only a genuinely absent snapshot should trigger a potentially costly
        # build; authentication/network failures must be surfaced to the caller.
        if getattr(error, "status_code", None) != 404 and getattr(error, "status", None) != 404:
            raise
    else:
        print(f"{name} already exists ({snapshot.state})")
        return
    image = Image.from_dockerfile(IMAGE_DIR / "Dockerfile")
    client.snapshot.create(
        CreateSnapshotParams(name=name, image=image, resources=Resources(cpu=4, memory=8, disk=10)),
        on_logs=lambda line: print(line, flush=True),
        timeout=3 * 3600,
    )
    print(f"created {name}")


if __name__ == "__main__":
    main()
