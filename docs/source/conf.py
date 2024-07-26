# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
sys.path.insert(0, os.path.abspath("../../"))

django_settings = "tests.settings"

project = "Django Signoffs"
copyright = "2022, Joseph Fall"
author = "Joseph Fall"

# The short X.Y version.
version = "0.3.9"
# The full version, including alpha/beta/rc tags.
release = "0.3.9"

# The master toctree document.
master_doc = "home"

# The suffix(es) of source filenames.
source_suffix = [".md", ".rst"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    # 'sphinx.ext.autodoc',
    "autodoc2",
    "sphinx.ext.napoleon",
    "sphinxcontrib_django",
    'sphinx_subfigure',
]

myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
    "linkify",
]

templates_path = ["_templates"]
exclude_patterns = [
    'templates'
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = "sphinx_book_theme"
html_theme = "furo"
html_theme_options = {
    "source_repository": "https://github.com/powderflask/django-signoffs",
    "source_branch": "master",
    # "announcement": "<b>v0.3.0</b> is now out! See the Changelog for details",
}

# -- Options for autodoc --------------------------------------------------
autodoc2_default_options = dict(import_members=True) # TODO: I need imported members to be documented, was looking at the source code for autodoc2. Can't use any autodoc config

# -- Options for autodoc2 -------------------------------------------------
# https://sphinx-autodoc2.readthedocs.io/en/latest/
autodoc2_render_plugin = "myst"
autodoc2_packages = [
    {
        "path": "../../signoffs",
        "auto_mode": False,
            # "exclude_dirs": ["contrib",
            #                  "core",
            #                  "static",
            #                  "templates",
            #                  "templatetags"],
    },
]
# autodoc2_module_all_regexes = [
#     r"signoffs.signoffs",
#     r"signoffs.approvals",
#     r"signoffs.models"
#     r"signoffs.forms",
#     r"signoffs.registry",
#     r"signoffs.process",
#     r"signoffs.signing_order",
#     r"signoffs.shortcuts",
#     r"signoffs.views",
# ]

# if a path isn't valid, manually fix it after seeing the sphinx warning during generation
autocreate_options = dict(
    package_root='signoffs',  # REQUIRED
    package_name='signoffs',
    ignore_files=[
        "__init__",
        "urls",
    ],
    template_dir="docs/source/templates",
    template="autocreate_template.md",
    index_template="index_template.md",
    exclude_regexes=[r'signoffs/\w+/\w+'],
    # only_render_valid_object_paths=False,
    get_from__all__=True,
)
