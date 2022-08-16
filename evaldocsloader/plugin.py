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
    config_scheme = (
        ('functions_announce_endpoint', config_options.Type(str,
                                                            required=True)),
        (('api_key', config_options.Type(str, required=True))),
        ('dev_section', config_options.Type(list, required=True)),
        ('user_section', config_options.Type(list, required=True)),
    )

    def get_functions_list(self):
        """
        Fetch list of evaluation functions, and their endpoints from a directory url
        """
        # If the api_key is "disabled", then exit the plugin
        if self.config['api_key'] == "disabled":
            raise PluginError("API key disabled, switching plugin off")

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

    def add_function_user_docs(self, f):
        """
        Sends the 'docs-user' command to a function using it's endpoint `url`
        save the file, add the function's accepted response areas to markdown
        and append a new mkdocs File to the newuserfiles object
        """
        url = f.get('url', False)
        name = f.get('name', False)
        supported_res_areas = f.get('supportedResponseTypes', [])
        logger.info(f"\tFetching user docs for {name}")

        # Files are saved to markdown
        out_fileloc = os.path.join(self._user_docs_dir, name + '.md')
        out_filepath = os.path.join(self.outdir, out_fileloc)

        # Fetch docs file from url
        res = rq.get(url, headers={'command': 'docs-user'})

        if res.status_code == 200:
            resarea_string = '!!! info "Supported Response Area Types"\n'
            resarea_string += "    This evaluation function is supported by the following Response Area components:\n\n"
            for t in supported_res_areas:
                resarea_string += f"     - `{t}`\n"

            with open(out_filepath, 'wb') as file:
                file.write(bytes(resarea_string, 'utf-8'))
                file.write(res.content)

            # Create and append a few file object
            self.newuserfiles[name] = File(
                out_fileloc,
                self.outdir,
                self._config['site_dir'],
                self._config['use_directory_urls'],
            )

        else:
            logger.error(
                f"Function {name} docs-user: {root} status code {res.status_code}"
            )

    def add_function_dev_docs(self, f):
        """
        Sends the 'docs-dev' command to a function using it's endpoint `url`
        save the file, append a new mkdocs File to the newdevfiles object
        """

        url = f.get('url', False)
        name = f.get('name', False)

        if not url:
            logger.error("Function missing url field")
            pass

        if not name:
            logger.error(f"Function missing name field")
            pass

        logger.info(f"\tFetching developer docs for {name}")

        # Files are saved to markdown
        out_fileloc = os.path.join(self._dev_docs_dir, name + '.md')
        out_filepath = os.path.join(self.outdir, out_fileloc)

        # Fetch docs file from url
        res = rq.get(url, headers={'command': 'docs-dev'})

        if res.status_code == 200:
            with open(out_filepath, 'wb') as file:
                file.write(res.content)

            # Create and append a few file object
            self.newdevfiles[name] = File(
                out_fileloc,
                self.outdir,
                self._config['site_dir'],
                self._config['use_directory_urls'],
            )

        else:
            logger.error(
                f"Function {name} docs-dev: {root} status code {res.status_code}"
            )

    def update_nav(self, nav, loc, files):
        """
        Recursive method appends downloaded documentation pages in `file` to
        the `nav` object based on the `loc` parameter
        """
        # Exit contition (we've reached the bottom of the location)
        if len(loc) == 0:
            # Append to the nav location
            if not isinstance(nav, list):
                nav = [nav]

            for k, v in files.items():
                nav.append({k: v.src_path})

            self.changed_nav = True
            return nav

        if isinstance(nav, dict):
            return {
                k: v if k != loc[0] else self.update_nav(v, loc[1:], files)
                for k, v in nav.items()
            }

        elif isinstance(nav, list):
            return [self.update_nav(item, loc, files) for item in nav]

        else:
            return nav

    def on_config(self, config):
        logger.info("Going to fetch Evaluation Function Documentations")
        self.newdevfiles = {}
        self.newuserfiles = {}
        self.problems = []
        self._config = config

        try:
            # Fetch the list of functions
            func_list = self.get_functions_list()

            # Create a directory in the docs_dir to store fetched files
            self._dir = tempfile.TemporaryDirectory(prefix='mkdocs_eval_docs_')
            self.outdir = self._dir.name

            # Create two directories within this, for dev and user-facing docs
            self._dev_docs_dir = "dev_eval_function_docs"
            self._user_docs_dir = "user_eval_function_docs"
            os.mkdir(os.path.join(self._dir.name, self._dev_docs_dir))
            os.mkdir(os.path.join(self._dir.name, self._user_docs_dir))

            # Request docs from each of the functions, saving files
            # And adding them to the site structure
            for f in func_list:
                self.add_function_dev_docs(f)
                self.add_function_user_docs(f)

            # Add the developer docs to the navigation
            self.changed_nav = False
            self._config['nav'] = self.update_nav(self._config['nav'],
                                                  self.config['dev_section'],
                                                  self.newdevfiles)

            # Check the path was update succesfully
            if not self.changed_nav:
                raise PluginError("Nav dev_section path not found")

            # Add the user docs to the navigation
            self.changed_nav = False
            self._config['nav'] = self.update_nav(self._config['nav'],
                                                  self.config['user_section'],
                                                  self.newuserfiles)

            # Check the path was update succesfully
            if not self.changed_nav:
                raise PluginError("Nav user_section path not found")

        except PluginError as e:
            logger.error(e.message)
            logger.error("An error occured, gave up on fetching external docs")
            return config

        return self._config

    def on_files(self, files, config):
        # Append all the new fetched files
        for f in self.newdevfiles.values():
            files.append(f)
        for f in self.newuserfiles.values():
            files.append(f)
        return files

    def on_post_build(self, config):
        try:
            logger.info("Cleaning up downloaded files")
            self._dir.cleanup()
        except AttributeError:
            pass
