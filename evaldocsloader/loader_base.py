from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class FunctionConfig:
    name: str
    docs_dir: Optional[str]

@dataclass
class DocsFile:
    """
    A documentation file
    """

    file_path: str
    """The path to the file"""

    dir: str
    """The directory containing the file"""

    edit_uri: Optional[str] = None
    """The URI to edit the file"""

@dataclass
class DocsBundle:
    """
    A bundle of documentation files
    """

    main: DocsFile
    """The main documentation file"""

    supplementary: List[DocsFile]
    """A list of supplementary documentation files"""

@dataclass
class Docs:
    """
    Documentation files for a single evaluation function
    """

    name: str
    """The name of the bundle (e.g. function name)"""

    dev: Optional[DocsBundle]
    """The developer-facing documentation file"""

    user: Optional[DocsBundle]
    """The user-facing documentation file"""

class DocsLoader(ABC):
    @abstractmethod
    def load(self) -> List[Docs]:
        """Load the documentation files for all evaluation functions

        Returns:
            List[DocsBundle]: A list of documentation bundles
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup any resources used by the loader"""
        pass