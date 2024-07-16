import logging
from typing import Tuple, Any, List, Dict

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files
from mkdocs.exceptions import PluginError


from .loader_base import DocsLoader, DocsFile
from .config import EvalDocsLoaderConfig
from .loader import FunctionLoader

logger = logging.getLogger("mkdocs.plugin.evaldocsloader")

class EvalDocsLoader(BasePlugin[EvalDocsLoaderConfig]):

    _loader: DocsLoader
    _files: List[File] = []

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig | None:
        # after parsing the config, create the loader
        self._loader = FunctionLoader(self.config)

        # load the documentation files
        bundles = self._loader.load()

        results: Dict[str, Dict[str, str]] = {
            "dev": {},
            "user": {}
        }

        files = []

        for bundle in bundles:
            # add the downloaded files to the list of output files
            # and store them in the results dictionary
            if bundle.dev:
                file = _create_mkdocs_file(bundle.dev, config)
                files.append(file)
                results["dev"][bundle.name] = file.src_path
            
            if bundle.user:
                file = _create_mkdocs_file(bundle.user, config)
                files.append(file)
                results["user"][bundle.name] = file.src_path

        # update the nav with the new files
        config.nav = self.update_nav(config.nav, results)

        # store the files for later use
        self._files = files

        return config

    def on_files(self, files: Files, /, *, config: MkDocsConfig) -> Files | None:
        for file in self._files:
            files.append(file)

        return files

    def on_post_build(self, *, _: MkDocsConfig) -> None:
        # cleanup the loader after the build
        self.loader.cleanup()

    def update_nav(self, nav: Any, results: Dict[str, Dict[str, str]]) -> None:
        nav, changed_dev = update_nav_section(nav, self.config.dev_section, results["dev"])
        if not changed_dev:
            raise PluginError("Nav dev_section path not updated")
        
        nav, changed_user = update_nav_section(nav, self.config.user_section, results["user"])
        if not changed_user:
            raise PluginError("Nav user_section path not updated")

        return nav

def update_nav_section(nav: Any, loc: List[str], files: Dict[str, str]) -> Tuple[Any, bool]:
    """
    Recursive method appends downloaded documentation pages in `file` to
    the `nav` object based on the `loc` parameter
    """
    if len(loc) == 0:
        # we found the location to insert the downloaded files

        if not isinstance(nav, list):
            nav = [nav]

        for k, v in files.items():
            nav.append({k: v})

        return nav, True

    if isinstance(nav, dict):
        # build a new dict with the (potentially) updated children
        processed_nav = {
            k: update_nav_section(v, loc[1:], files) if k == loc[0] else (v, False)
            for k, v in nav.items()
        }
        
        # check if any of the children have changed
        changed = any(changed for (_, changed) in processed_nav.values())

        # return the updated dict and whether it has changed
        return {k: v for k, (v, _) in processed_nav.items()}, changed

    elif isinstance(nav, list):
        # build a new list with the (potentially) updated children
        processed_nav = [update_nav_section(item, loc, files) for item in nav]

        # check if any of the children have changed
        changed = any(changed for (_, changed) in processed_nav)

        # return the updated list and whether it has changed
        return [item for (item, _) in processed_nav], changed

    else:
        # return the nav object as-is and that it hasn't changed
        return nav, False
    
def _create_mkdocs_file(file: DocsFile, config: MkDocsConfig) -> File:
    return File(
        path=file.path,
        src_dir=file.dir,
        dest_dir=config.site_dir,
        use_directory_urls=config.use_directory_urls,
    )