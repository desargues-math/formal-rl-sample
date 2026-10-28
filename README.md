# Desargues Sample

Two Lean 4 theorem-proving tasks: one textbook algebra exercise and one research theorem. Each includes a starter workspace, an execution environment, and automated proof verification for [Harbor](https://github.com/harbor-framework/harbor).

The statements and verification components are adapted from existing projects. Sources and credits are recorded in [`sources.lock.json`](sources.lock.json) and [`sources/`](sources/).

**Validation status:** this is an integration sample under validation. Current
software results and uncompleted runtime checks are recorded in
[`sample-checks.json`](sample-checks.json). The full pinned-image and hosted
workflow have not yet been validated for this sample. The Lean-GAP source
permission record is still unconfirmed; see [`RIGHTS.md`](RIGHTS.md) and
[`NOTICE`](NOTICE) for component attribution and license scope.

## Included tasks

| Task | Task ID | Mathematical level |
| --- | --- | --- |
| [Kernel and image of a linear map are submodules](tasks/lean_gap_df_10_2_1/instruction.md) | `lean_gap_df_10_2_1` | Textbook algebra |
| [Absolute profinite rigidity and hyperbolic geometry](tasks/annals_absolute_profinite_rigidity/instruction.md) | `annals_absolute_profinite_rigidity` | Research mathematics |

Each task has one theorem target and includes instructions, an environment recipe, starter workspace inputs, and a verifier. `manifest.json`, `manifest.parquet`, and `registry.json` describe both tasks. The levels describe the mathematics; agent solving difficulty has not been empirically calibrated. Agent starter packages contain no reference proofs.

The research task is an uncalibrated challenge. No accepted reference run or
agent success rate is recorded for it. The textbook reference fixture in the
runtime checker is for validating grading and is not a measured agent result.

## Agent workflow and grading

1. Initialize `/workspace` using the command in the task's instructions.
2. Complete `Submission.lean`, adding Lean helper files under `Submission/` as needed. Lean and Mathlib are available; task execution runs without network access.
3. Harbor collects the submitted Lean files and sends them to a fresh verifier sandbox. Comparator checks the proof against the original trusted statement.

**Reward is 1 for a fully accepted proof and 0 for an incomplete, invalid, or timed-out submission.** There is no partial credit. Infrastructure failures are reported separately. Lean compilation alone does not establish success: unfinished `sorry` proofs are rejected by the verifier.

`Solution.lean` connects the submitted declarations to the verifier; it contains no reference proof. The submitted answer is the workspace files.

## Run a task

Requires Python 3.12+, Git, and a Daytona account. Set `DAYTONA_API_KEY`, `DAYTONA_API_URL`, and the credentials required by your agent. Replace `AGENT_NAME` and `MODEL_NAME` below with your chosen agent and model.

```bash
git clone https://github.com/desargues-math/formal-rl-sample.git
cd formal-rl-sample

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e './generator[run]'
python -m annals_challenge_harbor.snapshot
SNAP=$(python -m annals_challenge_harbor.snapshot --print-name)

harbor run -p tasks -e daytona --ek snapshot_template_name="$SNAP" \
  -a AGENT_NAME -m MODEL_NAME -i lean_gap_df_10_2_1 -n 1
```

The snapshot command builds the shared environment in your Daytona account. Initial setup requires network access; agent execution and grading are offline. To run the research task, use `-i annals_absolute_profinite_rigidity`.

Each task requests **4 CPUs, 8 GiB memory, and 10 GiB storage**, with a four-hour agent budget and a three-hour-fifteen-minute verifier budget.

## Environment

The sample includes a shared Docker build recipe and a Daytona snapshot helper. See the [environment documentation](generator/README.md) for local Docker builds, dependency versions, and regeneration.
