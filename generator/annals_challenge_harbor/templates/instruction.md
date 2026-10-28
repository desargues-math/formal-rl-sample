# $title

Prove the supplied Lean theorem for task `$task_id`.

Initialize this task's workspace once:

```bash
python3 /opt/annals-challenge/start_task.py $task_id
cd /workspace
```

Read `Challenge.lean`, `Submission.lean`, and `ChallengeDeps.lean` when present. Fill every designated hole in `Submission.lean`, inside its existing `Submission` namespace. All targets in this task must be completed together:

$holes

Some holes construct a definition or instance used by later theorems. Supply those values together with the required proofs. Preserve the supplied declaration types and names. Add helper declarations in `Submission.lean` or additional Lean files under `Submission/`, importing them as needed. `Submission/Helpers.lean` is available as a starting point.

Lean, Mathlib and their pinned dependencies are installed. There is no internet access and no additional Lean Pool library. Keep the project's dependency configuration unchanged. You may check elaboration with `lake build Solution`; successful compilation alone does not establish completion because Lean accepts `sorry` placeholders.

`Challenge.lean`, `ChallengeDeps.lean`, `Solution.lean`, the Comparator configuration, and project/toolchain files are trusted task inputs. Only `Submission.lean` and Lean files under `Submission/` are collected. Changes to other files are not part of the submitted answer.

A fresh verifier uses the original trusted files and checks all designated declarations with Comparator. Reward is 1 only when the complete submission passes; otherwise it is 0. The accepted axioms are `propext`, `Quot.sound`, and `Classical.choice`; unfinished proofs and additional axioms are rejected. Write the formalization to the workspace files; the final chat response is not the submission.

Source: $source

