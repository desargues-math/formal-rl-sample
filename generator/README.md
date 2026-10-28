# Generator and environment

Scripts and a shared execution environment for packaging and running the two sample tasks.

## Regenerate offline

From the repository root, use Python 3.12 or later for Harbor 0.24. The generator
alone also supports Python 3.11.

```bash
python -m venv .venv
.venv/bin/pip install -e './generator[test]' 'harbor==0.24.0'
.venv/bin/python -m annals_challenge_harbor.adapter
.venv/bin/python -m annals_challenge_harbor.checks
```

To generate a separate copy, add `--out /path/to/release` to the adapter command.
The generator reads the committed source subset, verifies its SHA-256 inventories,
and preserves the mathematical statements. Source revisions and attribution are
recorded in [`sources.lock.json`](../sources.lock.json) and [`sources/`](../sources/).
Changing a pinned source requires an explicit source update; regeneration does not
follow upstream branches.

The generated package contains task instructions, starter workspaces, trusted
verifier inputs, manifests, and the shared image recipe. `Submission.lean` is the
agent's editable entry point; `Solution.lean` connects it to the verifier and
contains no reference proof. The runtime checker has a separate textbook proof
fixture; it is never copied into an agent starter.

## Build and run

Every task uses the same environment content. The image contains both starter
packages, selected by the `start_task.py` command in each task's instructions.
Reinitializing the same task preserves existing work; switching tasks requires a
fresh workspace.

The recipe pins Lean 4.35.0-rc3 for task compilation and lean4export, Lean 4.34.0
for Comparator, and a fixed Mathlib revision. It writes the task compiler location
to `/opt/lean-env/toolchain-bin` for the verifier. The recipe is designed for native Linux
amd64 and arm64 builds.

Build locally from the repository root:

```bash
docker build -t formal-rl-sample:local generator/image
```

For Daytona, install the runner dependencies and create the shared snapshot:

```bash
.venv/bin/pip install -e './generator[run]'
.venv/bin/python -m annals_challenge_harbor.snapshot
.venv/bin/python -m annals_challenge_harbor.snapshot --print-name
```

The snapshot name hashes the complete image context, including task payloads.
Credentials belong in the caller's environment. See the [main README](../README.md)
for the Harbor run command and resource requirements.

## Submission and grading

Only `Submission.lean` and optional `.lean` modules under `Submission/` cross from
the agent workspace to a fresh verifier sandbox. The trusted statement, fixed
definitions, bridge, configuration, and dependencies come from the task package.

Comparator checks the submitted proof against the trusted targets. Only `propext`,
`Quot.sound`, and `Classical.choice` are allowed; `enable_nanoda=false`.
The verifier uses an unprivileged build, read-only packages, network blocking,
bounded archive handling, and process cleanup.

After Lake prepares `LEAN_PATH`, a trusted launcher removes workspace executable
and dynamic-library search paths and pins Comparator, Landrun and lean4export to
absolute image paths. Local adversarial tests cover executable shadows and
symlink aliases. The corresponding Linux container smoke case remains a separate
runtime check; local tests do not establish sandbox security on the deployment host.

An accepted submission writes `1` to `/logs/verifier/reward.txt`. A rejected,
incomplete, missing, or non-compiling submission writes `0`. Trusted setup failures
produce diagnostic logs without a reward and are reported as infrastructure errors.

## Verification

The package tests cover statement preservation, task membership, target lists,
shared environment inputs, dependency pins, deterministic regeneration, workspace
initialization, trusted staging, and submission archive handling. Installing
`harbor==0.24.0` also enables parsing the bundles with Harbor's task model.

The checks command writes `sample-checks.json` from a fresh pytest run and records
the input digest and installed Python, Harbor, pytest and PyArrow versions. Its
pass status requires Harbor 0.24.0, no skipped tests, unchanged release inputs
during testing, and a successful test exit. Raw logs and JUnit evidence are saved
under `work/checks/`. The GitHub Actions workflow runs the same software checks.

After building the image, run starter compilation, synthetic security checks and
the actual textbook reference proof through collection and fresh grading:

```bash
.venv/bin/python generator/tests/smoke_runtime.py \
  --image formal-rl-sample:local --report work/runtime-checks.json
```

These checks exercise valid and invalid synthetic proofs, rejection of additional
axioms, submission-controlled tool shadows, and acceptance of the textbook proof
with rejection of its unfinished starter. They require Docker's `NET_ADMIN`
capability for network isolation and do not measure agent solving difficulty or
prove the Annals target. Reports identify the actual image ID and architecture.

To attach a successful complete runtime report to current software evidence:

```bash
.venv/bin/python -m annals_challenge_harbor.checks \
  --runtime-report work/runtime-checks.json
```

The report must be from all runtime phases and match the current release input
digest. Partial, failed and stale runtime evidence is not accepted.

Recorded results for this two-task sample are in [`sample-checks.json`](../sample-checks.json).
The report states which software and Linux container checks have run. Linux
container results do not certify a separate hosted deployment. The root
`packaging-checks.json` and `runtime-checks.json` describe an earlier release and
do not validate this sample.
