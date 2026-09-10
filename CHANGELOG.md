# Changelog

## Unreleased

## 0.3.0

- Switch distribution from PyPI to tagged GitHub Releases. Consumers install with a
  `git`/`git+https` reference pinned to a `vX.Y.Z` tag; the PyPI `evaldocsloader`
  project is deprecated.
- Add `.github/workflows/release.yml`: on a pushed `v*` tag it checks the tag against
  `pyproject.toml`, builds the package, and publishes a GitHub Release with the
  `sdist`/`wheel` attached.
