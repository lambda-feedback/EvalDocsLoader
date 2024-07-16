from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from mkdocs.structure.files import File

@dataclass
class DocsBundle:
    """
    A bundle of documentation files for a single evaluation function
    """

    name: str
    """The name of the bundle (e.g. function name)"""

    dev: Optional[File]
    """The developer-facing documentation file"""

    user: Optional[File]
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