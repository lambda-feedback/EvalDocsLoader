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