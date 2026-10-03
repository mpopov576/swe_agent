from abc import ABC, abstractmethod
from pathlib import Path


class Parser(ABC):
    @abstractmethod
    def parse(self, file_path: Path):
        pass