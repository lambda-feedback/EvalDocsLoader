
import requests as rq
import os
import tempfile
import logging
import ujson
import concurrent.futures
from typing import List, Dict

from github import Github, Auth
from github.Repository import Repository

from .loader_base import DocsLoader, Docs, FunctionConfig
from .config import EvalDocsLoaderConfig
from .loader_fetch import FetchDocsJob

logger = logging.getLogger("mkdocs.plugin.evaldocsloader.loader")

class FunctionLoader(DocsLoader):

    _config: EvalDocsLoaderConfig
    _dir: tempfile.TemporaryDirectory
    _github: Github
    _max_workers: int

    def __init__(self, config: EvalDocsLoaderConfig) -> None:
        if not config.functions_announce_endpoint:
            raise ValueError("Functions announce endpoint not set")
        
        if not config.api_key or config.api_key == "disabled":
            raise ValueError("API key not set")
        
        if not config.github_token:
            raise ValueError("GitHub token not set")
        
        if not config.github_owner:
            raise ValueError("GitHub owner not set")
        
        if not config.github_topic:
            raise ValueError("GitHub repository topic not set")
        
        if not config.max_workers >= 0:
            raise ValueError("Max workers must be greater than or equal to 0")

        self._config = config
        self._max_workers = min(32, config.max_workers if config.max_workers > 0 else (os.cpu_count() or 1) + 4)
        self._github = Github(auth=Auth.Token(config.github_token), pool_size=self._max_workers)

    def load(self) -> List[Docs]:
        logger.info("Fetching Evaluation Function documentation...")

        try:
            # get all of the function repositories
            repos = self._get_functions_repos()

            # get the metadata for the functions
            meta = self._get_functions_meta()

            # create a temporary directory to store the documentation
            self._dir = tempfile.TemporaryDirectory(prefix='mkdocs_eval_docs_')

            # create the directories for the documentation
            for category in ["user", "dev"]:
                os.mkdir(os.path.join(self._dir.name, f"{category}_eval_function_docs"))

            docs = []

            # fetch the documentation for each function
            with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                for doc in pool.map(lambda r: self._fetch_function_docs(r, meta), repos):
                    docs.append(doc)

            return docs
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
    ) -> Docs:
        # get the function config from the repository
        config = self._get_function_config(repo)

        # warn if no metadata is found for the function
        if not meta_map.get(config.name):
            logger.warning(f"No deployed evaluation function found for '{config.name}'")

        meta = meta_map.get(config.name, {})

        result = {}

        for category in ["user", "dev"]:
            try:
                job = FetchDocsJob(category, repo, meta, config, self._dir.name)
                result[category] = job.fetch()
            except Exception as e:
                logger.warning(f"Failed to fetch '{category}' docs for '{repo.name}': {e}")

        return Docs(
            name=config.name,
            user=result.get("user"),
            dev=result.get("dev"),
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

    def cleanup(self):
        try:
            logger.info("Cleaning up downloaded files")
            self._dir.cleanup()
        except AttributeError:
            pass
