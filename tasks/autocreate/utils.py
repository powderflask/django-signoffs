from __future__ import annotations
import os
import re
from dataclasses import dataclass, fields

__all__ = [
    'DisplayText',
    'get_fields',
    'render_to_file',
    'get_module_paths',
    'append_or_init',
]


@dataclass
class DisplayText:
    """
    Basic unicode Styling for Text
    """
    silent: bool = False

    H = '\033[95m'  # Header
    BLU = '\033[94m'
    CYN = '\033[96m'
    GRN = '\033[92m'
    WRN = '\033[93m'  # Warning
    F = '\033[91m'  # Fail
    END = '\033[0m'
    B = '\033[1m'  # Bold
    U = '\033[4m'  # Underline

    @classmethod
    def wrap(cls, string: str, *formatters) -> str:  # this fails when the str being wrapped has already been wrapped
        """
        Return the string wrapped in the specified formatters
        """
        start = ''.join([getattr(cls, formatter.upper()) for formatter in formatters if formatter]) or ''
        return f"{start}{string}{cls.END if start else ''}"

    def verbose(self, *args):  # , wrap: list | str = None):
        if not self.silent:
            # if wrap:
            #     if isinstance(wrap, str):
            #         wrap = [wrap]
            #     args = [self.wrap(arg, *wrap) for arg in args]
            print(*args)


def get_fields(data_class, filter_func=None) -> list:
    """
    :param data_class: the dataclass to get fields from
    :param filter_func: Must take a field as input and returns a boolean
    """

    if filter_func:
        return [f.name for f in fields(data_class) if filter_func(f)]
    return [f.name for f in fields(data_class)]


def render_to_file(file_path: str, template: str, env, **kwargs):
    """
    Creates a file from file_path and write the rendered doc_template content to it
    kwargs passed to render
    :param file_path: the file path to write the file to
    :param env: the jinja2 Environment
    :param template: the doc_template file name - must be known by env
    """
    template = env.get_template(template)
    rendered_content = template.render(**kwargs)
    with open(file_path, 'w') as f:
        f.write(rendered_content)


def get_module_paths(from_dir: str, exclude_regexes: list[str]) -> list[str]:
    module_paths = []
    for file_name in os.listdir(from_dir):
        file_path = f"{from_dir}/{file_name}"  # FIXME: below, if pattern doesn't match, it calls .group() on NoneType
        if not exclude_regexes or not any([re.match(pattern, file_path).group() for pattern in exclude_regexes]):
            module_paths.append(file_path)
    return module_paths


def append_or_init(dict_obj: dict[str, list], key: str, val: str) -> None:
    """
    append val to list at key, else initialize a new list with val for key
    """
    if key in dict_obj:
        dict_obj[key].append(val)
    else:
        dict_obj[key] = [val]
