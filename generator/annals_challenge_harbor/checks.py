"""Generate current software evidence; do not infer runtime or agent results."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
REPORT_FILES = {'sample-checks.json', 'packaging-checks.json', 'runtime-checks.json',
                'REPAIR_PLAN.md'}


def release_input_digest(root: Path = ROOT) -> str:
    """Hash validation inputs, excluding evidence, progress notes and local caches."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(p in {'.git', '.venv', '.lake', '.pytest_cache', '__pycache__', 'work',
                     'build', 'dist'} or p.endswith('.egg-info') for p in relative.parts):
            continue
        if (not path.is_file() or path.name in REPORT_FILES
                or path.suffix == '.pyc' or path.name == '.DS_Store'):
            continue
        digest.update(relative.as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def installed_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'sample-checks.json')
    parser.add_argument('--runtime-report', type=Path)
    args = parser.parse_args()
    before = release_input_digest()
    logs = ROOT / 'work/checks'
    logs.mkdir(parents=True, exist_ok=True)
    junit = logs / 'junit.xml'
    junit.unlink(missing_ok=True)
    started = time.monotonic()
    command = [sys.executable, '-m', 'pytest', 'generator/tests', '-q',
               f'--junitxml={junit.relative_to(ROOT)}']
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=600)
    (logs / 'pytest.log').write_text(completed.stdout)
    print(completed.stdout, end='')
    after = release_input_digest()
    suites = ET.parse(junit).getroot().iter('testsuite') if junit.is_file() else []
    counts = {name: 0 for name in ('tests', 'failures', 'errors', 'skipped')}
    for suite in suites:
        for name in counts:
            counts[name] += int(suite.attrib.get(name, 0))
    passed = (completed.returncode == 0 and before == after and counts['tests'] > 0
              and counts['failures'] == 0 and counts['errors'] == 0
              and counts['skipped'] == 0 and installed_version('harbor') == '0.24.0')
    report = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'release_input_sha256': after,
        'task_count': len(list((ROOT / 'tasks').glob('*/task.toml'))),
        'software_checks': {
            'result': 'passed' if passed else 'failed',
            'command': 'python -m pytest generator/tests -q --junitxml=work/checks/junit.xml',
            'exit_code': completed.returncode,
            'inputs_unchanged_during_checks': before == after,
            'python': platform.python_version(),
            'harbor': installed_version('harbor'),
            'pytest': installed_version('pytest'),
            'pyarrow': installed_version('pyarrow'),
            'junit_counts_including_subtests': counts,
            'duration_sec': round(time.monotonic() - started, 3),
            'scope': 'Packaging, source preservation, regeneration and local Python regressions; no container execution.',
        },
        'runtime': {'result': 'not_completed',
                    'scope': 'The full pinned-image verifier has not been validated for these inputs.'},
    }
    if args.runtime_report is not None:
        runtime = json.loads(args.runtime_report.read_text())
        if (runtime.get('release_input_sha256') != after
                or runtime.get('phase') != 'all' or runtime.get('result') != 'passed'):
            raise SystemExit('Runtime evidence must be a successful all-phase run for these exact release inputs')
        report['runtime'] = runtime
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
