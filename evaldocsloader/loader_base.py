from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class DocsFile:
    """
    A documentation file
    """

    path: str
    """The path to the file"""

    dir: str
    """The directory containing the file"""

@dataclass
class DocsBundle:
    """
    A bundle of documentation files for a single evaluation function
    """

    name: str
    """The name of the bundle (e.g. function name)"""

    dev: Optional[DocsFile]
    """The developer-facing documentation file"""

    user: Optional[DocsFile]
    """The user-facing documentation file"""

class DocsLoader(ABC):
    @abstractmethod
    def load(self) -> List[DocsBundle]:
        """Load the documentation files for all evaluation functions

        Returns:
            List[DocsBundle]: A list of documentation bundles
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup any resources used by the loader"""
        pass