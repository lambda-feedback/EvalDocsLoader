# Changelog

## Unreleased

## 0.3.0

- Switch distribution from PyPI to tagged GitHub Releases. Consumers install with a
  `git`/`git+https` reference pinned to a `vX.Y.Z` tag; the PyPI `evaldocsloader`
  project is deprecated.
- Add `.github/workflows/release.yml`. Run it from **Actions → Release** with a
  `patch`/`minor`/`major`/`pre*` bump: it bumps `pyproject.toml`, commits and tags on
  `main`, builds, and publishes a GitHub Release with the `sdist`/`wheel` attached.
  Also runs on a manually pushed `v*` tag (verified against `pyproject.toml`).
