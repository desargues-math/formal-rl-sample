# Vendor readiness repair plan

Baseline: `e1ddb0d1cad236f4d22232ab9a964234a701cba4`, reviewed 2026-10-29.
Work branch: `fix/vendor-readiness`.

## Current progress

- Packaging: `NOTICE` restored, Apache-2.0 text and component attribution added; regenerated release checks pass.
- Verifier: post-Lake tool/library filtering and absolute tool paths implemented. Local adversarial checks pass.
- Software evidence: automated report command and pinned-action CI workflows implemented. The first repaired suite passed 35 tests and 26 subtests.
- Runtime: actual textbook and additional adversarial smoke cases implemented. The tool-shadow fixture's Lean syntax was checked locally with Lean 4.34.1; this is not the pinned production runtime result.
- Full Linux build: pending; local host has about 8 GiB free, insufficient headroom for a fresh full Lean/Mathlib image. A Linux CI workflow is prepared for the build and grading checks.
- Commercial permission and agent difficulty: remain open. Contributor network affiliation is separate from the component permission record.

## 1. Repair packaging and attribution

- Restore `NOTICE` and the Apache-2.0 license text already declared by the generator.
- Record which files are original integration work and which are adapted inputs.
- Keep Lean-GAP's unconfirmed license explicit; do not claim permission that has not been evidenced.
- Require attribution files in regenerated releases and test their presence.

Done when the documented packaging tests pass and a separate generated release contains all notices.

## 2. Restore verifier tool isolation

- Keep the task's Lean search paths, but remove workspace paths from executable and dynamic-library lookup after `lake env` prepares the environment.
- Pin Comparator, Landrun and lean4export to absolute image-owned paths.
- Test a submission-writable executable shadow and reject symlink aliases to the workspace.
- Add container smoke coverage for tool shadowing and unauthorized axioms.

Done when local adversarial path tests pass; production security validation additionally requires the pinned Linux image smoke run.

## 3. Make release evidence reproducible

- Replace the inaccurate hand-maintained software result with a report generated from a real pytest run.
- Record the checked input digest, Python/Harbor versions, scope, and uncompleted checks.
- Add CI for packaging, trusted statement preservation and regeneration.
- Validate a real textbook proof through collection and the fresh verifier, alongside positive and negative synthetic cases.
- Keep the research task's solvability and agent difficulty unverified until actual evidence exists.

Done when a fresh local check produces a truthful report. Container and hosted results must be reported separately and never inferred from unit tests.

## 4. Run the supported environment

- Build or reuse only an image matching the current context; record the actual image ID and architecture.
- Run starter compilation, real textbook acceptance, placeholder rejection, extra-axiom rejection, and adversarial tool lookup checks.
- Run Harbor collection and grading on Daytona once a supported image and execution credentials are available.
- Keep failures visible as failures; do not reuse historical 50-task reports as current evidence.

Done when current logs demonstrate the advertised end-to-end workflow. Do not delete unrelated local images or consume external paid resources to work around missing local capacity.

## 5. Complete the buyer evidence package

- Obtain and record Lean-GAP redistribution/commercial-use permission or replace that input with a clearly licensed task.
- Measure solving rates on named models with fixed attempt counts and budgets; include time and infrastructure errors.
- Select an intermediate task using those results, with a verified reference proof, rather than assigning an unsupported difficulty label.
- Describe the delivered value as task adaptation, environment integration and verification, with original contributions identified accurately.

Done when permissions and empirical results support the claims in the buyer-facing sample. A lower price does not substitute for this evidence.

## Change delivery

Make changes on the repair branch, regenerate both task bundles from the canonical templates, run appropriate checks, and prepare a reviewable patch. No main-branch merge is part of this repair pass.
