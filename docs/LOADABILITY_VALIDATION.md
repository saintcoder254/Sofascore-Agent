# Loadability validation

## What CI verifies

The `Loadability and smoke tests` workflow installs declared runtime dependencies on Python 3.11 and 3.12, compiles the Python source tree, imports the FastAPI application, checks required routes, verifies that the qualification gate fails closed on missing evidence, and checks that the market model emits finite bounded probabilities for a minimal offline fixture.

## What CI does not prove

Passing these tests does not establish live provider availability, Render health, probability calibration, or successful qualification of a real match. Those require separate integration tests with source telemetry and a known fixture ID. No production prediction should be released when those checks are unavailable.

## Local verification

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
python -m compileall -q .
python -m pytest -q
uvicorn app:app --host 0.0.0.0 --port 8000
```
