import os
import logging
import threading
from urllib.parse import urljoin
from typing import Dict, Optional, List, Any, Tuple, Callable, Set

from github.ContentFile import ContentFile
from github.Repository import Repository

import mistletoe
import mistletoe.ast_renderer
import mistletoe.markdown_renderer
import mistletoe.span_token
import mistletoe.token
import mistletoe.block_token
import mistletoe.core_tokens
from mistletoe.markdown_renderer import MarkdownRenderer
from mistletoe.base_renderer import BaseRenderer

from .loader_base import DocsFile, DocsBundle, FunctionConfig
from autotests import TestFile

logger = logging.getLogger("mkdocs.plugin.evaldocsloader.fetcher")

renderer_lock = threading.Lock()

class FetchDocsJob:
    _category: str
    _repo: Repository
    _meta: Dict[str, Any]
    _config: FunctionConfig
    _out_dir: str
    _base_dir: str
    _link_out_dir: str
    _remote_docs_dir: Optional[str]
    _visited_files: Set[str]
    _test_file: Optional[TestFile]

    def __init__(
        self,
        category: str,
        repo: Repository,
        meta: Dict[str, Any],
        config: FunctionConfig,
        out_dir: str,
    ) -> None:
        self._category = category
        self._repo = repo
        self._meta = meta
        self._config = config
        self._out_dir = out_dir
        self._base_dir = f"{category}_eval_function_docs"
        self._link_out_dir = os.path.join(self._out_dir, self._base_dir)
        self._remote_docs_dir = self._config.docs_dir
        self._visited_files = set()
        self._test_file = None

    def fetch(self) -> DocsBundle:
        results: List[DocsFile] = []

        os.mkdir(os.path.join(self._link_out_dir, self._config.name))

        self._fetch_test_file()
        self._fetch_and_process_file(f"{self._category}.md", f"{self._config.name}.md", results)

        return DocsBundle(
            main=results[0],
            supplementary=results[1:] if len(results) > 1 else [],
        )

    def _edit_url(self, file: ContentFile):
        return f"{self._repo.html_url}/blob/{self._repo.default_branch}/{file.path}"

    def _fetch_and_process_file(
        self,
        remote_file_path: str,
        out_file_path: str,
        results: List[DocsFile],
        level: int = 0
    ) -> None:
        # if we have reached the maximum recursion depth, return
        if level > 4:
            logger.warning(f"Reached maximum recursion depth for '{self._config.name}'")
            return

        # fetch file from the repository
        file = self._fetch_file(remote_file_path)

        # if we have already visited this file, return
        if file.path in self._visited_files:
            return

        # add the file to the visited files
        self._visited_files.add(file.path)

        # set the global docs_dir for future use
        if not self._remote_docs_dir:
            self._remote_docs_dir = os.path.dirname(file.path)

        out_file_path = os.path.join(self._base_dir, out_file_path)

        # process the file and get children
        out_data, links = self._process_file(file)

        # write the file to the output directory
        out_path = os.path.join(self._out_dir, out_file_path)
        with open(out_path, "wb") as fw:
            fw.write(out_data)

        results.append(
            DocsFile(
                dir=self._out_dir,
                file_path=out_file_path,
                edit_uri=self._edit_url(file),
            )
        )

        # fetch and process all children
        for (__remote_file_path, __out_file_path) in links:
            try:
                self._fetch_and_process_file(__remote_file_path, __out_file_path, results, level + 1)
            except Exception as e:
                logger.warning(f"Failed to fetch supplemental '{__remote_file_path}' for '{self._config.name}': {e}")

    def _process_file(self, file: ContentFile) -> Tuple[bytes, List[Tuple[str, str]]]:
        # if the file is not a markdown file, return the content as-is
        if not file.path.lower().endswith(".md"):
            return (file.decoded_content, [])

        # get the content of the file as a string
        content_str = str(file.decoded_content, "utf-8")

        # we have to wrap the whole rendering process in the renderer context as well
        # as synchronize access between all threads we are spinning up because of the
        # way mistletoe handles parsing and rendering:
        #
        # 1) Multithreading support: mistletoe uses a global token index to keep track
        #    of supported tokens, which is not thread-safe. This means that we can't
        #    parse multiple documents at the same time.

        # 2) Rendering context: mistletoe's parser and renderer are tightly coupled,
        #    with the renderer context providing supported tokens to the parser.
        with renderer_lock, MarkdownRenderer() as renderer:
            # parse the markdown document content
            doc = mistletoe.Document(content_str)

            # initilize the link loader. This is a special renderer that will
            # collect all links in and modify them to point to the right location.
            # 
            # NOTE: make sure to never use it as a context manager or any of
            # its functionality, as it will interfere with the renderer context
            link_loader = _MarkdownLinkCollector(
                lambda p: os.path.join(self._config.name, f"{p}".replace("/", "__"))
            )

            # collect and modify all links in the document
            doc = link_loader.render(doc)

            # run any category-specific document modifications
            doc = self._edit_docs(doc, file)

            # render the document to markdown
            out = renderer.render(doc)
            
            return (bytes(out, "utf-8"), link_loader.links)

    def _edit_docs(self, doc: mistletoe.Document, file: ContentFile) -> mistletoe.Document:
        # first, try category-specific edits
        if edit_fn := getattr(self, f"_edit_{self._category}_docs", None):
            doc = edit_fn(doc)
        else:
            logger.debug(f"No edit function found for {self._category}")

        # then, do common edits afterwards
        return self._edit_docs_common(doc, file)

    def _edit_user_docs(self, doc: mistletoe.Document) -> mistletoe.Document:
        # find the index of the first heading in the document
        heading = -1
        for i, token in enumerate(doc.children):
            if isinstance(token, mistletoe.block_token.Heading) and token.level == 1:
                heading = i
                break

        # insert the response areas string after the first root heading
        supported_response_types = self._meta.get("supportedResponseTypes", [])
        response_areas_content = format_response_areas(supported_response_types)
        doc.children.insert(heading + 1, mistletoe.block_token.Paragraph([response_areas_content]))

        # Insert a section at the end with examples auto-generated from tests, if a tests file exists
        if self._test_file:
            logger.info(f"Test file found for {self._repo.name}, generating examples")
            # Append the content to the end of the file
            doc.children.append(mistletoe.block_token.Heading((2, "Auto-Generated Examples", None)))
            for group in self._test_file.groups:
                doc.children.append(mistletoe.block_token.Heading((3, group.get("title"), None)))
                for test in group.get("tests", []):
                    doc.children.append(mistletoe.block_token.Paragraph([test.desc]))
                    doc.children.append(mistletoe.markdown_renderer.BlankLine({}))
                    # Sub tests have the same answer and parameters as a test, but a different response value
                    for sub_test in test.sub_tests:
                        response = sanitise_response(sub_test.response)
                        answer = sanitise_response(test.answer)
                        correct = "✓" if sub_test.is_correct else "✗"
                        
                        if sub_test.desc:
                            doc.children.append(mistletoe.block_token.Paragraph([sub_test.desc]))
                            doc.children.append(mistletoe.markdown_renderer.BlankLine({}))
                        
                        doc.children.append(mistletoe.block_token.Table(([
                            "\n|Response|Answer|Correct?|",
                            "|-|-|-|",
                            f"|`{response}`|`{answer}`|{correct}|",
                        ], 0)))
                        doc.children.append(mistletoe.markdown_renderer.BlankLine({}))

        return doc

    def _edit_docs_common(self, doc: mistletoe.Document, file: ContentFile) -> mistletoe.Document:
        # find the index of the first heading in the document
        heading = -1
        for i, token in enumerate(doc.children):
            if isinstance(token, mistletoe.block_token.Heading) and token.level == 1:
                heading = i
                break

        edit_link = self._edit_url(file)
        repo_link = self._repo.html_url
        edit_content = "\n".join([
            f"[Edit on GitHub :fontawesome-solid-pen-to-square:]({edit_link}){{ .md-button }}",
            f"[View Code :fontawesome-solid-code:]({repo_link}){{ .md-button }}",
            "",
            "---",
            "",
        ])
        doc.children.insert(heading + 1, mistletoe.block_token.Paragraph([edit_content]))

        return doc

    def _fetch_test_file(self):
        """
        Attempts to fetch a file in the repository root called "eval_tests.*", which
        contains a list of tests. If this file is found, it is parsed into a TestFile
        structure and stored in self._test_file.
        """
        root_files = self._repo.get_contents("")
        for root_file in root_files:
            if root_file.name.startswith("eval_tests."):
                test_file_str = str(root_file.decoded_content, "utf-8")
                try:
                    self._test_file = TestFile(test_file_str, root_file.name)
                except Exception as e:
                    logger.warning(f"The test file could not be parsed: {e}")
                # If a TestFile was successfully parsed, it is stored in self._test_file.
                # Otherwise, it is left as None
                return

    def _fetch_file(self, file_path: str, docs_dir: Optional[str] = None) -> ContentFile:
        """
        Fetches a documentation file from the specified directory or the default location.

        Args:
            docs_path (Optional[str]): The path to the docs root, relative to the repository root.
            file (str): The name of the file to fetch.

        Returns:
            ContentFile: The fetched documentation file.

        Raises:
            Exception: If the file cannot be found in the specified directory or the default location.
        """
        # if we have no clue where to look, try to locate the file
        if not docs_dir and not self._remote_docs_dir:
            return self._locate_file(file_path)

        # if we do not have a specific docs_dir, but we have one defined, use that
        if not docs_dir and self._remote_docs_dir:
            docs_dir = self._remote_docs_dir

        # we know we have a docs_dir, so we can try to fetch the file from there
        docs_dir = docs_dir.strip("/")
        docs_dir = f"{docs_dir}/"
        path = urljoin(docs_dir, file_path)

        logger.debug(f"Trying to fetch {path}...")
        content = self._repo.get_contents(path)

        return content

    def _locate_file(self, file_path: str):
        try:
            # try to get the file from the default location
            logger.debug(f"Trying to fetch {file_path} from 'docs'...")
            return self._fetch_file(file_path, "docs")
        except Exception:
            # if the default location does not exist, try the app/docs location
            logger.debug(f"Could not find docs in 'docs', trying 'app/docs'...")
            return self._fetch_file(file_path, "app/docs")

class _MarkdownLinkCollector(BaseRenderer):
    _generate_link: Callable[[str], str]
    _links: List[Tuple[str, str]]

    def __init__(self, generate_link: Callable[[str], str]) -> None:
        # make sure we don't change the renderer's tokens, as supported tokens
        # are managed globally, which will also interfere with the MarkdownRenderer.
        super().__init__()
        self._links = []
        self._generate_link = generate_link
        # TODO: add all other tokens supported by the MarkdownRenderer
        self.render_map["BlankLine"] = self.render_blank_line
    
    def render_inner(self, token: mistletoe.token.Token) -> mistletoe.token.Token:
        if token.children:
            for child in token.children:
                self.render(child)
        return token
    
    @property
    def links(self) -> List[Tuple[str, str]]:
        return self._links

    def render_image(self, token: mistletoe.span_token.Image) -> mistletoe.span_token.Image:
        token.src = self._collect_link(token.src)
        return super().render_image(token)
    
    def render_auto_link(self, token: mistletoe.span_token.AutoLink) -> mistletoe.span_token.AutoLink:
        token.target = self._collect_link(token.target)
        return super().render_auto_link(token)
    
    def render_link(self, token: mistletoe.span_token.Link) -> mistletoe.span_token.Link:
        token.target = self._collect_link(token.target)
        return super().render_link(token)
    
    def render_blank_line(self, token: mistletoe.markdown_renderer.BlankLine) -> mistletoe.markdown_renderer.BlankLine:
        return token
    
    def _collect_link(self, link_url: str) -> None:
        # only fetch relative links
        if link_url.startswith("http"):
            return link_url

        out_link = self._generate_link(link_url)

        self._links.append((link_url, out_link))

        return out_link

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

def sanitise_response(input: str) -> str:
    # When tests are placed in tables, '|' characters delimit table cells.
    # Any '|'s in the input must be escaped.
    return input.replace("|", "\\|")
