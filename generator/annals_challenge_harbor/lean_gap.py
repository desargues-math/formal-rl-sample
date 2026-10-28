"""Load the one supplied Lean-GAP statement and verify its packaged inputs."""
from __future__ import annotations

import json
from pathlib import Path

from .challenges import Challenge, PERMITTED_AXIOMS, STARTER_FILES, sha256_file

TASK_ID = "lean_gap_df_10_2_1"


def load_lean_gap(source: Path) -> Challenge:
    source = source.resolve()
    provenance = json.loads((source / "provenance.json").read_text())
    hashes = provenance["files"]
    actual = {p.relative_to(source).as_posix() for p in source.rglob("*")
              if p.is_file() and p.name != "provenance.json"}
    if actual != set(hashes):
        raise ValueError("Lean-GAP source inventory differs from provenance")
    for name, expected in hashes.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe Lean-GAP source path: {name}")
        path = source / relative
        if path.is_symlink() or sha256_file(path) != expected:
            raise ValueError(f"Lean-GAP source hash mismatch: {name}")
    metadata_path = source / "task.json"
    metadata = json.loads(metadata_path.read_text())
    if metadata["id"] != TASK_ID or provenance["selection"] != [TASK_ID]:
        raise ValueError("Unexpected Lean-GAP task selection")
    package = source / "generated" / TASK_ID
    for name in ("Challenge.lean", "Solution.lean", *STARTER_FILES, "config.json", "holes.json"):
        if not (package / name).is_file():
            raise ValueError(f"Missing Lean-GAP package file: {name}")
    original = source / provenance["original_file"]
    if original.read_bytes() != (package / "Challenge.lean").read_bytes():
        raise ValueError("Lean-GAP mathematical statement was changed")
    config = json.loads((package / "config.json").read_text())
    holes = json.loads((package / "holes.json").read_text())
    if (config.get("theorem_names") != ["DF_10_2_1"]
            or config.get("definition_names", [])
            or config.get("challenge_module") != "Challenge"
            or config.get("solution_module") != "Solution"
            or config.get("enable_nanoda") is not False
            or tuple(config.get("permitted_axioms", [])) != PERMITTED_AXIOMS
            or holes["id"] != TASK_ID
            or [h["name"] for h in holes["holes"]] != ["DF_10_2_1"]):
        raise ValueError("Unexpected Lean-GAP verification contract")
    return Challenge(TASK_ID, metadata["title"], metadata, tuple(holes["holes"]),
                     config, package, metadata_path)
