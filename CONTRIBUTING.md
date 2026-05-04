# Contributing

Thank you for your interest in contributing to anxwritter.

## Before you start

Open an issue first for any non-trivial change so we can agree on approach
before you invest time writing code. For typos, doc fixes, or clearly isolated
bugs a PR without a prior issue is fine.

## Developer Certificate of Origin

This project uses the
[Developer Certificate of Origin v1.1](https://developercertificate.org) (DCO).
By submitting a contribution you certify that you authored it or otherwise have
the right to submit it under the MIT licence.

Add a sign-off line to every commit:

```bash
git commit -s -m "your message"
```

This appends `Signed-off-by: Your Name <your@email.com>` to the commit message.
Commits without a sign-off will not be merged.

## Development setup

```bash
pip install -e ".[dev]"
```

## Running tests

```bash
pytest           # standard suite
pytest -m perf   # performance / scale tests (slow, opt-in)
```

## Code style

- PEP 8; the project uses `ruff` for linting.
- No new runtime dependencies without prior discussion in an issue.
- Type hints for any new public API surface.

## ANX format references

Do not paste text or assets from i2/N.Harris into this repository — XML
schemas, ANB error messages, EULA or NOTICES text, help-text excerpts, the
standard semantic-type library, icon files, or DLLs.

## Pull requests

- One logical change per PR.
- Add or update tests for any changed behaviour.
- CI runs on Python 3.10–3.13; all versions must pass before merge.
