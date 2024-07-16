import requests as rq
import os
import tempfile
import logging
import ujson
import concurrent.futures
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

from github import Github, Auth
from github.Repository import Repository

from .loader_base import DocsLoader, DocsFile, DocsBundle
from .config import EvalDocsLoaderConfig

logger = logging.getLogger("mkdocs.plugin.evaldocsloader.loader")

@dataclass
class FunctionConfig:
    name: str
    docs_dir: str

@dataclass
class _GatherFunctionResult:
    repos: List[Repository]
    meta: Dict[str, Dict]

class FunctionLoader(DocsLoader):

    _config: EvalDocsLoaderConfig
    _dir: tempfile.TemporaryDirectory
    _github: Github

    def __init__(self, config: EvalDocsLoaderConfig) -> None:
        self._config = config
        self._github = Github(auth=Auth.Token(config.github_token))

        if not config["api_key"] or config.api_key == "disabled":
            raise ValueError("API key disabled, switching plugin off")

    def load(self) -> List[DocsBundle]:
        logger.info("Fetching Evaluation Function documentation...")

        try:
            # get all of the function repositories
            repos = self._get_functions_repos()

            # get the metadata for the functions
            meta = self._get_functions_meta()

            # create a temporary directory to store the documentation
            self._dir = tempfile.TemporaryDirectory(prefix='mkdocs_eval_docs_')

            bundles = []

            # fetch the documentation for each function
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
                for bundle in pool.map(lambda r: self._fetch_function_docs(r, meta), repos):
                    bundles.append(bundle)

            return bundles
        except Exception as e:
            logger.error(f"Could not fetch function documentation: {e}")
            raise e

    def _get_functions_repos(self) -> List[Repository]:
        query = self._github.search_repositories(
            "",
            org=self._config.github_owner,
            topic=self._config.github_topic,
        )

        repos = [repo for repo in query]

        logger.debug(f"Found {len(repos)} function repositories")

        return repos
 
    def _get_functions_meta(self) -> Dict[str, Dict]:
        """
        Fetch list of evaluation functions, and their endpoints from a directory url
        """

        url = self._config.function_announce_endpoint
        logger.info(f"Getting list of functions from {url}")

        res = rq.get(url, headers={'api-key': self.config['api_key']})

        if res.status != 200:
            raise ValueError(f"get_functions_meta: status code {res.status}")
        
        data = res.json()

        func_list = data.get("edges", None)

        if func_list == None:
            message = data.get("message", "list could not be parsed, check api response follows correct format")
            raise ValueError(f"get_functions_meta: {message}")
        
        logger.info(f"get_functions_meta: found {len(func_list)} functions")

        return func_list

    def _fetch_function_docs(
        self,
        repo: Repository,
        meta_map: Dict[str, Dict],
    ) -> DocsBundle:
        # get the function config from the repository
        config = self._get_function_config(repo)

        # warn if no metadata is found for the function
        if not meta_map.get(config.name):
            logger.warn(f"fetch_function_docs: No metadata for {config.name}")

        meta = meta_map.get(config.name, {})

        # create base dir for the function docs
        out_dir = os.path.join(self._dir.name, config.name)
        os.mkdir(out_dir)

        # fetch the documentation
        user = self._fetch_user_docs(repo, meta, config.docs_dir, out_dir)
        dev = self._fetch_dev_docs(repo, meta, config.docs_dir, out_dir)

        return DocsBundle(
            name=config.name,
            user=user,
            dev=dev,
        )

    def _get_function_config(self, repo: Repository) -> FunctionConfig:
        try:
            file = repo.get_contents("config.json")
            config = ujson.loads(file.decoded_content)

            name = config.get("name")
            if not name:
                raise ValueError(f"Failed to get name for {repo.name}")

            return FunctionConfig(
                name=name,
                docs_dir=config.get("docs_dir", "docs"),
            )
        except Exception as e:
            raise ValueError(f"Failed to get config for {repo.name}: {e}")

    def _fetch_user_docs(self, repo: Repository, meta: Dict[str, Any], docs_dir: str, out_dir: str) -> Optional[DocsFile]:

        # fetch the user documentation
        try:
            userDocs = repo.get_contents(f"{docs_dir}/user.md")

            path = os.path.join(out_dir, "user.md")

            supported_response_types = meta.get("supportedResponseTypes", [])
            response_areas_str = format_response_areas(supported_response_types)

            with open(path, "wb") as file:
                file.write(bytes(response_areas_str, "utf-8"))
                file.write(bytes("\n\n", "utf-8"))
                file.write(userDocs.decoded_content)

            return DocsFile(
                path=path,
                dir=out_dir,
            )
        except Exception as e:
            logger.error(f"Failed to get user docs for {f.name}")
            return None
        
    def _fetch_dev_docs(self, repo: Repository, meta: Dict[str, Any], docs_dir: str, out_dir: str) -> Optional[DocsFile]:
        # fetch the developer documentation
        try:
            devDocs = repo.get_contents(f"{docs_dir}/dev.md")

            path = os.path.join(out_dir, "dev.md")

            with open(path, "wb") as file:
                file.write(devDocs.decoded_content)

            return DocsFile(
                path=path,
                dir=out_dir,
            )
        except Exception as e:
            logger.error(f"Failed to get dev docs for {f.name}")
            return None

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

def format_response_areas(areas: List[str]) -> str:
    out = "!!! info \"Supported Response Area Types\"\n"

    if not areas or len(areas) == 0:
        out += "    This evaluation function does not support any Response Area components"
        return out

    out += "    This evaluation function is supported by the following Response Area components:\n\n"
    for t in areas:
        out += f"     - `{t}`\n"
    return out