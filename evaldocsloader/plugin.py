from mkdocs.plugins import BasePlugin
from mkdocs.config import config_options
from mkdocs.structure.files import File

import requests as rq
import os
import tempfile

import logging

try:
    from mkdocs.exceptions import PluginError
except ImportError:
    PluginError = SystemExit

logger = logging.getLogger("mkdocs.plugin.evaldocsloader")


class EvalDocsLoader(BasePlugin):
    config_scheme = (('functions_announce_endpoint',
                      config_options.Type(str, required=True)),
                     (('api_key', config_options.Type(str, required=True))),
                     ('add_to_section', config_options.Type(list,
                                                            required=True)))

    def get_functions_list(self):
        """
        Fetch list of evaluation functions, and their endpoints from a directory url
        """
        root = self.config["functions_announce_endpoint"]
        logger.info(f"Getting list of functions from {root}")

        try:
            # Fetch list of eval function endpoints from url
            res = rq.get(root, headers={'api-key': self.config['api_key']})
            if res.status_code == 200:
                data = res.json()

                # Extract list from response
                func_list = data.get("edges", "Error")

                if func_list == "Error":

                    raise PluginError(
                        f"get_functions_list: {data.get('message', 'list could not be parsed, check api response follows correct format')}"
                    )

                else:
                    logger.info(
                        f"get_functions_list: found {len(func_list)} functions"
                    )
                    return func_list

            else:
                raise PluginError(
                    f"get_functions_list: {root} status code {res.status_code}"
                )

        except Exception as e:
            raise PluginError(e)

    def add_function_docs(self, f, out_dir):
        """
        Sends the 'docs' command to a function using it's endpoint given in `url`
        and saves the file, returning it's path and name
        """
        url = f.get('url', False)
        name = f.get('name', False)

        if not url:
            logger.error("Function missing url field")
            pass

        if not name:
            logger.error(f"Function missing name field")
            pass

        logger.info(f"\tFetching docs for {name}")

        # Files are save to markdown
        out_fileloc = os.path.join(self._docs_dir, name + '.md')
        out_filepath = os.path.join(out_dir, out_fileloc)

        # Fetch docs file from url
        res = rq.get(url, headers={'command': 'docs'})

        if res.status_code == 200:
            with open(out_filepath, 'wb') as file:
                file.write(res.content)

            # Create and append a few file object
            self.newfiles[name] = File(
                out_fileloc,
                out_dir,
                self._config['site_dir'],
                self._config['use_directory_urls'],
            )

        else:
            logger.error(
                f"Function {name}: {root} status code {res.status_code}")

    def update_nav(self, nav, loc):
        """
        Recursive method appends downloaded documentation pages to the nav
        based on the add_to_section parameter
        """
        # Exit contition (we've reached the bottom of the location)
        if len(loc) == 0:
            # Append to the nav location
            if not isinstance(nav, list):
                nav = [nav]

            for k, v in self.newfiles.items():
                nav.append({k: v.src_path})

            self.changed_nav = True
            return nav

        if isinstance(nav, dict):
            return {
                k: v if k != loc[0] else self.update_nav(v, loc[1:])
                for k, v in nav.items()
            }

        elif isinstance(nav, list):
            return [self.update_nav(item, loc) for item in nav]

        else:
            return nav

    def on_config(self, config):
        logger.info("Going to fetch Evaluation Function Documentations")
        self.newfiles = {}
        self.problems = []
        self._config = config

        try:
            # Fetch the list of functions
            func_list = self.get_functions_list()

            # Create a directory in the docs_dir to store fetched files
            self._dir = tempfile.TemporaryDirectory(prefix='mkdocs_eval_docs_')

            # Create a directory within this (to help with better URL generation)
            self._docs_dir = "fetched_eval_function_docs"
            os.mkdir(os.path.join(self._dir.name, self._docs_dir))

            # Request docs from each of the functions, saving files
            # And adding them to the site structure
            for f in func_list:
                self.add_function_docs(f, self._dir.name)

            # Add the docs to the navigation
            self.changed_nav = False
            self._config['nav'] = self.update_nav(
                self._config['nav'], self.config['add_to_section'])

            # Check the path was update succesfully
            if not self.changed_nav:
                raise PluginError("Nav path supplied was not found")

        except PluginError as e:
            logger.error(e.message)
            logger.error("An error occured, gave up on fetching external docs")
            return config

        return self._config

    def on_files(self, files, config):
        # Append all the new fetched files
        for f in self.newfiles.values():
            files.append(f)
        return files

    def on_post_build(self, config):
        try:
            logger.info("Cleaning up downloaded files")
            self._dir.cleanup()
        except AttributeError:
            pass
