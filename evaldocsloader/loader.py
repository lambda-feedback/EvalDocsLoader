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
from github.ContentFile import ContentFile

from .loader_base import DocsLoader, DocsFile, DocsBundle
from .config import EvalDocsLoaderConfig

logger = logging.getLogger("mkdocs.plugin.evaldocsloader.loader")

@dataclass
class FunctionConfig:
    name: str
    docs_dir: Optional[str]

@dataclass
class _GatherFunctionResult:
    repos: List[Repository]
    meta: Dict[str, Dict]

class FunctionLoader(DocsLoader):

    _config: EvalDocsLoaderConfig
    _dir: tempfile.TemporaryDirectory
    _github: Github

    def __init__(self, config: EvalDocsLoaderConfig) -> None:
        if not config.functions_announce_endpoint:
            raise ValueError("Functions announce endpoint not set")
        
        if not config.api_key or config.api_key == "disabled":
            raise ValueError("API key disabled, switching plugin off")
        
        if not config.github_token:
            raise ValueError("Github token not set")
        
        if not config.github_owner:
            raise ValueError("Github owner not set")
        
        if not config.github_topic:
            raise ValueError("Github repository topic not set")

        self._config = config
        self._github = Github(auth=Auth.Token(config.github_token))

    def load(self) -> List[DocsBundle]:
        logger.info("Fetching Evaluation Function documentation...")

        logger

        try:
            # get all of the function repositories
            repos = self._get_functions_repos()

            # get the metadata for the functions
            meta = self._get_functions_meta()

            # create a temporary directory to store the documentation
            self._dir = tempfile.TemporaryDirectory(prefix='mkdocs_eval_docs_')

            os.mkdir(os.path.join(self._dir.name, "deployed_functions"))

            bundles = []

            # fetch the documentation for each function
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                for bundle in pool.map(lambda r: self._fetch_function_docs(r, meta), repos):
                    bundles.append(bundle)

            return bundles
        except Exception as e:
            raise e

    def _get_functions_repos(self) -> List[Repository]:
        logger.info(f"Getting evaluation function repositories for topic {self._config.github_topic} in {self._config.github_owner}")

        query = self._github.search_repositories(
            f"org:{self._config.github_owner} topic:{self._config.github_topic}",
        )

        repos = [repo for repo in query]

        logger.debug(f"Found {len(repos)} function repositories")

        return repos
 
    def _get_functions_meta(self) -> Dict[str, Dict]:
        """
        Fetch list of evaluation functions, and their endpoints from a directory url
        """

        url = self._config.functions_announce_endpoint
        logger.info(f"Getting deployed evaluation functions from {url}")

        res = rq.get(url, headers={"api-key": self._config.api_key})

        if res.status_code != 200:
            raise ValueError(f"Coud not fetch functions list: {res.status_code} {res.text}")
        
        data = res.json()

        func_list = data.get("edges", None)

        if not func_list:
            raise ValueError(data.get("message", "list could not be parsed, check api response follows correct format"))
        
        logger.info(f"Found {len(func_list)} deployed evaluation functions")

        return {meta["name"]: meta for meta in func_list}

    def _fetch_function_docs(
        self,
        repo: Repository,
        meta_map: Dict[str, Dict],
    ) -> DocsBundle:
        # get the function config from the repository
        config = self._get_function_config(repo)

        # warn if no metadata is found for the function
        if not meta_map.get(config.name):
            logger.warning(f"No deployed evaluation function found for '{config.name}'")

        meta = meta_map.get(config.name, {})

        base_path = os.path.join("deployed_functions", config.name)

        out_dir = self._dir.name

        # create base dir for the function docs
        os.mkdir(os.path.join(out_dir, base_path))

        user = None
        user_out_path = os.path.join(base_path, "user.md")
        user_out_file = os.path.join(out_dir, user_out_path)
        try:
            self._fetch_user_docs(repo, meta, config.docs_dir, user_out_file)
            user = DocsFile(path=user_out_path, dir=out_dir)
        except Exception as e:
            logger.warning(f"Failed to fetch 'user' docs for '{repo.name}': {e}")

        dev = None
        dev_out_path = os.path.join(base_path, "dev.md")
        dev_out_file = os.path.join(out_dir, dev_out_path)
        try:
            self._fetch_dev_docs(repo, meta, config.docs_dir, dev_out_file)
            dev = DocsFile(path=dev_out_path, dir=out_dir)
        except Exception as e:
            logger.warning(f"Failed to fetch 'dev' docs for '{repo.name}': {e}")

        return DocsBundle(
            name=config.name,
            user=user,
            dev=dev,
        )

    def _get_function_config(self, repo: Repository) -> FunctionConfig:
        try:
            file = repo.get_contents("config.json")
            config = ujson.loads(file.decoded_content)

            name = config.get("EvaluationFunctionName")
            if not name:
                raise ValueError(f"Could not get function name")

            return FunctionConfig(
                name=name,
                docs_dir=config.get("docs_dir", None),
            )
        except Exception as e:
            raise ValueError(f"Failed to get function config for {repo.name}", e)

    def _fetch_user_docs(
        self,
        repo: Repository,
        meta: Dict[str, Any],
        remote_dir: Optional[str],
        out_file: str,
    ) -> None:
        userDocs = self._fetch_docs(repo, remote_dir, "user.md")

        supported_response_types = meta.get("supportedResponseTypes", [])
        response_areas_str = format_response_areas(supported_response_types)

        with open(out_file, "wb") as file:
            file.write(bytes(response_areas_str, "utf-8"))
            file.write(bytes("\n\n", "utf-8"))
            file.write(userDocs.decoded_content)
        
    def _fetch_dev_docs(
        self,
        repo: Repository,
        meta: Dict[str, Any],
        remote_dir: Optional[str],
        out_file: str,
    ) -> None:
        devDocs = self._fetch_docs(repo, remote_dir, "dev.md")

        with open(out_file, "wb") as file:
            file.write(devDocs.decoded_content)

    def cleanup(self):
        try:
            logger.info("Cleaning up downloaded files")
            self._dir.cleanup()
        except AttributeError:
            pass

    def _fetch_docs(self, repo: Repository, docs_dir: Optional[str], file: str) -> ContentFile:
        if docs_dir:
            # try to get the file from the specified directory
            logger.debug(f"Trying to fetch {file} from {docs_dir}")
            return repo.get_contents(f"{docs_dir}/{file}")

        try:
            # try to get the file from the default location
            return self._fetch_docs(repo, "docs", file)
        except Exception:
            # if the default location does not exist, try the app/docs location
            logger.warning(f"Could not find docs in default location for {repo.name}, trying app/docs")
            return self._fetch_docs(repo, "app/docs", file)

def format_response_areas(areas: List[str]) -> str:
    if not areas or len(areas) == 0:
        out = "!!! warning \"Supported Response Area Types\"\n"
        out += "    This evaluation function is not configured for any Response Area components"
        return out

    out = "!!! info \"Supported Response Area Types\"\n"
    out += "    This evaluation function is supported by the following Response Area components:\n\n"
    for t in areas:
        out += f"     - `{t}`\n"
    return out