# Scripts Directory

This directory contains helper scripts for local development and evaluation.

Implemented scripts:

- `generate_smoke_fixture.py`: creates a synthetic local fixture under `data/` for validator and evaluator smoke tests.
- `validate_manifest.py`: validates dataset manifest JSON files against the expected shape.
- `evaluate_baseline.py`: runs the current contour-ranking baseline against one or more manifests and reports top-k metrics.
