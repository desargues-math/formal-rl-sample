# Vendor readiness repair plan

Baseline: `e1ddb0d1cad236f4d22232ab9a964234a701cba4`, reviewed 2026-10-29.
Work branch: `fix/vendor-readiness`.

## Current progress

- Packaging: `NOTICE` restored, Apache-2.0 text and component attribution added; regenerated release checks pass.
- Verifier: post-Lake tool/library filtering and absolute tool paths implemented. Local adversarial checks pass.
- Software evidence: automated report command and pinned-action CI workflows implemented. The first repaired suite passed 35 tests and 26 subtests.
- Runtime: actual textbook and additional adversarial smoke cases implemented. The tool-shadow fixture's Lean syntax was checked locally with Lean 4.34.1; this is not the pinned production runtime result.
- Full Linux build: succeeded on GitHub's amd64 runner in about 7 minutes. Starter compilation found a textbook bridge error: the bridge omitted the explicit linear-map argument. This is fixed without changing the theorem statement; the complete runtime suite is being rerun.
- Presentation: keep research/textbook as mathematical levels. No empirical agent difficulty or hosted-platform pass is claimed. Lean-GAP stays in the sample with its existing attribution and provenance.

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
- Describe research/textbook as mathematical levels; do not make agent-performance claims.

Done when a fresh local check produces a truthful report. Container and hosted results must be reported separately and never inferred from unit tests.

## 4. Run the supported environment

- Build or reuse only an image matching the current context; record the actual image ID and architecture.
- Run starter compilation, real textbook acceptance, placeholder rejection, extra-axiom rejection, and adversarial tool lookup checks.
- Run Harbor collection and grading on Daytona once a supported image and execution credentials are available.
- Keep failures visible as failures; do not reuse historical 50-task reports as current evidence.

Done when current logs demonstrate the advertised end-to-end workflow. Do not delete unrelated local images or consume external paid resources to work around missing local capacity.

## 5. Present the sample accurately

- Keep the two mathematical level labels: textbook algebra and research mathematics.
- Include the actual software and Linux verifier results, with their tested input digest.
- Describe the work and expert contributions accurately while retaining upstream attribution.
- Keep task provenance available; the original permission record is not changed by a software test result.
- Agent solving-rate studies and additional intermediate tasks are optional future work, not claims made by this two-task sample.

Done when the buyer-facing claims match the evidence and the sample's stated scope.

## Change delivery

Make changes on the repair branch, regenerate both task bundles from the canonical templates, run appropriate checks, and prepare a reviewable patch. No main-branch merge is part of this repair pass.
