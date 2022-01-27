# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
# -- Path setup --------------------------------------------------------------
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import datetime
import os
import pathlib
import sys

from sphinx.directives.code import LiteralInclude

try:
    from importlib.metadata import version as pkg_version
except ImportError:
    from importlib_metadata import version as pkg_version

import pytest

try:
    pytest.helpers
except AttributeError:
    from pytest_helpers_namespace.plugin import HelpersRegistry

    pytest.helpers = HelpersRegistry()

try:
    DOCS_BASEPATH = pathlib.Path(__file__).resolve().parent
except NameError:
    # sphinx-intl and six execute some code which will raise this NameError
    # assume we're in the doc/ directory
    DOCS_BASEPATH = pathlib.Path(".").resolve().parent

REPO_ROOT = DOCS_BASEPATH.parent

addtl_paths = (
    DOCS_BASEPATH / "_ext",  # custom Sphinx extensions
    REPO_ROOT / "src",  # saltfactories itself (for autodoc)
)

for addtl_path in addtl_paths:
    sys.path.insert(0, str(addtl_path))

# -- Project information -----------------------------------------------------
this_year = datetime.datetime.today().year
if this_year == 2020:
    copyright_year = 2020
else:
    copyright_year = f"2020 - {this_year}"
project = "PyTest Salt Factories"
copyright = f"{copyright_year}, VMware, Inc."
author = "VMware, Inc."

# The full version, including alpha/beta/rc tags
release = pkg_version("pytest-salt-factories")

# Variables to pass into the docs from sitevars.rst for rst substitution
with open("sitevars.rst") as site_vars_file:
    site_vars = site_vars_file.read().splitlines()

rst_prolog = """
{}
""".format(
    "\n".join(site_vars[:])
)

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx_copybutton",
    # "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinxcontrib.spelling",
    "sphinxcontrib.towncrier",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    ".vscode",
    ".venv",
    ".git",
    ".gitlab-ci",
    ".gitignore",
    "sitevars.rst",
]

autosummary_generate = True
modindex_common_prefix = ["saltfactories."]
master_doc = "contents"
# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"
html_title = project
html_theme_options = {
    "light_logo": "img/SaltProject_altlogo_teal.png",
    "dark_logo": "img/SaltProject_altlogo_teal.png",
    "announcement": (
        "<b>"
        "Documentation is always evolving, but this one hasn't reached it's prime for a 1.0.0 release. "
        "Once we reach that stage, this warning will go away."
        "</b>"
    ),
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# These paths are either relative to html_static_path
# or fully qualified paths (eg. https://...)
html_css_files = [
    "css/inline-include.css",
]

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large. Favicons can be up to at least 228x228. PNG
# format is supported as well, not just .ico'
html_favicon = "_static/img/SaltProject_Logomark_teal.png"

# Sphinx Napoleon Config
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

# ----- Intersphinx Config ---------------------------------------------------------------------------------------->
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pytest": ("https://docs.pytest.org/en/stable/", None),
    "salt": ("https://docs.saltproject.io/en/latest/", None),
    "psutil": ("https://psutil.readthedocs.io/en/latest/", None),
    "coverage": ("https://coverage.readthedocs.io/en/latest/", None),
    "pytestshellutils": ("https://pytest-shell-utilities.readthedocs.io/en/latest/", None),
    "pytestsysstats": ("https://pytest-system-statistics.readthedocs.io/en/latest/", None),
    "pytestskipmarkers": ("https://pytest-skip-markers.readthedocs.io/en/latest/", None),
}
# <---- Intersphinx Config -----------------------------------------------------------------------------------------

# ----- Autodoc Config ---------------------------------------------------------------------------------------------->
autodoc_default_options = {"member-order": "bysource"}
autodoc_mock_imports = ["salt"]
autodoc_typehints = "description"
# <---- Autodoc Config -----------------------------------------------------------------------------------------------


# ----- Towncrier Draft Release ------------------------------------------------------------------------------------->
# Options: draft/sphinx-version/sphinx-release
towncrier_draft_autoversion_mode = "draft"
towncrier_draft_include_empty = True
towncrier_draft_working_directory = REPO_ROOT
# Not yet supported:
# towncrier_draft_config_path = 'pyproject.toml'  # relative to cwd
# <---- Towncrier Draft Release --------------------------------------------------------------------------------------


# ----- Literal Include - Auto Caption ------------------------------------------------------------------------------>


class IncludeExample(LiteralInclude):
    """
    The first argument to the directive is the file path relative to the repository root

    .. code-block:: rst

        .. include-example:: relative/path/to/example.py

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.example_file = self.arguments[0]
        # Get the current doc path relative to the docs directory
        rel_current_source = os.path.relpath(DOCS_BASEPATH, self.state.document.current_source)
        # Now, the passed filename, relative to the current doc, so that including it actually works
        self.arguments[0] = os.path.join(rel_current_source, self.example_file)

    def run(self):
        if "caption" not in self.options:
            self.options["caption"] = self.example_file
        if "name" not in self.options:
            self.options["name"] = self.example_file
        return super().run()


# <---- Literal Include - Auto Caption -------------------------------------------------------------------------------


def setup(app):
    app.add_directive("include-example", IncludeExample)
    app.add_crossref_type(
        directivename="fixture",
        rolename="fixture",
        indextemplate="pair: %s; fixture",
    )
    # Allow linking to pytest's confvals.
    app.add_object_type(
        "confval",
        "pytest-confval",
        objname="configuration value",
        indextemplate="pair: %s; configuration value",
    )
