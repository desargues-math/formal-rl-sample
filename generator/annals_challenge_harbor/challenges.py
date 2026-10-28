"""Read the pinned LeanEval Annals inventory without rewriting Lean source.

The manifest's ``annals`` tag determines membership, regardless of status or
leaderboard visibility. A paper is one task, including all of its definition,
instance, and theorem holes.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib

SOURCE_REPOSITORY = "https://github.com/leanprover/lean-eval"
SOURCE_COMMIT = "38361be884302c7edce1908c4aef8296eb2cb27e"
ANNALS_REPOSITORY = "https://github.com/ImperialCollegeLondon/AnnalsChallenge"
ANNALS_COMMIT = "e32eb1411db0d700ca874dd695aea92f78699db8"
LEAN_TOOLCHAIN = "leanprover/lean4:v4.35.0-rc3"
MATHLIB_COMMIT = "5e0c4e5239cb0a2d86d68a884bf52cfd963fce22"
SELECTED_TASK_IDS = ('annals_absolute_profinite_rigidity',)
EXPECTED_TASKS = 2
EXPECTED_HOLES = 2
EXPECTED_DEPENDENCY_MODULES = 1
PERMITTED_AXIOMS = ("propext", "Quot.sound", "Classical.choice")
TRUSTED_LEAN_FILES = ("Challenge.lean", "Solution.lean", "ChallengeDeps.lean")
STARTER_FILES = ("Submission.lean", "Submission/Helpers.lean")
PROVENANCE_FILENAME = "provenance.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Challenge:
    id: str
    title: str
    metadata: dict
    holes: tuple[dict, ...]
    config: dict
    source_dir: Path
    manifest_path: Path

    @property
    def theorem_names(self) -> list[str]:
        return list(self.config.get("theorem_names", []))

    @property
    def definition_names(self) -> list[str]:
        return list(self.config.get("definition_names", []))

    @property
    def trusted_files(self) -> tuple[str, ...]:
        return tuple(name for name in TRUSTED_LEAN_FILES if (self.source_dir / name).is_file())

    @property
    def status(self) -> str:
        return self.metadata["status"]

    @property
    def leaderboard_url(self) -> str:
        return self.metadata.get("leaderboard_url", f"https://lean-lang.org/eval/problems/{self.id}/")

    @property
    def source_repository(self) -> str:
        return self.metadata.get("source_repository", SOURCE_REPOSITORY)

    @property
    def source_revision(self) -> str:
        return self.metadata.get("source_revision", SOURCE_COMMIT)

    @property
    def difficulty(self) -> str:
        return self.metadata.get("difficulty", "research")

    def source_hashes(self) -> dict[str, str]:
        """Hashes used to verify preservation of trusted and editable starters."""
        names = (*self.trusted_files, *STARTER_FILES, "config.json", "holes.json")
        return {name: sha256_file(self.source_dir / name) for name in sorted(names)}


def verify_source(source: Path) -> None:
    """Check a vendored snapshot's hashes, or a Git checkout's revision.

An unpacked upstream release can be supplied for initial vendoring. Its selected
bytes are then recorded in provenance.json and checked on offline regeneration.
"""
    provenance_path = source / PROVENANCE_FILENAME
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("repository") != SOURCE_REPOSITORY or provenance.get("revision") != SOURCE_COMMIT:
            raise ValueError("Vendored source provenance does not match the pinned LeanEval revision")
        files = provenance.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("Vendored source provenance has no file hashes")
        for name, expected in sorted(files.items()):
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe provenance path: {name}")
            path = source / relative
            if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"Vendored source hash mismatch: {name}")
        actual = {p.relative_to(source).as_posix() for p in source.rglob("*")
                  if p.is_file() and p.name != PROVENANCE_FILENAME}
        if actual != set(files):
            raise ValueError("Vendored source inventory does not match provenance.json")
    elif (source / ".git").exists():
        commit = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        if commit != SOURCE_COMMIT:
            raise ValueError(f"Expected LeanEval {SOURCE_COMMIT}; found {commit}")
        changed = subprocess.check_output(
            ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"], text=True
        ).strip()
        if changed:
            raise ValueError("The upstream Git checkout has tracked changes; use the pinned clean snapshot")


def load_challenges(source: Path, *, check_inventory: bool = True) -> list[Challenge]:
    source = source.resolve()
    verify_source(source)
    directory = source / "manifests" / "problems"
    if not directory.is_dir():
        raise ValueError(f"Missing LeanEval manifests directory: {directory}")
    challenges: list[Challenge] = []
    for path in sorted(directory.glob("*.toml")):
        metadata = tomllib.loads(path.read_text(encoding="utf-8"))
        if "annals" not in metadata.get("tags", []):
            continue
        problem_id = metadata["id"]
        if problem_id not in SELECTED_TASK_IDS:
            continue
        if path.stem != problem_id or not re.fullmatch(r"annals_[a-z0-9_]+", problem_id):
            raise ValueError(f"Invalid Annals problem identifier in {path}")
        package = source / "generated" / problem_id
        for name in ("Challenge.lean", "Solution.lean", *STARTER_FILES,
                     "holes.json", "config.json", "lakefile.toml", "lean-toolchain"):
            if not (package / name).is_file() or (package / name).is_symlink():
                raise ValueError(f"Missing or unsafe generated source: {package / name}")
        if (package / "lean-toolchain").read_text().strip() != LEAN_TOOLCHAIN:
            raise ValueError(f"Unexpected Lean toolchain for {problem_id}")
        lakefile = tomllib.loads((package / "lakefile.toml").read_text(encoding="utf-8"))
        mathlib = [item for item in lakefile.get("require", []) if item.get("name") == "mathlib"]
        if len(mathlib) != 1 or mathlib[0].get("rev") != MATHLIB_COMMIT:
            raise ValueError(f"Unexpected Mathlib pin for {problem_id}")
        config = json.loads((package / "config.json").read_text(encoding="utf-8"))
        holes_doc = json.loads((package / "holes.json").read_text(encoding="utf-8"))
        holes = tuple(holes_doc["holes"])
        if holes_doc["id"] != problem_id or holes_doc["module"] != metadata["module"]:
            raise ValueError(f"Hole metadata does not match manifest: {problem_id}")
        if [h["basename"] for h in holes] != metadata["holes"]:
            raise ValueError(f"Hole ordering does not match manifest: {problem_id}")
        names = [h["name"] for h in holes]
        targets = config.get("theorem_names", []) + config.get("definition_names", [])
        # Upstream singleton configs use a basename; multi-hole configs use
        # qualified names. Preserve that spelling and resolve it only for this
        # inventory check, using Comparator's unambiguous suffix convention.
        resolved = []
        for target in targets:
            matches = [name for name in names if name == target or name.endswith("." + target)]
            if len(matches) != 1:
                raise ValueError(f"Ambiguous or missing Comparator target {target}: {problem_id}")
            resolved.append(matches[0])
        if len(set(names)) != len(names) or len(set(resolved)) != len(resolved) or set(names) != set(resolved):
            raise ValueError(f"Comparator targets do not match the declared holes: {problem_id}")
        if config.get("challenge_module") != "Challenge" or config.get("solution_module") != "Solution":
            raise ValueError(f"Unexpected Comparator module names: {problem_id}")
        if config.get("enable_nanoda") is not False:
            raise ValueError(f"Unexpected independent-kernel setting: {problem_id}")
        if tuple(config.get("permitted_axioms", [])) != PERMITTED_AXIOMS:
            raise ValueError(f"Unexpected permitted axioms: {problem_id}")
        challenges.append(Challenge(problem_id, metadata["title"], metadata, holes, config, package, path))
    from .lean_gap import load_lean_gap
    extra_source = source.parent / "lean-gap"
    if not extra_source.is_dir():
        extra_source = Path(__file__).resolve().parents[2] / "sources/lean-gap"
    challenges.append(load_lean_gap(extra_source))
    if check_inventory:
        counts = (len(challenges), sum(len(c.holes) for c in challenges),
                  sum("ChallengeDeps.lean" in c.trusted_files for c in challenges))
        expected = (EXPECTED_TASKS, EXPECTED_HOLES, EXPECTED_DEPENDENCY_MODULES)
        if counts != expected:
            raise ValueError(f"Expected tasks/holes/dependency modules {expected}; found {counts}")
    return challenges
