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
autoapi_add_toctree_entry = False  # listed explicitly in the index toctree

# _key_bindings.md is a fragment, included in key_bindings.rst and the tutorial
exclude_patterns = ["_key_bindings.md"]

suppress_warnings = [
    "ref.python",  # re-exports in __init__.py create duplicate cross-reference targets
    "myst.header",  # the included _key_bindings.md starts at ### headings
]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "images/logo_transparent.png"


# -- Generated keybindings table ---------------------------------------------
# The plugin's shortcuts are defined once, in
# napari_track_edit.data_views.keybindings_config.KEYBINDINGS, and the table
# included by key_bindings.rst is rendered from it so the two cannot drift.
KEYBINDINGS_TABLE = "_generated/keybinding_defaults.rst"


def _write_keybindings_table(app=None):
    from pathlib import Path

    from napari_track_edit.data_views.keybindings_config import keybindings_rst

    out = Path(__file__).parent / KEYBINDINGS_TABLE
    out.parent.mkdir(exist_ok=True)
    out.write_text(keybindings_rst().rstrip("\n") + "\n")


# -- Tutorial images ---------------------------------------------------------
# The tutorial (napari-track-edit_tutorial.md) is also exported to PDF, so it lays out
# its figures with raw HTML <img src="images/...">. Sphinx only copies images that are
# referenced through directives, so copy the images folder next to the built pages.
def _copy_tutorial_images(app, exception):
    import shutil
    from pathlib import Path

    if exception is None and app.builder.format == "html":
        src = Path(app.srcdir) / "images"
        shutil.copytree(src, Path(app.outdir) / "images", dirs_exist_ok=True)


# -- Tutorial includes -------------------------------------------------------
# The tutorial embeds other markdown files with the include syntax of the VS Code
# 'Markdown PDF' extension, :[label](file.md), which MyST does not know. Expand those
# includes when the tutorial is read, so that the docs page matches the PDF.
def _expand_markdown_includes(app, docname, source):
    import re
    from pathlib import Path

    if docname != "napari-track-edit_tutorial":
        return

    def include(match):
        path = Path(app.srcdir) / match.group(1)
        app.env.note_dependency(str(path))  # rebuild the tutorial when it changes
        return path.read_text()

    source[0] = re.sub(
        r"^:\[[^\]]*\]\(\s*(\S+?\.md)\s*\)$", include, source[0], flags=re.MULTILINE
    )
    # the stylesheet at the top only styles the PDF export, and is not published
    source[0] = re.sub(
        r"^<link rel=\"stylesheet\"[^>]*>\n", "", source[0], flags=re.MULTILINE
    )


def setup(app):
    app.connect("builder-inited", _write_keybindings_table)
    app.connect("source-read", _expand_markdown_includes)
    app.connect("build-finished", _copy_tutorial_images)
