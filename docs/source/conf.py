project = "Motile Tracker"
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
autoapi_dirs = ["../../src/motile_tracker"]

exclude_patterns = []

suppress_warnings = [
    "ref.python",  # re-exports in __init__.py create duplicate cross-reference targets
]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
# html_static_path = ['_static']


# -- Generated keybindings table ---------------------------------------------
# The plugin's shortcuts are defined once, in
# motile_tracker.data_views.keybindings_config.KEYBINDINGS, and the table
# included by key_bindings.rst is rendered from it so the two cannot drift.
KEYBINDINGS_TABLE = "_generated/keybinding_defaults.rst"


def _write_keybindings_table(app=None):
    from pathlib import Path

    from motile_tracker.data_views.keybindings_config import keybindings_rst

    out = Path(__file__).parent / KEYBINDINGS_TABLE
    out.parent.mkdir(exist_ok=True)
    out.write_text(keybindings_rst().rstrip("\n") + "\n")


def setup(app):
    app.connect("builder-inited", _write_keybindings_table)
