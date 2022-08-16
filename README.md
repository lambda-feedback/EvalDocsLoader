# MkDocs Plugin: Evaluation Function Documentation Loader
Mkdocs plugin for fetching additional .md files registered in a db before render. Specifically from a web request which returns all the available evaluation functions endpoints.

This plugin was specifially developped for the [LambdaFeedback](https://lambdafeedback.com) platform.

*NOTE: There is currently no safety checking to make sure downloaded markdown files are valid and able to be rendered, they are simply copied over directly from the evaluation function endpoint*

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