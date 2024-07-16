import requests as rq
import os
import tempfile
import logging

from mkdocs.structure.files import File, Files
from mkdocs.exceptions import PluginError

logger = logging.getLogger("mkdocs.plugin.evaldocsloader.loader_function")

from .loader import BaseLoader
from .config import FunctionLoaderConfig

class FunctionLoader(BaseLoader):

    def __init__(self, config: FunctionLoaderConfig) -> None:
        if not config.api_key:
            raise ValueError("Function Loader API key is required")
        
        if not config.announce_endpoint:
            raise ValueError("Function Loader announce endpoint is required")
        
        self.config = config

    def load(self) -> Files:
        logger.info("Going to fetch Evaluation Function Documentations")
        self.newdevfiles = {}
        self.newuserfiles = {}

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
            for f in func_list:
                self.add_function_dev_docs(f)
                self.add_function_user_docs(f)

        except PluginError as e:
            logger.error(e.message)
            logger.error("An error occured, gave up on fetching external docs")
            return config

        return self._config
 
    def get_functions_meta(self):
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
                    f"get_functions_list: status code {res.status_code}"
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
                f"Function {name} status code {res.status_code}"
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
                f"Function {name} status code {res.status_code}"
            )

    # def on_files(self, files, config):
    #     # Append all the new fetched files
    #     for f in self.newdevfiles.values():
    #         files.append(f)
    #     for f in self.newuserfiles.values():
    #         files.append(f)
    #     return files

    def cleanup(self):
        try:
            logger.info("Cleaning up downloaded files")
            self._dir.cleanup()
        except AttributeError:
            pass
