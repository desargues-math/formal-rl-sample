# Component provenance and rights record

This record separates integration code from upstream mathematical content. The
root Apache-2.0 license applies to the original generator and integration work;
it does not replace the terms of third-party inputs.

| Component | Evidence | Recorded status |
| --- | --- | --- |
| Desargues generator, environment recipes and Harbor integration | `generator/pyproject.toml`, `LICENSE`, `NOTICE` | Apache-2.0, matching the package's existing declaration |
| LeanEval selected source and generated research workspace | `sources/lean-eval/LICENSE`, `sources/lean-eval/provenance.json` | Upstream Apache-2.0 text retained |
| AnnalsChallenge research statement, via LeanEval | [License at pinned revision](https://github.com/ImperialCollegeLondon/AnnalsChallenge/blob/e32eb1411db0d700ca874dd695aea92f78699db8/LICENSE), `sources.lock.json` | Upstream Apache-2.0 |
| FineEnvs verifier adaptation | `generator/annals_challenge_harbor/templates/tests/grade.py` source header, pinned dataset in `sources.lock.json` | Apache-2.0 as recorded by the adaptation; retain attribution in `NOTICE` |
| Lean-GAP textbook statement | `sources/lean-gap/task.json`, `sources/lean-gap/provenance.json` | Unconfirmed: supplied archive did not specify a license |
| Image dependencies | Repository URLs and exact revisions in `sources.lock.json` and `generator/image/lake-manifest.json` | Upstream terms apply; source trees retain their license files |

## Open permission record

The Lean-GAP input is identified by archive SHA-256
`23db6c436d7b115038a049d5bf8c61c55c713ade2f64e98e566f821393ffcbe3`
and statement SHA-256
`3fe291eeaf6242f852d51e8e3fb3495b059f08a8bef245cd5bb51742fb96fe20`.

Before representing this complete bundle as cleared for commercial redistribution,
record the applicable dataset license or a permission grant covering that file,
including its source, date, scope and required attribution. A paper citation or
the existence of a public download is not a permission record for this archive.
Until that evidence is available, this component remains unconfirmed. An
alternative is to replace it with a task whose permissions are documented and
rerun statement, packaging and runtime validation.

## Authored contribution

The delivered work adapts public formal statements into Harbor tasks and adds
workspace initialization, artifact collection, reproducible source inventories,
environment recipes and fresh verification. The selected theorem statements and
the upstream research starter/bridge are credited to their sources. Reference
proofs used for runtime checks are test fixtures, not additional dataset tasks.
