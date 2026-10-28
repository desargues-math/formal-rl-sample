"""Adversarial tool lookup checks at the post-Lake verifier boundary."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

import pytest

GRADE = Path(__file__).parents[1] / 'annals_challenge_harbor/templates/tests/grade.py'
spec = importlib.util.spec_from_file_location('grade_tool_paths', GRADE)
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


@pytest.fixture
def layout(tmp_path):
    run = tmp_path / 'workspace'
    writable = run / '.lake/build/bin'
    trusted = tmp_path / 'trusted-bin'
    writable.mkdir(parents=True)
    trusted.mkdir()
    tools = {}
    for key, name in [('COMPARATOR_BIN', 'comparator'),
                      ('COMPARATOR_LANDRUN', 'landrun'),
                      ('COMPARATOR_LEAN4EXPORT', 'lean4export')]:
        for directory, message in [(writable, 'untrusted'), (trusted, 'trusted')]:
            path = directory / name
            path.write_text(f'#!/bin/sh\nprintf "{message}\\n"\n')
            path.chmod(0o755)
        tools[key] = trusted / name
    with patch.object(grade, 'COMPARATOR_TOOLS', tools):
        yield run, writable, trusted, tools


def test_submission_tool_shadows_are_never_executed(layout, tmp_path):
    run, writable, trusted, _ = layout
    alias = tmp_path / 'workspace-bin-alias'
    alias.symlink_to(writable, target_is_directory=True)
    env = grade.comparator_environment(run, {
        'PATH': os.pathsep.join(map(str, [writable, alias, trusted, tmp_path / 'absent'])),
        'LEAN_PATH': 'preserve-the-task-module-search-path',
        'COMPARATOR_LANDRUN': str(writable / 'landrun'),
        'LD_LIBRARY_PATH': str(alias),
        'DYLD_LIBRARY_PATH': os.pathsep.join([str(writable), str(trusted)]),
    })
    assert env['LEAN_PATH'] == 'preserve-the-task-module-search-path'
    assert 'LD_LIBRARY_PATH' not in env
    assert env['DYLD_LIBRARY_PATH'] == str(trusted.resolve())
    for key, name in [('COMPARATOR_BIN', 'comparator'),
                      ('COMPARATOR_LANDRUN', 'landrun'),
                      ('COMPARATOR_LEAN4EXPORT', 'lean4export')]:
        assert shutil.which(name, path=env['PATH']) == str(trusted.resolve() / name)
        result = subprocess.run([env[key]], env=env, capture_output=True, text=True, check=True)
        assert result.stdout == 'trusted\n'


def test_workspace_symlink_cannot_be_a_trusted_tool(layout, tmp_path):
    run, writable, trusted, tools = layout
    link = trusted / 'tool-alias'
    link.symlink_to(writable / 'landrun')
    tools['COMPARATOR_LANDRUN'] = link
    with pytest.raises(grade.GradingError, match='unsafe trusted tool'):
        grade.comparator_environment(run, {'PATH': str(trusted)})


def test_empty_relative_or_only_workspace_path_fails_closed(layout):
    run, writable, _, _ = layout
    for value in ['', '.', f'{writable}{os.pathsep}.', str(writable / 'not-created-yet')]:
        with pytest.raises(grade.GradingError, match='no trusted executable'):
            grade.comparator_environment(run, {'PATH': value})


def test_missing_image_tool_is_an_infrastructure_error(layout):
    run, _, trusted, tools = layout
    tools['COMPARATOR_LEAN4EXPORT'].unlink()
    with pytest.raises(grade.GradingError, match='missing trusted tool'):
        grade.comparator_environment(run, {'PATH': str(trusted)})
