"""Release invariants: membership, source preservation, and runnable packaging."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from annals_challenge_harbor.challenges import load_challenges, STARTER_FILES

ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / 'generator/image'


@pytest.fixture(scope='module')
def challenges():
    return load_challenges(ROOT / 'sources/lean-eval')


def digest_tree(directory: Path) -> dict[str, str]:
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def test_full_inventory_and_holes(challenges):
    ids = {c.id for c in challenges}
    assert ids == {'annals_absolute_profinite_rigidity', 'lean_gap_df_10_2_1'}
    assert 'annals_absolute_profinite_rigidity' in ids
    assert sum(len(c.holes) for c in challenges) == 2
    assert sum(len(c.holes) > 1 for c in challenges) == 0
    assert {p.name for p in (ROOT / 'tasks').iterdir() if p.is_dir()} == ids
    registry = json.loads((ROOT / 'registry.json').read_text())
    assert len(registry) == 1
    assert registry[0]['name'] == 'annals-math-rl'
    assert registry[0]['version'] == '1.0'
    assert {entry['path'] for entry in registry[0]['tasks']} == {f'tasks/{i}' for i in ids}


def test_mathlib_only_configuration():
    manifest = json.loads((IMAGE / 'lake-manifest.json').read_text())
    names = {p['name'] for p in manifest['packages']}
    assert 'mathlib' in names
    assert not names & {'lean-pool', '«lean-pool»', 'TauCeti', 'lean-eval-generator'}
    mathlib = next(p for p in manifest['packages'] if p['name'] == 'mathlib')
    assert mathlib['rev'] == '5e0c4e5239cb0a2d86d68a884bf52cfd963fce22'
    assert (IMAGE / 'lean-toolchain').read_text().strip() == 'leanprover/lean4:v4.35.0-rc3'
    project = (IMAGE / 'lakefile.lean').read_text()
    assert 'require mathlib' in project
    assert 'lean-pool' not in project and 'TauCeti' not in project


def test_preserved_mathematical_files_and_target_configs(challenges):
    for challenge in challenges:
        task = ROOT / 'tasks' / challenge.id
        assert not (task / 'solution').exists()
        for name in challenge.trusted_files:
            assert (task / 'tests' / name).read_bytes() == (challenge.source_dir / name).read_bytes()
        config = json.loads((task / 'tests/task.json').read_text())
        for key in ('theorem_names', 'definition_names', 'permitted_axioms'):
            assert config[key] == challenge.config.get(key, [])
        assert config['grade_timeout_sec'] == 10800
        starter = IMAGE / 'challenges' / challenge.id
        for name in (*challenge.trusted_files, *STARTER_FILES, 'config.json', 'holes.json'):
            assert (starter / name).read_bytes() == (challenge.source_dir / name).read_bytes()
        assert not (starter / 'lakefile.toml').exists()
        assert not (starter / 'WorkspaceTest.lean').exists()
    textbook = ROOT / 'tasks/lean_gap_df_10_2_1/tests'
    assert not (textbook / 'ChallengeDeps.lean').exists()
    assert (textbook / 'Challenge.lean').read_bytes() == (
        ROOT / 'sources/lean-gap/Formal/DF_10/DF_10_2.lean').read_bytes()


def test_identical_images_and_resource_contract(challenges):
    expected = digest_tree(IMAGE)
    for challenge in challenges:
        task = ROOT / 'tasks' / challenge.id
        assert digest_tree(task / 'environment') == expected
        config = tomllib.loads((task / 'task.toml').read_text())
        assert config['schema_version'] == '1.4'
        assert config['agent']['timeout_sec'] == 14400
        assert config['agent']['network_mode'] == 'no-network'
        assert config['verifier']['environment_mode'] == 'separate'
        assert config['verifier']['timeout_sec'] == 11700
        assert config['verifier']['network_mode'] == 'no-network'
        assert config['environment']['memory_mb'] == 8192
        assert config['environment']['cpus'] == 4
        assert config['environment']['storage_mb'] == 10240


def test_parquet_and_harbor_schema(challenges):
    import pyarrow.parquet as pq
    table = pq.read_table(ROOT / 'manifest.parquet')
    assert table.num_rows == 2
    # The actual supported runner parses every generated task, rather than a
    # handwritten subset of its TOML schema.
    pytest.importorskip('harbor')
    from harbor.models.task.task import Task
    for challenge in challenges:
        task = Task(ROOT / 'tasks' / challenge.id)
        assert task.name == f'annals-math-rl/{challenge.id}'
        assert 'Submission.lean' in task.instruction


def test_offline_regeneration_is_deterministic(tmp_path):
    destination = tmp_path / 'regenerated'
    subprocess.run([sys.executable, '-m', 'annals_challenge_harbor.adapter',
                    '--source', str(ROOT / 'sources/lean-eval'), '--out', str(destination)],
                   cwd=ROOT / 'generator', check=True, capture_output=True, text=True)
    assert digest_tree(destination / 'tasks') == digest_tree(ROOT / 'tasks')
    for name in ('registry.json', 'manifest.json', 'manifest.parquet', 'README.md',
                 'NOTICE', 'LICENSE', 'RIGHTS.md'):
        assert (destination / name).read_bytes() == (ROOT / name).read_bytes(), name


@pytest.mark.parametrize('task_id', ['annals_absolute_profinite_rigidity', 'lean_gap_df_10_2_1'])
def test_initializer_preserves_existing_submission(tmp_path, task_id):
    spec = importlib.util.spec_from_file_location('annals_starter', IMAGE / 'start_task.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lean_env = tmp_path / 'lean-env'
    lean_env.mkdir()
    (lean_env / '.lake/packages').mkdir(parents=True)
    for name in module.PROJECT_FILES:
        (lean_env / name).write_bytes((IMAGE / name).read_bytes())
    workspace = tmp_path / 'workspace'
    args = dict(workspace=workspace, tasks=IMAGE / 'challenges', lean_env=lean_env)
    assert module.start_task(task_id, **args)
    submission = workspace / 'Submission.lean'
    submission.write_text('-- user progress\n')
    assert module.start_task(task_id, **args) is False
    assert submission.read_text() == '-- user progress\n'
    with pytest.raises(ValueError):
        other_id = 'lean_gap_df_10_2_1' if task_id.startswith('annals_') else 'annals_absolute_profinite_rigidity'
        module.start_task(other_id, **args)
