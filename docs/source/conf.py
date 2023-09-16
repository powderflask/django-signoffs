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
version = "0.4.0"
# The full version, including alpha/beta/rc tags.
release = "0.4.0"

# The master toctree document.
master_doc = "index"

# The suffix(es) of source filenames.
source_suffix = [".rst", ".md"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "autodoc2",
    "sphinx.ext.napoleon",
    "sphinxcontrib_django",
]

myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
    "linkify",
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = "sphinx_rtd_theme"
html_theme = "furo"
html_theme_options = {
    "source_repository": "https://github.com/powderflask/django-signoffs",
    "source_branch": "master",
    # "announcement": "<b>v0.3.0</b> is now out! See the Changelog for details",
}

# -- Options for autodoc2 -------------------------------------------------
# https://sphinx-autodoc2.readthedocs.io/en/latest/
autodoc2_render_plugin = "myst"
autodoc2_packages = [
    {
        "path": "../../signoffs",
        "auto_mode": False,
    },
]
autodoc2_module_all_regexes = [
    r"signoffs.core.approvals",
    r"signoffs.core.forms",
    r"signoffs.core.signoffs",
    r"signoffs.core.utils",
    r"signoffs.core.signing_order\..*",
    r"signoffs.registry",
]
