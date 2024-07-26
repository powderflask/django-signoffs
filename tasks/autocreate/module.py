import os
import re
from dataclasses import dataclass


@dataclass
class Module:
    """
    Helper class for documenting a module - from_dict and operations
    """
    file_path: str
    # db_file: str
    doc_file_path: str = None
    name: str = None
    object_paths: dict = None
    # contents: str = None

    def __post_init__(self):
        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"Module could not be initialized because {self.file_path=} does not exist")

        self.name = self.name or self.file_path.split('/')[-1]

    @classmethod
    def init_all_from_dir(cls, from_dir: str, exclude_regexes: list[str]=None) -> list['Module']:
        """
        return a list of Module objs initialized from module paths that aren't matched by a pattern in exclude regexes
        This relies on the ability to initialize a Module instance with only the file_path param
        """
        patterns = [re.compile(pattern) for pattern in exclude_regexes]
        modules = []
        for file_name in os.listdir(from_dir):
            file_path = f"{from_dir}/{file_name}"  # FIXME: below, if pattern doesn't match, it calls .group() on NoneType
            if os.path.isfile(file_path) and (not exclude_regexes or not any([pattern.match(file_path) for pattern in patterns])):
                modules.append(cls(file_path=file_path))
        return modules

    @property
    def get_display_name(self):
        return self.name.replace(".py", "")

    @property
    def dot_path(self) -> str:
        """
        return the file_path as a dot path, excluding the module name if name is `__init__.py`
        """
        if self.name == '__init__.py':
            return self.file_path[:-len(self.name) - 1].replace('/', '.')
        else:
            return self.file_path[:-3].replace('/', '.')
