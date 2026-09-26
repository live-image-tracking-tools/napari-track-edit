project = "Napari Track Edit"
copyright = "2024, Howard Hughes Medical Institute"  # noqa: A001
author = "Caroline Malin-Mayor"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
    "autoapi.extension",
    "sphinx_rtd_theme",
    "sphinxcontrib.video",
]
autoapi_dirs = ["../../src/napari_track_edit"]

exclude_patterns = []

suppress_warnings = [
    "ref.python",  # re-exports in __init__.py create duplicate cross-reference targets
]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
# html_static_path = ['_static']
