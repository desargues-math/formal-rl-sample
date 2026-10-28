#!/usr/bin/env python3
"""Check starter builds, grading security and a real textbook reference proof.

Run from a host with Docker: python tests/smoke_runtime.py --image annals-challenge:local
The compilation phase leaves upstream placeholders intact. Reference and
synthetic proofs live in temporary workspaces, never in the agent starters.
This checks no Annals proof and measures no agent solving difficulty.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import time
import uuid

from annals_challenge_harbor.checks import release_input_digest

ROOT = Path(__file__).resolve().parents[2]
TOOL_SHADOW = r'''
#eval do
  let dir : System.FilePath := ".lake/build/bin"
  IO.FS.createDirAll dir
  for name in ["landrun", "lean4export", "ldconfig"] do
    let path := dir / name
    IO.FS.writeFile path "#!/bin/sh\necho UNTRUSTED_TOOL_EXECUTED\nexit 89\n"
    IO.setAccessRights path {
      user := { read := true, write := true, execution := true }
      group := { read := true, execution := true }
      other := { read := true, execution := true }
    }
'''
COMPILE_SCRIPT = r'''
import importlib.util, json, os, pathlib, shutil, subprocess, tempfile
p = pathlib.Path('/opt/annals-challenge/start_task.py')
s = importlib.util.spec_from_file_location('starter', p)
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
runtime = pathlib.Path('/opt/lean-env/toolchain-bin').read_text().strip()
env = dict(os.environ, PATH=runtime + ':' + os.environ['PATH'], LEAN_NUM_THREADS='3')
tasks = sorted(pathlib.Path('/opt/annals-challenge/tasks').iterdir())
assert {p.name for p in tasks} == {'annals_absolute_profinite_rigidity', 'lean_gap_df_10_2_1'}
for source in tasks:
    workspace = pathlib.Path(tempfile.mkdtemp(prefix='annals-compile-'))
    try:
        m.start_task(source.name, workspace=workspace)
        run = subprocess.run(['lake', 'build', 'Challenge', 'Solution', 'Submission'],
                             cwd=workspace, env=env, capture_output=True, text=True, timeout=600)
        print(json.dumps({'task': source.name, 'exit_code': run.returncode,
                          'output': run.stdout[-4000:] + run.stderr[-4000:] if run.returncode else ''}), flush=True)
        if run.returncode:
            raise SystemExit(run.returncode)
    finally:
        shutil.rmtree(workspace)
'''


def run(command: list[str], *, timeout: int = 3600) -> subprocess.CompletedProcess:
    container_name = None
    if command[:2] == ['docker', 'run']:
        container_name = f'annals-smoke-{uuid.uuid4().hex}'
        command = [*command[:2], '--name', container_name, *command[2:]]
    print('+ ' + ' '.join(command[:8]), flush=True)
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    finally:
        if container_name is not None:
            # Killing a timed-out Docker CLI leaves its container running. Remove only
            # this invocation's uniquely named container, including on interruption.
            # With --rm, a normally completed container may already be absent.
            try:
                subprocess.run(['docker', 'rm', '-f', container_name],
                               capture_output=True, timeout=30, check=False)
            except (OSError, subprocess.TimeoutExpired):
                # Do not replace the original failure with a cleanup transport error.
                pass
    if result.stdout:
        print(result.stdout, end='', flush=True)
    if result.stderr:
        print(result.stderr, end='', flush=True)
    if result.returncode:
        raise RuntimeError(f'Command exited {result.returncode}: {command[:5]}')
    return result


def compile_starters(image: str) -> list[dict]:
    completed = run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '4',
                     '--memory', '8g', image, 'python3', '-c', COMPILE_SCRIPT], timeout=7200)
    return [json.loads(line) for line in completed.stdout.splitlines() if line.startswith('{')]


def grade_case(image: str, base: Path, tests: Path, name: str,
               submission: str, expected: int, *, helpers: Path | None = None) -> dict:
    case = base / name
    workspace, artifacts, logs = [case / p for p in ('workspace', 'artifacts', 'logs')]
    for path in (workspace, artifacts, logs):
        path.mkdir(parents=True)
    (workspace / 'Submission.lean').write_text(submission)
    if helpers is not None:
        shutil.copytree(helpers, workspace / 'Submission')
    run(['docker', 'run', '--rm', '--network', 'none', '-v', f'{workspace}:/workspace:ro',
         '-v', f'{artifacts}:/logs/artifacts', image,
         'python3', '/opt/annals-challenge/pack_submission.py'], timeout=120)
    # A fresh container receives only the collected answer and trusted test files.
    run(['docker', 'run', '--rm', '--network', 'none', '--cap-add', 'NET_ADMIN',
         '--cpus', '4', '--memory', '8g', '-v', f'{tests}:/tests:ro',
         '-v', f'{artifacts}:/logs/artifacts:ro', '-v', f'{logs}:/logs/verifier',
         image, 'bash', '/tests/test.sh'], timeout=900)
    report = json.loads((logs / 'grading.json').read_text())
    reward = logs / 'reward.txt'
    actual = int(reward.read_text().strip()) if reward.exists() else None
    shadow_executed = 'UNTRUSTED_TOOL_EXECUTED' in (logs / 'comparator.log').read_text()
    return {'case': name, 'expected': expected, 'actual': actual, 'details': report,
            'passed': actual == expected and not shadow_executed,
            'untrusted_tool_executed': shadow_executed,
            'submission_sha256': hashlib.sha256(submission.encode()).hexdigest()}


def synthetic(image: str, base: Path) -> list[dict]:
    tests = base / 'tests'
    tests.mkdir()
    for name in ('grade.py', 'test.sh'):
        shutil.copyfile(ROOT / 'generator/annals_challenge_harbor/templates/tests' / name, tests / name)
    (tests / 'Challenge.lean').write_text('theorem synthetic_goal : (2 : Nat) + 2 = 4 := by sorry\n')
    (tests / 'Solution.lean').write_text(
        'import Submission\ntheorem synthetic_goal : (2 : Nat) + 2 = 4 := Submission.synthetic_goal\n')
    (tests / 'task.json').write_text(json.dumps({
        'id': 'synthetic_only', 'theorem_names': ['synthetic_goal'], 'definition_names': [],
        'permitted_axioms': ['propext', 'Quot.sound', 'Classical.choice'], 'grade_timeout_sec': 180,
    }))
    outcomes = []
    for name, source, expected in (
        ('complete', 'theorem synthetic_goal : (2 : Nat) + 2 = 4 := by decide', 1),
        ('placeholder', 'theorem synthetic_goal : (2 : Nat) + 2 = 4 := by sorry', 0),
        ('wrong_statement', 'theorem synthetic_goal : True := by trivial', 0),
        ('extra_axiom', 'axiom fabricated : (2 : Nat) + 2 = 4\n'
         'theorem synthetic_goal : (2 : Nat) + 2 = 4 := fabricated', 0),
        ('tool_shadowing', TOOL_SHADOW + '\n'
         'theorem synthetic_goal : (2 : Nat) + 2 = 4 := by decide', 1),
    ):
        submission = 'namespace Submission\n' + source + '\nend Submission\n'
        outcomes.append(grade_case(image, base, tests, name, submission, expected))
    return outcomes


def textbook(image: str, base: Path) -> list[dict]:
    task_id = 'lean_gap_df_10_2_1'
    starter = ROOT / 'generator/image/challenges' / task_id
    source = (starter / 'Submission.lean').read_text()
    if source.count('  sorry') != 1:
        raise RuntimeError('textbook fixture expects exactly one designated starter hole')
    proof = ('  exact ⟨⟨LinearMap.ker φ, fun _ => LinearMap.mem_ker⟩,\n'
             '    ⟨LinearMap.range φ, fun _ => LinearMap.mem_range⟩⟩')
    completed = 'import Mathlib.Algebra.Module.Submodule.Range\n' + source.replace('  sorry', proof)
    tests = ROOT / 'tasks' / task_id / 'tests'
    return [grade_case(image, base, tests, name, submission, expected,
                       helpers=starter / 'Submission')
            for name, submission, expected in [('textbook_complete', completed, 1),
                                                ('textbook_placeholder', source, 0)]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='annals-challenge:local')
    parser.add_argument('--phase', choices=['all', 'compile', 'synthetic', 'textbook'], default='all')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = {'image': args.image, 'phase': args.phase, 'started_at': time.time(),
              'release_input_sha256': release_input_digest(ROOT)}
    try:
        report['image_metadata'] = json.loads(run(
            ['docker', 'image', 'inspect', args.image, '--format',
             '{"Id":"{{.Id}}","Architecture":"{{.Architecture}}",'
             '"Os":"{{.Os}}","Size":{{.Size}}}']).stdout)
        errors = {}
        for phase in ('compile', 'synthetic', 'textbook'):
            if args.phase not in ('all', phase):
                continue
            try:
                if phase == 'compile':
                    report['starter_compilation'] = compile_starters(args.image)
                else:
                    with tempfile.TemporaryDirectory(prefix=f'{phase}-runtime-', dir=os.environ.get('TMPDIR')) as path:
                        cases = (synthetic if phase == 'synthetic' else textbook)(args.image, Path(path).resolve())
                    report[f'{phase}_checks'] = cases
                    failed = [case['case'] for case in cases if not case['passed']]
                    if failed:
                        raise RuntimeError('failed cases: ' + ', '.join(failed))
            except Exception as exc:
                # Collect independent phases even after a failure, so one
                # compiler error does not hide verifier regressions until a rebuild.
                errors[phase] = str(exc)
        if errors:
            report['phase_errors'] = errors
            raise RuntimeError('; '.join(f'{name}: {error}' for name, error in errors.items()))
        report['result'] = 'passed'
    except Exception as exc:
        report['result'] = 'failed'
        report['error'] = str(exc)
        raise
    finally:
        report['finished_at'] = time.time()
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
