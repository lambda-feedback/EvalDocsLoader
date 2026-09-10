# MkDocs Plugin: Evaluation Function Documentation Loader

Mkdocs plugin for fetching additional .md files registered in a db before render. Specifically from a web request which returns all the available evaluation functions endpoints.

This plugin was specifially developed for the [LambdaFeedback](https://lambdafeedback.com) platform.

_NOTE: There is currently no safety checking to make sure downloaded markdown files are valid and able to be rendered, they are simply copied over directly from the evaluation function endpoint_

## Configuration

Enable plugin in the `mkdocs.yml` file:

```yaml
plugins:
  - evaldocsloader:
    functions_announce_endpoint: "http://127.0.0.1:5050/testingfunctions"
    api_key: !ENV [API_KEY, "disable"]
    dev_section: ["Developers", "Evaluation Functions"]
    user_section: ["Teachers, "Evaluation Functions"]
```

**`functions_announce_endpoint`**: Endpoint from which a list of evaluation functions be fetched

**`api_key`** Key to be passed onto the headers of the request ade to the functions announcing endpoint, used to authenticate the request.

**`dev_section`** and **`user_section`**: Paths under which the fetched documentation files should be included, for the developer and teacher-facing files respectively. Thes can be arbirarily long. In this example, developer documentation would be appended to content under the "Developers" section in the "Evaluation Functions" subsection.

## Behaviour

This plugin hooks into three events:

**`on_config`**: After the config is loaded, a list of evaluation functions is fetched the endpoint specified in `functions_announce_endpoint`. Documentation files are fetched from each of the urls returned, and saved to a temporary directory. Successfully downloaded files are then registered to the `nav` config, under the sections specified in `dev_section` and `user_section`.

**`on_files`**: Downloaded files are appended onto the end of the main `mkdocs.structure.files.Files` object

**`on_post_build`**: The created temporary directory is cleaned up

For all events, if a plugin-breaking error occurs, it will be caught and evaluation function documentation fetching is aborted.

## Installing

This package is distributed via **tagged GitHub Releases**, not PyPI. The PyPI
project (`evaldocsloader`, last released `0.1.5` in 2023) is deprecated and no
longer updated — do not install from it.

Pin a released tag in the consuming project:

- **Poetry** (`pyproject.toml`):

  ```toml
  evaldocsloader = { git = "https://github.com/lambda-feedback/EvalDocsLoader.git", tag = "v0.3.0" }
  ```

- **pip** / `requirements.txt`:

  ```
  evaldocsloader @ git+https://github.com/lambda-feedback/EvalDocsLoader.git@v0.3.0
  ```

Tracking `branch = "main"` / `@main` instead of a tag pulls in unreleased code and
should only be done alongside a committed lock file.

## Local development

Preferred:

```bash
poetry install
```

or, with plain pip:

```bash
pip install -e .
```

A small Flask API for testing lives in `testing_api/`. It is not part of the plugin —
it just provides an endpoint to develop against.

## Cutting a release (maintainers)

1. Bump `version` in `pyproject.toml` on `main` and merge.
2. Tag the merge commit and push the tag — it must match `pyproject.toml`:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

3. The [`Release` workflow](.github/workflows/release.yml) verifies the tag against
   `pyproject.toml`, runs `poetry build`, and publishes a GitHub Release with the
   built `sdist`/`wheel` attached. Confirm it under the repo's **Releases** tab.
4. Bump the pinned `tag` in consuming repos (e.g. `user-documentation/pyproject.toml`)
   in a follow-up PR.

### Sources/References

Plugin for loading external markdown files: https://github.com/fire1ce/mkdocs-embed-external-markdown

Template for plugins: https://github.com/byrnereese/mkdocs-plugin-template

File Selection: https://github.com/supcik/mkdocs-select-files

Dealing with new files: https://github.com/oprypin/mkdocs-gen-files/blob/master/mkdocs_gen_files/plugin.py
