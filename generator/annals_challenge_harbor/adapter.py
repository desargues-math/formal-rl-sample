"""Generate a mixed textbook/research Harbor sample from pinned statement inputs.

    python -m annals_challenge_harbor.adapter --source /path/to/lean-eval --out ..

Without --source, use the checked-in sources/lean-eval subset. Regeneration is
offline: source bytes are verified against its provenance manifest. This module
does not fetch, attempt, or assess proofs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from string import Template
import tempfile

from .challenges import (
    ANNALS_COMMIT, ANNALS_REPOSITORY, Challenge, LEAN_TOOLCHAIN, MATHLIB_COMMIT,
    PROVENANCE_FILENAME, SOURCE_COMMIT, SOURCE_REPOSITORY, STARTER_FILES,
    load_challenges, sha256_file, verify_source,
)

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent.parent
IMAGE_DIR = PKG.parent / "image"
TEMPLATES = PKG / "templates"
DATASET_NAME = "annals-math-rl"
DATASET_VERSION = "1.0"
GRADE_TIMEOUT_SEC = 3 * 3600
VERIFIER_TIMEOUT_SEC = GRADE_TIMEOUT_SEC + 15 * 60
AGENT_TIMEOUT_SEC = 4 * 3600
SOURCE_PACKAGE_FILES = (
    "Challenge.lean", "ChallengeDeps.lean", "Solution.lean", *STARTER_FILES,
    "config.json", "holes.json", "lakefile.toml", "lean-toolchain", "README.md", "WorkspaceTest.lean",
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_list(values: list[str]) -> str:
    return "[" + ", ".join(toml_str(value) for value in values) + "]"


def selected_source_files(source: Path, challenges: list[Challenge]) -> list[Path]:
    paths: list[Path] = []
    for name in ("LICENSE", "README.md", "SECURITY.md", "lean-toolchain", "solution-dependencies.json"):
        path = source / name
        if path.is_file():
            paths.append(path)
    for challenge in challenges:
        paths.append(challenge.manifest_path)
        paths.extend(challenge.source_dir / name for name in SOURCE_PACKAGE_FILES
                     if (challenge.source_dir / name).is_file())
    return sorted(paths, key=lambda path: path.relative_to(source).as_posix())


def vendor_sources(source: Path, target: Path, challenges: list[Challenge]) -> None:
    """Keep original inputs, including upstream configs with unused lean-pool.

Only the runtime package changes its dependency access. The source copy remains
an exact record of the selected upstream files.
"""
    source = source.resolve()
    target = target.resolve()
    if source == target:
        verify_source(target)
        return
    files = selected_source_files(source, challenges)
    hashes = {path.relative_to(source).as_posix(): sha256_file(path) for path in files}
    if target.exists():
        verify_source(target)
        old = json.loads((target / PROVENANCE_FILENAME).read_text(encoding="utf-8"))
        if old["files"] != hashes:
            raise ValueError("Selected upstream bytes differ from the existing pinned source subset")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".annals-source-", dir=target.parent) as temporary:
        staged = Path(temporary) / "lean-eval"
        staged.mkdir()
        for path in files:
            relative = path.relative_to(source)
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        write_json(staged / PROVENANCE_FILENAME, {
            "repository": SOURCE_REPOSITORY,
            "revision": SOURCE_COMMIT,
            "selection": "Every manifest tagged annals and its committed generated workspace; no status filtering",
            "annals_repository": ANNALS_REPOSITORY,
            "annals_revision": ANNALS_COMMIT,
            "files": hashes,
        })
        staged.rename(target)


def task_metadata(challenge: Challenge) -> dict:
    return {
        "id": challenge.id,
        "title": challenge.title,
        "statement_revision": challenge.metadata["statement_revision"],
        "upstream_status": challenge.status,
        "upstream_visible": challenge.metadata["visible"],
        "theorem_names": challenge.theorem_names,
        "definition_names": challenge.definition_names,
        "permitted_axioms": list(challenge.config["permitted_axioms"]),
        "challenge_module": "Challenge",
        "solution_module": "Solution",
        "enable_nanoda": False,
        "grade_timeout_sec": GRADE_TIMEOUT_SEC,
        "holes": [{"name": h["name"], "kind": h["kind"]} for h in challenge.holes],
        "source_commit": challenge.source_revision,
        "source_repository": challenge.source_repository,
        "source_family": challenge.metadata.get("source_family", "annals-challenge"),
        "difficulty": challenge.difficulty,
        "source_sha256": challenge.source_hashes(),
    }


def stage_image_challenges(challenges: list[Challenge], image_dir: Path) -> None:
    """Populate the one shared image before copying it into any Harbor task."""
    with tempfile.TemporaryDirectory(prefix=".annals-challenges-", dir=image_dir) as temporary:
        staged = Path(temporary) / "challenges"
        staged.mkdir()
        for challenge in challenges:
            destination = staged / challenge.id
            destination.mkdir()
            for name in (*challenge.trusted_files, *STARTER_FILES, "config.json", "holes.json"):
                path = destination / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(challenge.source_dir / name, path)
            write_json(destination / "task.json", task_metadata(challenge))
        current = image_dir / "challenges"
        if current.exists():
            shutil.rmtree(current)
        staged.rename(current)


def instruction(challenge: Challenge) -> str:
    return Template((TEMPLATES / "instruction.md").read_text(encoding="utf-8")).substitute(
        title=challenge.title,
        task_id=challenge.id,
        holes="\n".join(f"- `{h['name']}` ({h['kind']})" for h in challenge.holes),
        source=challenge.metadata.get("source", ""),
        leaderboard_url=challenge.leaderboard_url,
    )


def task_toml(challenge: Challenge) -> str:
    return f'''schema_version = "1.4"

[task]
name = "{DATASET_NAME}/{challenge.id}"
version = "1.0.0"
description = {toml_str(f"Prove the supplied statement: {challenge.title}; {len(challenge.holes)} theorem target.")}
keywords = {toml_list(["lean4", "mathlib", "theorem-proving", challenge.metadata.get("source_family", "annals-challenge"), challenge.difficulty])}

[metadata]
source = {toml_str(challenge.source_repository)}
source_revision = {toml_str(challenge.source_revision)}
source_family = {toml_str(challenge.metadata.get("source_family", "annals-challenge"))}
challenge = {toml_str(challenge.id)}
paper_title = {toml_str(challenge.title)}
statement_revision = {challenge.metadata['statement_revision']}
upstream_status = {toml_str(challenge.status)}
upstream_visible = {str(challenge.metadata['visible']).lower()}
leaderboard_url = {toml_str(challenge.leaderboard_url)}
theorems = {toml_list(challenge.theorem_names)}
definition_holes = {toml_list(challenge.definition_names)}
hole_count = {len(challenge.holes)}
difficulty = {toml_str(challenge.difficulty)}
library_policy = "mathlib-only"

[agent]
timeout_sec = {AGENT_TIMEOUT_SEC}
network_mode = "no-network"

[environment]
build_timeout_sec = 5400
cpus = 4
memory_mb = 8192
storage_mb = 10240
workdir = "/workspace"
env = {{ LEAN_NUM_THREADS = "3" }}

[verifier]
timeout_sec = {VERIFIER_TIMEOUT_SEC}
environment_mode = "separate"
network_mode = "no-network"

[[verifier.collect]]
command = "python3 /opt/annals-challenge/pack_submission.py"
timeout_sec = 300
'''


def manifest_entry(challenge: Challenge) -> dict:
    return {
        "task": challenge.id,
        "path": f"tasks/{challenge.id}",
        "title": challenge.title,
        "source_family": challenge.metadata.get("source_family", "annals-challenge"),
        "source_repository": challenge.source_repository,
        "source_revision": challenge.source_revision,
        "difficulty": challenge.difficulty,
        "difficulty_basis": challenge.metadata.get("difficulty_basis", "Research mathematics; qualitative level, not empirically calibrated."),
        "source_module": challenge.metadata["module"],
        "statement_revision": challenge.metadata["statement_revision"],
        "upstream_status": challenge.status,
        "upstream_visible": challenge.metadata["visible"],
        "source": challenge.metadata.get("source", ""),
        "submitter": challenge.metadata.get("submitter", ""),
        "upstream_notes": challenge.metadata.get("notes", ""),
        "leaderboard_url": challenge.leaderboard_url,
        "theorems": challenge.theorem_names,
        "definition_holes": challenge.definition_names,
        "hole_names": [h["name"] for h in challenge.holes],
        "hole_kinds": [h["kind"] for h in challenge.holes],
        "hole_count": len(challenge.holes),
        "has_challenge_deps": "ChallengeDeps.lean" in challenge.trusted_files,
        "grade_timeout_sec": GRADE_TIMEOUT_SEC,
        "source_sha256": challenge.source_hashes(),
    }


def write_task(challenge: Challenge, out: Path, image_dir: Path) -> dict:
    directory = out / "tasks" / challenge.id
    if directory.exists():
        shutil.rmtree(directory)
    tests = directory / "tests"
    tests.mkdir(parents=True)
    shutil.copytree(image_dir, directory / "environment",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".annals-*"))
    (directory / "instruction.md").write_text(instruction(challenge), encoding="utf-8")
    (directory / "task.toml").write_text(task_toml(challenge), encoding="utf-8")
    for name in (*challenge.trusted_files, "config.json", "holes.json"):
        shutil.copyfile(challenge.source_dir / name, tests / name)
    write_json(tests / "task.json", task_metadata(challenge))
    for name in ("grade.py", "test.sh"):
        shutil.copyfile(TEMPLATES / "tests" / name, tests / name)
    (tests / "test.sh").chmod(0o755)
    return manifest_entry(challenge)


def image_digest(image_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(image_dir.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.name.endswith(".pyc") or path.name == ".DS_Store":
            continue
        digest.update(path.relative_to(image_dir).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def write_dataset_files(out: Path, challenges: list[Challenge], entries: list[dict], shared_image_hash: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    write_json(out / "registry.json", [{
        "name": DATASET_NAME,
        "version": DATASET_VERSION,
        "description": "Two Lean theorem-proving tasks spanning textbook algebra and research mathematics, with separate Comparator verification in Harbor.",
        "tasks": [{"name": entry["task"], "path": entry["path"]} for entry in entries],
    }])
    write_json(out / "manifest.json", {
        "dataset": DATASET_NAME,
        "version": DATASET_VERSION,
        "source": "AnnalsChallenge and Lean-GAP",
        "source_revisions": {entry["source_family"]: entry["source_revision"] for entry in entries},
        "annals_commit": ANNALS_COMMIT,
        "lean_toolchain": LEAN_TOOLCHAIN,
        "mathlib_commit": MATHLIB_COMMIT,
        "library_policy": "mathlib-only",
        "image_sha256": shared_image_hash,
        "task_count": len(entries),
        "hole_count": sum(len(challenge.holes) for challenge in challenges),
        "tasks": entries,
    })
    parquet_entries = [{**entry, "source_sha256": json.dumps(entry["source_sha256"], sort_keys=True)}
                       for entry in entries]
    pq.write_table(pa.Table.from_pylist(parquet_entries), out / "manifest.parquet", compression="zstd")
    card = Template((TEMPLATES / "dataset_README.md").read_text(encoding="utf-8")).substitute(
        source_commit=SOURCE_COMMIT,
        annals_commit=ANNALS_COMMIT,
        lean_toolchain=LEAN_TOOLCHAIN,
        mathlib_commit=MATHLIB_COMMIT,
        task_count=len(entries),
        hole_count=sum(len(challenge.holes) for challenge in challenges),
    )
    # Preserve the dataset card supplied with this public subset.
    if (ROOT / "README.md").is_file():
        card = (ROOT / "README.md").read_text(encoding="utf-8")
    (out / "README.md").write_text(card, encoding="utf-8")


def generate(source: Path, out: Path, *, image_dir: Path = IMAGE_DIR) -> list[dict]:
    """Generate a complete release. No subset/status/accepted-proof filtering."""
    source, out, image_dir = source.resolve(), out.resolve(), image_dir.resolve()
    challenges = load_challenges(source)
    # Fail before modifying outputs if a build dependency or template is missing.
    import pyarrow  # noqa: F401
    for path in (image_dir / "Dockerfile", image_dir / "lake-manifest.json",
                 TEMPLATES / "tests" / "grade.py", TEMPLATES / "tests" / "test.sh",
                 TEMPLATES / "instruction.md", TEMPLATES / "dataset_README.md"):
        if not path.is_file():
            raise ValueError(f"Missing generator input: {path}")
    tasks_dir = out / "tasks"
    if tasks_dir.exists():
        unexpected = {p.name for p in tasks_dir.iterdir() if p.is_dir()} - {c.id for c in challenges}
        if unexpected:
            raise ValueError(f"Refusing to remove unexpected task directories: {sorted(unexpected)}")
    out.mkdir(parents=True, exist_ok=True)
    vendor_sources(source, out / "sources" / "lean-eval",
                   [c for c in challenges if c.id.startswith("annals_")])
    extra_source = next(c for c in challenges if c.id.startswith("lean_gap_")).source_dir.parents[1]
    extra_target = out / "sources/lean-gap"
    if extra_target.resolve() != extra_source.resolve():
        shutil.copytree(extra_source, extra_target, dirs_exist_ok=True)
    stage_image_challenges(challenges, image_dir)
    shared_image_hash = image_digest(image_dir)
    entries = [write_task(challenge, out, image_dir) for challenge in challenges]
    write_dataset_files(out, challenges, entries, shared_image_hash)
    if out != ROOT:
        # --out produces a self-contained uploadable release, including the
        # editable generator, image recipe, offline sources and attribution.
        shutil.copytree(ROOT / "generator", out / "generator", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache",
                                                     "*.egg-info", ".DS_Store", ".annals-*"))
        for path in (ROOT / "NOTICE", ROOT / "sources.lock.json", ROOT / ".gitignore",
                     ROOT / "sample-checks.json", ROOT / "packaging-checks.json", ROOT / "runtime-checks.json",
                     *sorted(ROOT.glob("LICENSE*"))):
            if path.is_file():
                shutil.copyfile(path, out / path.name)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=ROOT / "sources" / "lean-eval",
                        help="Pinned LeanEval checkout/archive; defaults to the vendored offline subset")
    parser.add_argument("--out", type=Path, default=ROOT, help="Dataset root (default: this repository)")
    args = parser.parse_args()
    try:
        entries = generate(args.source, args.out)
    except (ValueError, OSError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Wrote {len(entries)} tasks with {sum(entry['hole_count'] for entry in entries)} holes to {args.out / 'tasks'}")


if __name__ == "__main__":
    main()
