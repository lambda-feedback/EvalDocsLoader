# MkDocs Plugin: Evaluation Function Documentation Loader
Mkdocs plugin for fetching additional .md files registered in a db before render. Specifically from a web request which returns all the available evaluation functions endpoints.

This plugin was specifially developped for the [LambdaFeedback](https://lambdafeedback.com) platform.

*NOTE: There is currently no safety checking to make sure downloaded markdown files are valid and able to be rendered, they are simply copied over directly from the evaluation function endpoint*

## Configuration 
Enable plugin in the `mkdocs.yml` file:
```yaml
plugins:
  - evaldocsloader:
     gql_root_url: "http://127.0.0.1:5050/testingfunctions"
     add_to_section: ["Authoring Content", "Evaluation Functions"]
```

**`gql_root_url`**: GraphQL Endpoint from which a list of evaluation functions be fetched

**`add_to_section`**: Path under which the fetched documentation files should be included. This can be arbirarily long. In this example, functions would appended to content under the "Authoring Content" section in the "Grading Functions" subsection.

## Behaviour
This plugin hooks into three events:

**`on_config`**: After the config is loaded, a list of evaluation functions is fetched the endpoint specified in `gql_root_url`. Documentation files are fetched from each of the urls returned, and saved to a temporary directory. Successfully downloaded files are then registered to the `nav` config, under the section specified in `add_to_section`.

**`on_files`**: Downloaded files are appended onto the end of the main `mkdocs.structure.files.Files` object

**`on_post_build`**: The created temporary directory is cleaned up

For all events, if a plugin-breaking error occurs, it will be caught and evaluation function documentation fetching is aborted.

## Dev Notes
Package can be installed locally using 
```bash
pip install -e .
```

I've included a small flask api for testing, it's not relevant to the actual plugin - just for development.


### Sources/References

Plugin for loading external markdown files: https://github.com/fire1ce/mkdocs-embed-external-markdown

Template for plugins: https://github.com/byrnereese/mkdocs-plugin-template

File Selection: https://github.com/supcik/mkdocs-select-files

Dealing with new files: https://github.com/oprypin/mkdocs-gen-files/blob/master/mkdocs_gen_files/plugin.py