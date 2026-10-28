"""Annals-specific verifier staging and classification, without root or Lean installed."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

GRADE = Path(__file__).parents[1] / "annals_challenge_harbor" / "templates" / "tests" / "grade.py"
spec = importlib.util.spec_from_file_location("annals_grade_project", GRADE)
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


class ProjectTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = self.root / "lean-env"
        self.tests = self.root / "trusted-tests"
        self.run_root = self.root / "runs"
        for directory in (self.env, self.tests, self.run_root):
            directory.mkdir()
        (self.env / ".lake" / "packages").mkdir(parents=True)
        self.project = {
            "lakefile.lean": "-- canonical project with pinned Mathlib\n",
            "lake-manifest.json": '{"packages": []}\n',
            "lean-toolchain": "leanprover/lean4:v4.35.0-rc3\n",
        }
        for name, text in self.project.items():
            (self.env / name).write_text(text)
        self.challenge = "theorem target : True := by sorry\n"
        self.solution = "import Submission\n"
        (self.tests / "Challenge.lean").write_text(self.challenge)
        (self.tests / "Solution.lean").write_text(self.solution)
        self.config = {
            "id": "synthetic-fixture",
            "grade_timeout_sec": 10,
            "theorem_names": ["target"],
            "definition_names": [],
            "permitted_axioms": ["propext", "Quot.sound", "Classical.choice"],
            # The verifier fixes these trusted module names and the optional secondary kernel.
            "challenge_module": "UntrustedChallenge",
            "solution_module": "UntrustedSolution",
            "enable_nanoda": True,
        }
        for name, value in (("LEAN_ENV", self.env), ("TESTS", self.tests), ("RUN_ROOT", self.run_root)):
            mock = patch.object(grade, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        # Linux's grader account and ownership changes are unrelated to the staging assertions.
        mock = patch.object(grade.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=2000))
        mock.start()
        self.addCleanup(mock.stop)
        mock = patch.object(grade.os, "chown")
        mock.start()
        self.addCleanup(mock.stop)

    def test_stages_canonical_project_and_trusted_wrappers(self):
        run = grade.fresh_run(self.config)
        for name, text in self.project.items():
            self.assertEqual((run / name).read_text(), text)
        self.assertEqual((run / "Challenge.lean").read_text(), self.challenge)
        self.assertEqual((run / "Solution.lean").read_text(), self.solution)
        self.assertFalse((run / "ChallengeDeps.lean").exists())
        self.assertFalse((run / "Submission.lean").exists())
        self.assertTrue((run / ".lake" / "packages").is_symlink())
        self.assertEqual((run / ".lake" / "packages").resolve(), (self.env / ".lake" / "packages").resolve())
        actual = json.loads((run / "config.json").read_text())
        self.assertEqual(actual, {
            "challenge_module": "Challenge",
            "solution_module": "Solution",
            "theorem_names": self.config["theorem_names"],
            "definition_names": self.config["definition_names"],
            "permitted_axioms": self.config["permitted_axioms"],
            "enable_nanoda": False,
        })

    def test_stages_optional_dependency_from_trusted_tests(self):
        content = "def fixedDefinition : Nat := 17\n"
        (self.tests / "ChallengeDeps.lean").write_text(content)
        run = grade.fresh_run(self.config)
        self.assertEqual((run / "ChallengeDeps.lean").read_text(), content)

    def test_repeated_attempts_do_not_reuse_agent_build_products(self):
        first = grade.fresh_run(self.config)
        (first / ".lake" / "build").mkdir()
        (first / ".lake" / "build" / "untrusted.olean").write_text("untrusted")
        (first / "Solution.lean").write_text("changed wrapper")
        second = grade.fresh_run(self.config)
        self.assertNotEqual(first, second)
        self.assertFalse((second / ".lake" / "build").exists())
        self.assertEqual((second / "Solution.lean").read_text(), self.solution)

    def test_missing_trusted_wrapper_is_an_infrastructure_error(self):
        (self.tests / "Solution.lean").unlink()
        with self.assertRaises(FileNotFoundError):
            grade.fresh_run(self.config)

    def test_runtime_toolchain_is_explicit(self):
        selected = self.root / "task-toolchain" / "bin"
        selected.mkdir(parents=True)
        for name in ("lean", "lake"):
            (selected / name).write_text("#!/bin/sh\n")
            (selected / name).chmod(0o755)
        (self.env / "toolchain-bin").write_text(str(selected) + "\n")
        self.assertEqual(grade.toolchain_bin(), selected)

    def test_missing_or_invalid_toolchain_is_an_infrastructure_error(self):
        with self.assertRaises(grade.GradingError):
            grade.toolchain_bin()
        for location in ("", "relative/bin", str(self.root / "absent")):
            with self.subTest(location=location):
                (self.env / "toolchain-bin").write_text(location)
                with self.assertRaises(grade.GradingError):
                    grade.toolchain_bin()


class ClassifyTest(unittest.TestCase):
    def test_solution_wrapper_marks_submission_stage(self):
        output = "Building Challenge\nBuilding Solution\nerror: Submission.lean failed\n"
        self.assertEqual(grade.classify(1, output)[0], 0)

    def test_trusted_challenge_failure_does_not_score_the_agent(self):
        output = "Building Challenge\nerror: ChallengeDeps.lean failed\n"
        self.assertIsNone(grade.classify(1, output)[0])
        self.assertIsNone(grade.classify(None, output)[0])

    def test_success_message_alone_does_not_override_nonzero_exit(self):
        output = "Building Solution\nYour solution is okay!\n"
        self.assertEqual(grade.classify(1, output)[0], 0)
        self.assertEqual(grade.classify(0, output)[0], 1)
        self.assertEqual(grade.classify(0, "Building Solution\n")[0], 0)


if __name__ == "__main__":
    unittest.main()
