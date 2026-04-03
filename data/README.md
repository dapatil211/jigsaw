# Data Directory

Use this directory for local sample data, evaluation manifests, and runtime artifacts that are not intended to live in source control by default.

Suggested layout:

```text
data/
|-- raw/
|-- manifests/
|-- eval/
`-- sessions/
```

Keep large images and generated session artifacts out of git unless they are intentionally curated fixtures.

## Recommended External Dataset Layout

- `data/raw/`: source captures used for local experiments
- `data/manifests/`: JSON manifests matching `docs/dataset-manifest.md`
- `data/eval/`: derived evaluation reports
- `data/sessions/`: runtime session artifacts created by the backend

## Included Fixture

- `data/manifests/smoke-manifest.json`: generated synthetic fixture for smoke-testing the validator and baseline evaluator
