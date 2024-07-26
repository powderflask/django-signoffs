from __future__ import annotations
from typing import TYPE_CHECKING
import os
import re
import ast
import json
from tasks.autocreate.utils import append_or_init

if TYPE_CHECKING:
    from tasks.autocreate.module import Module
from icecream import ic


class Resolver:

    def __init__(self, file_path: str, db_path: str):
        self.file_path = file_path
        self.db_path = db_path
        self.module_contents = None
        self.obj_paths = None
        self.invalid_paths = None
        self.json_data = None

    # def get_obj_paths(self):
    #     obj_paths = self.get_obj_import_paths(self.requested_objs)
    #     return {name: obj_paths.get(name) or f"{self.dot_path}.{name}" for name in self.requested_objs}

    def load_module_contents(self, force_reload: bool = False):
        if not self.module_contents or force_reload:
            with open(self.file_path, 'r') as f:
                self.module_contents = f.read()

    def load_json_data(self, force_reload: bool = False):  # TODO: load json data in cfg or autocreate -> avoid reloading for every module
        if not self.json_data or force_reload:
            with open(self.db_path, 'r') as f:
                self.json_data = json.loads(f.read()).get('items')

    @staticmethod
    def construct_dot_path(obj_name, path_from_root: str = None, module_node_path: str = None, level: int = 0) -> str:
        """
        Returns the import path from the content root to the object definition
        :param module_node_path: the dot path provided by asteroids `node.module`
        :param obj_name: the name of the object
        :param level: the number of leading dots in the discovered import
        :param path_from_root:  the path to the current module from the package root
        """
        if path_from_root and not (module_node_path or level):
            module_path = path_from_root.replace('.py', '').replace('/', '.')
            return f"{module_path}.{obj_name}"

        obj_path = f"{module_node_path}.{obj_name}"
        if level:
            dirs = re.findall(r"([^/\\]+)(?=[/\\])", path_from_root)
            if '.' in dirs[-1]:  # discard the last term if it's a file name
                dirs = dirs[:-1]
            obj_path = '.'.join((*dirs[:(None if not 1-level else 1-level)], obj_path))  # avoid using 0 => slice empty
        return obj_path

    @staticmethod
    def guess_file_path(current_file_path: str, guessed_name='__init__.py') -> str:
        """
        Replaces the last term from the current file_path with the `guessed_name`
        "Guess" the file path to the module containing the import statement for an object
        """

        current_file_name = current_file_path.rsplit('/')[-1]
        path = current_file_path[:-len(current_file_name)]
        return path + guessed_name

    @staticmethod
    def pop_invalid_paths(from_dict: dict[any, any], to_dict: dict[str, str]) -> dict[str, str]:
        """
        Modifies the `obj_paths` by removing all paths that don't exist as keys in the db items

        :returns: a dict holding all paths in `obj_paths` not found in the db
        """
        invalid_paths = {name: to_dict.pop(name)
                         for name, path in to_dict.copy().items()
                         if not from_dict.get(path)}
        return invalid_paths

    def list_objs_from_var(self, target_var: str = "__all__") -> list:
        """
        Return a list of objects found ONLY in the first assignment to target_var in the module
        """
        self.load_module_contents()
        tree = ast.parse(self.module_contents)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == target_var and isinstance(node.value, ast.List):
                        return [elt.s for elt in node.value.elts if isinstance(elt, ast.Str)]

    def get_obj_import_paths(self, contents: str=None, path: str=None, from_list: list = None) -> dict[str, str]:
        """
        Get the import path for objects in "matches" if it exists, otherwise get all object import paths
        """

        contents = contents or self.module_contents
        path = path or self.file_path

        obj_paths = {}
        tree = ast.parse(contents)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    obj_name = alias.asname or alias.name
                    if not from_list or obj_name in from_list:
                        module_dot_path = getattr(node, 'module', '')
                        level = getattr(node, 'level', '')
                        obj_paths[obj_name] = self.construct_dot_path(obj_name=obj_name,
                                                                      path_from_root=path,
                                                                      module_node_path=module_dot_path,
                                                                      level=level)

        return obj_paths

    def resolve_module(self, target_var: str = "__all__", max_recursion=3):
        """
        Get the full import path for each object in this module's `__all__`
        :returns: obj_dict
        """
        self.load_module_contents()
        self.load_json_data()

        target_objs = self.list_objs_from_var(target_var=target_var)
        if not target_objs:
            return {}

        self.obj_paths = self.get_obj_import_paths(from_list=target_objs)
        self.obj_paths.update(
            **{obj: self.construct_dot_path(obj_name=obj, path_from_root=self.file_path)
               for obj in target_objs
               if obj not in self.obj_paths.keys()}
        )
        self.invalid_paths = self.pop_invalid_paths(self.json_data, self.obj_paths)
        if not self.invalid_paths or not self.obj_paths:
            return self.obj_paths
        bad_file_paths = {}

        attempt = 0
        while attempt <= max_recursion:
            attempt += 1
            good_file_paths = {}
            for obj, path in self.invalid_paths.items():
                guess = self.guess_file_path(path)
                if os.path.isfile(guess):
                    append_or_init(good_file_paths, guess, obj)
                else:
                    append_or_init(bad_file_paths, guess, obj)

            self.invalid_paths.clear()

            for file_path, objs in good_file_paths:
                with open(file_path, 'r') as f:
                    contents = f.read()
                found_paths = self.get_obj_import_paths(contents, file_path, from_list=objs)
                invalid = self.pop_invalid_paths(self.json_data, found_paths)
                self.obj_paths.update(**found_paths)
                self.invalid_paths.update(**invalid)

            if not self.invalid_paths or attempt == max_recursion:
                break
        return self.obj_paths  # TODO: return bad_guesses too?
