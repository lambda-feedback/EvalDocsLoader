
import requests as rq
import os
import tempfile
import logging
import ujson
import concurrent.futures
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from urllib.parse import urljoin

import mistletoe
import mistletoe.span_token
import mistletoe.token
import mistletoe.block_token
import mistletoe.core_tokens
from mistletoe.markdown_renderer import MarkdownRenderer
from mistletoe.base_renderer import BaseRenderer

from github import Github, Auth
from github.Repository import Repository
from github.ContentFile import ContentFile

from .loader_base import DocsLoader, DocsFile, Docs, DocsBundle
from .config import EvalDocsLoaderConfig

logger = logging.getLogger("mkdocs.plugin.evaldocsloader.loader")

@dataclass
class FunctionConfig:
    name: str
    docs_dir: Optional[str]

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
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
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
                result[category] = self._fetch_docs(category, repo, meta, config)
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

    def _fetch_docs(
        self,
        category: str,
        repo: Repository,
        meta: Dict[str, Any],
        config: FunctionConfig,
    ) -> DocsBundle:
        out_dir = self._dir.name

        base_dir = f"{category}_eval_function_docs"

        # the out path is the path used to build the url
        out_path = os.path.join(base_dir, f"{config.name}.md")

        # fetch the documentation file
        file = fetch_docs_file(repo, config.docs_dir, f"{category}.md")

        # determine the actual directory of the file
        actual_docs_path = os.path.dirname(file.path)

        # parse the markdown document
        doc = mistletoe.Document(str(file.decoded_content, "utf-8"))

        link_out_dir = os.path.join(out_dir, base_dir)
        link_loader = _MarkdownLinkLoader(
            repo=repo,
            name=config.name,
            docs_path=actual_docs_path,
            out_dir=link_out_dir
        )
        doc = link_loader.render(doc)

        edit_fn = getattr(self, f"_edit_{category}_docs", None)
        if edit_fn:
            doc = edit_fn(doc, meta)
        else:
            logger.debug(f"No edit function found for {category}")

        # write the rendered markdown to the output file
        out_file_name = os.path.join(out_dir, out_path)
        with open(out_file_name, "wb") as fw:
            with MarkdownRenderer() as renderer:
                out = renderer.render(doc)
                fw.write(bytes(out, "utf-8"))

        edit_uri = f"{repo.html_url}/edit/main/{file.path}"

        return DocsBundle(
            main=DocsFile(path=out_path, dir=out_dir, edit_uri=edit_uri),
            supplementary=[
                DocsFile(path=os.path.join(base_dir, f), dir=out_dir)
                for f in link_loader.files
            ],
        )

    def _edit_user_docs(
        self,
        doc: mistletoe.Document,
        meta: Dict[str, Any],
    ) -> mistletoe.Document:

        # find the index of the first heading in the document
        heading = -1
        for i, token in enumerate(doc.children):
            if isinstance(token, mistletoe.block_token.Heading) and token.level == 1:
                heading = i
                break

        # insert the response areas string after the first root heading
        supported_response_types = meta.get("supportedResponseTypes", [])
        response_areas_content = format_response_areas(supported_response_types)
        doc.children.insert(heading + 1, mistletoe.block_token.Paragraph([response_areas_content]))

        return doc

    def cleanup(self):
        try:
            logger.info("Cleaning up downloaded files")
            self._dir.cleanup()
        except AttributeError:
            pass


def format_response_areas(areas: List[str]) -> str:
    out = []

    if not areas or len(areas) == 0:
        out.append("!!! warning \"Supported Response Area Types\"")
        out.append("    This evaluation function is not configured for any Response Area components")
    else:
        out.append("!!! info \"Supported Response Area Types\"")
        out.append("    This evaluation function is supported by the following Response Area components:")
        out.append("")
        for t in areas:
            out.append(f"      - `{t}`")

    return "\n".join(out)


def fetch_docs_file(repo: Repository, docs_path: Optional[str], file: str) -> ContentFile:
    if docs_path:
        # try to get the file from the specified directory
        docs_path = docs_path.strip("/")
        docs_path = f"{docs_path}/"
        path = urljoin(docs_path, file)
        logger.debug(f"Trying to fetch {path}...")
        return repo.get_contents(path)

    try:
        # try to get the file from the default location
        logger.debug(f"Trying to fetch {file} from default location...")
        return fetch_docs_file(repo, "docs", file)
    except Exception:
        # if the default location does not exist, try the app/docs location
        logger.warning(f"Could not find docs in default location for {repo.name}, trying app/docs...")
        return fetch_docs_file(repo, "app/docs", file)


class _MarkdownLinkLoader(BaseRenderer):
    _repo: Repository
    _name: str
    _docs_path: str
    _out_dir: str
    _files: List[str]

    def __init__(self, repo: Repository, name: str, docs_path: str, out_dir: str) -> None:
        self._repo = repo
        self._name = name
        self._docs_path = docs_path
        self._out_dir = out_dir
        self._files = []
        super().__init__()
    
    def render_inner(self, token: mistletoe.token.Token) -> mistletoe.token.Token:
        if token.children:
            for child in token.children:
                self.render(child)
        return token
    
    @property
    def files(self) -> List[str]:
        return self._files

    def render_image(self, token: mistletoe.span_token.Image) -> mistletoe.span_token.Image:
        token.src = self._fetch(token.src)
        return super().render_image(token)
    
    def render_auto_link(self, token: mistletoe.span_token.AutoLink) -> mistletoe.span_token.AutoLink:
        token.target = self._fetch(token.target)
        return super().render_auto_link(token)
    
    def render_link(self, token: mistletoe.span_token.Link) -> mistletoe.span_token.Link:
        token.target = self._fetch(token.target)
        return super().render_link(token)
    
    def _fetch(self, link_url: str) -> None:
        # only fetch relative links
        if link_url.startswith("http"):
            return link_url

        try:
            # fetch the markdown file
            file = fetch_docs_file(self._repo, self._docs_path, link_url)

            out_file_name = link_url.replace("/", "_")
            out_file_name = f"{self._name}_{out_file_name}"

            out_file_path = os.path.join(self._out_dir, out_file_name)

            with open(out_file_path, "wb") as f:
                f.write(file.decoded_content)

            self._files.append(out_file_name)

            return out_file_name
        except Exception as e:
            logger.warning(f"Failed to fetch supplementary content for {self._name} - {link_url}: {e}")
            return link_url