"""Tests for the plugin's keybindings panel and the plumbing behind it.

The point of these is that a rebind has to reach four places at once - napari's
settings, the layer keymaps that actually dispatch, the Qt widgets' own dispatch
tables and the button captions - so most tests here check a rebind end to end
rather than one layer of it.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from napari.settings import get_settings
from napari.utils.action_manager import action_manager
from napari.utils.key_bindings import KeymapHandler, coerce_keybinding
from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QKeySequence

from napari_track_edit.application_menus.editing_selection_menu import EditingMenu
from napari_track_edit.application_menus.keybindings_widget import (
    KeybindingsWidget,
    ShortcutEdit,
    open_keybindings_panel,
)
from napari_track_edit.application_menus.welcome_widget import (
    DOCS_URL,
    KEYBINDINGS_LINK,
    WelcomeWidget,
)
from napari_track_edit.data_views.keybindings_config import (
    CMD,
    KEYBINDINGS,
    SHORTCUTS,
    current_general_key_actions,
    current_shortcuts,
    format_shortcut,
    keybindings_rst,
    set_shortcut,
    shortcut_text,
)
from napari_track_edit.data_views.views_coordinator.tracks_viewer import TracksViewer


@pytest.fixture
def loaded(make_napari_viewer, solution_tracks_3d_with_division):
    """A viewer with tracks, its TracksViewer, and the editing menu.

    Uses `make_napari_viewer` to match the rest of tests/application_menus;
    see tests/data_views/conftest.py for why the two viewer fixtures must not
    be mixed within a session.
    """
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks=solution_tracks_3d_with_division, name="test")
    return viewer, tracks_viewer, EditingMenu(viewer)


def _handler_for(layer, viewer, key):
    """Name of whatever napari would actually run for `key` with `layer` active.

    Compared by qualified name rather than identity: napari wraps each keymap
    entry, so the value is not the bound method that was registered.
    """
    handler = KeymapHandler()
    handler.keymap_providers = [layer, viewer]
    found = handler.active_keymap.get(coerce_keybinding(key))
    if found is None:
        return None
    found = getattr(found, "func", found)
    return f"{getattr(found, '__module__', '')}.{getattr(found, '__qualname__', found)}"


TRACKS_VIEWER = (
    "napari_track_edit.data_views.views_coordinator.tracks_viewer.TracksViewer"
)


def _qt_action(key: int, modifiers: int = 0) -> str | None:
    return current_general_key_actions().get((key, modifiers))


def test_shortcuts_are_spelled_out_not_glyphs():
    """Captions use key names, not the platform's glyphs, so they read the same
    everywhere and match what the keybindings panel shows."""

    assert format_shortcut("shift+a") == "Shift+A"
    assert format_shortcut("Escape") == "Esc"
    assert format_shortcut("Delete") == "Del"
    assert "⇧" not in format_shortcut("shift+a")  # no ⇧
    assert "⌦" not in format_shortcut("Delete")  # no ⌦


def test_docs_table_covers_every_action_platform_neutrally():
    """The docs table is generated, so it cannot drift from KEYBINDINGS - and it
    must not name modifiers after whichever machine built the docs."""

    table = keybindings_rst()
    for config in KEYBINDINGS.values():
        assert config["description"] in table
    # no modifier named after the machine that built the docs
    assert "Option" not in table
    assert "Cmd+" not in table.replace("Ctrl/Cmd+", "")


def test_button_caption_follows_a_rebind(loaded):
    """A caption must show the key that is bound now, not the default it was
    written with."""

    _, _, menu = loaded
    assert menu.connect_nodes_btn.text() == "Connect [C]"
    assert "[Shift+C]" in menu.connect_nodes_btn.toolTip()

    set_shortcut("connect_nodes_with_divisions", "shift+e")
    set_shortcut("connect_nodes_linearly", "alt+c")

    assert menu.connect_nodes_btn.text() == "Connect [Shift+E]"
    tooltip = menu.connect_nodes_btn.toolTip()
    assert "[Shift+E]" in tooltip
    assert f"[{shortcut_text('connect_nodes_linearly')}]" in tooltip


def test_rebind_moves_napari_and_qt_dispatch_together(loaded):
    """The three things a key press can go through have to agree: the layer
    keymap, the Qt widgets' table, and the caption."""

    viewer, tracks_viewer, menu = loaded
    layer = tracks_viewer.tracking_layers.points_layer
    undo = f"{TRACKS_VIEWER}.undo"

    assert _handler_for(layer, viewer, "z") == undo
    assert _qt_action(ord("Z")) == "undo"

    set_shortcut("undo", "ctrl+u")

    assert _handler_for(layer, viewer, "ctrl+u") == undo
    assert _handler_for(layer, viewer, "z") != undo  # released back to napari
    assert _qt_action(ord("Z")) != "undo"
    assert "undo" in current_general_key_actions().values()
    assert menu.undo_btn.text() == f"Undo [{format_shortcut('ctrl+u')}]"


def test_modifier_combos_reach_qt_dispatch(loaded):
    """A modifier combo has to survive the trip into the Qt table.

    Regression test: the shortcut is stored in napari's spelling, which
    QKeySequence reads as Qt's. The two disagree on macOS - napari's "Ctrl" is
    literal Control, Qt's is Command - so parsing it the Qt way bound the
    other modifier, and a chord needed one key in the canvas and a different
    one in the tree view and table.
    """

    set_shortcut("undo", "ctrl+alt+u")

    entries = [k for k, v in current_general_key_actions().items() if v == "undo"]
    assert entries, "ctrl+alt+u did not reach the Qt dispatch table"
    key, modifiers = entries[0]
    assert key == ord("U")
    assert modifiers == int(
        (
            # Qt calls the physical Control key "Meta" on macOS
            Qt.MetaModifier if sys.platform == "darwin" else Qt.ControlModifier
        ).value
        | Qt.AltModifier.value
    )


def test_redo_chord_is_the_platforms_command_key(loaded):
    """The second redo binding must be the chord the platform actually uses -
    Cmd+Shift+Z on macOS, Ctrl+Shift+Z elsewhere - and the canvas and the Qt
    widgets must agree on which physical keys that is."""

    viewer, tracks_viewer, _menu = loaded
    layer = tracks_viewer.tracking_layers.points_layer

    chord = current_shortcuts("redo")[1]
    expected = "Cmd+Shift+Z" if sys.platform == "darwin" else "Ctrl+Shift+Z"
    assert format_shortcut(chord) == expected

    assert _handler_for(layer, viewer, chord) == f"{TRACKS_VIEWER}.redo"

    command = Qt.ControlModifier  # Cmd on macOS, Ctrl elsewhere - as Qt sees it
    combo = (int(Qt.Key_Z), int((command | Qt.ShiftModifier).value))
    assert current_general_key_actions().get(combo) == "redo"


def test_docs_name_the_command_modifier_for_every_platform(loaded):
    """The docs are read everywhere, so the chord is written "Ctrl/Cmd" rather
    than resolved to whichever machine built them."""

    assert "Ctrl/Cmd+Shift+Z" in keybindings_rst()


def test_panel_rebind_clears_the_conflicting_plugin_action(loaded):
    """Taking a key another plugin action owns is allowed, and clears it there.

    Refusing the edit is what makes napari's dialog unusable for this, and one
    key cannot drive two plugin actions anyway.
    """

    _, _, _menu = loaded
    panel = KeybindingsWidget()

    panel._editors["undo"].setKeySequence(QKeySequence("D"))
    panel._commit("undo")

    assert current_shortcuts("undo") == ["D"]
    # delete_node's editable key is cleared; its fixed extra [Delete] stays
    assert current_shortcuts("delete_node") == ["Delete"]
    assert "Delete the selected nodes" in panel._status.text()


def test_panel_reports_but_does_not_refuse_a_napari_collision(loaded):
    """A collision with napari is information: we shadow it on purpose."""

    _, _, _menu = loaded
    panel = KeybindingsWidget()

    # "p" is napari's activate_points_add_mode
    panel._editors["undo"].setKeySequence(QKeySequence("P"))
    panel._commit("undo")

    assert current_shortcuts("undo") == ["P"]
    assert "napari" in panel._status.text()


def test_panel_clear_unbinds_without_falling_back_to_the_default(loaded):
    """An action the user cleared has to stay cleared."""

    _, _, _menu = loaded
    panel = KeybindingsWidget()

    panel._editors["undo"].setKeySequence(QKeySequence())
    panel._commit("undo")

    assert current_shortcuts("undo") == []
    assert shortcut_text("undo") == ""


def test_panel_restore_defaults_only_touches_our_actions(loaded):
    """Our reset must not disturb napari's own shortcuts."""

    _, _, _menu = loaded
    panel = KeybindingsWidget()
    napari_before = dict(action_manager._shortcuts).get("napari:reset_view")

    set_shortcut("undo", "ctrl+u")
    panel._restore_defaults()

    assert current_shortcuts("undo") == ["Z"]
    assert dict(action_manager._shortcuts).get("napari:reset_view") == napari_before


def test_napari_restore_all_leaves_our_shortcuts_alone(loaded):
    """napari's "Restore All Keybindings" resets its own settings. Ours live in
    our own file, so the user's choices survive it untouched."""

    _, _tracks_viewer, menu = loaded
    set_shortcut("connect_nodes_with_divisions", "shift+e")

    get_settings().shortcuts.reset()

    assert current_shortcuts("connect_nodes_with_divisions") == ["Shift+E"]
    assert menu.connect_nodes_btn.text() == "Connect [Shift+E]"


def test_overrides_survive_a_reload(loaded):
    """A rebind is written to disk, not just held in memory."""

    _, _, _menu = loaded
    set_shortcut("undo", "ctrl+alt+u")

    SHORTCUTS._overrides = None  # next read comes from the file

    assert current_shortcuts("undo") == ["Ctrl+Alt+U"]


def test_picking_an_actions_own_fixed_extra_does_not_duplicate_it(loaded):
    """redo is always bound to the platform's redo chord; choosing that as its
    editable key too must not list it twice."""

    _, _, _menu = loaded
    set_shortcut("redo", f"{CMD}+shift+z")

    assert len(current_shortcuts("redo")) == 1


def test_panel_is_reused_rather_than_stacked(loaded):
    """The panel is non-modal, so reopening it must not pile up windows."""

    _, _, menu = loaded

    first = open_keybindings_panel(menu)
    second = open_keybindings_panel(menu)

    assert first is second


def test_committed_docs_table_is_up_to_date():
    """The docs table is generated from KEYBINDINGS and committed, so it reads
    correctly on GitHub and in a PR diff rather than only after a docs build.
    Regenerate it with `just docs-build` when the table changes.

    Compares the content rather than the exact bytes: the end-of-file-fixer
    pre-commit hook normalizes trailing newlines, so a byte-for-byte check
    fails in CI on a file the hook has touched.
    """

    generated = (
        Path(__file__).parents[2]
        / "docs"
        / "source"
        / "_generated"
        / "keybinding_defaults.rst"
    )

    assert generated.read_text().rstrip("\n") == keybindings_rst().rstrip("\n")


def test_keybindings_is_a_link_that_opens_the_panel(qtbot):
    """The Keybindings entry sits in the Getting Started links row as a real
    anchor, so it matches its neighbours, and opens the panel rather than
    navigating - which, with a scheme Qt cannot resolve, would blank the
    document."""

    welcome = WelcomeWidget(None)
    qtbot.addWidget(welcome)

    assert KEYBINDINGS_LINK in welcome.links.toHtml()
    assert not welcome.links.openLinks()

    welcome._on_link_clicked(QUrl(KEYBINDINGS_LINK))

    assert isinstance(welcome._track_edit_keybindings_panel, KeybindingsWidget)
    assert KEYBINDINGS_LINK in welcome.links.toHtml()  # still showing the links


def test_other_links_still_open_in_a_browser(qtbot):
    """Taking over link handling must not break the ordinary links."""

    welcome = WelcomeWidget(None)
    qtbot.addWidget(welcome)

    with patch(
        "napari_track_edit.application_menus.welcome_widget.QDesktopServices.openUrl"
    ) as opened:
        welcome._on_link_clicked(QUrl(DOCS_URL))

    assert opened.call_args[0][0].toString() == DOCS_URL


def test_no_editor_floats_over_the_header(qtbot):
    """Every shortcut editor must live in a cell.

    Regression test: the row height was measured from a ShortcutEdit built with
    the table as its parent. Never being placed in a cell, Qt painted it at the
    table's top-left corner, over the "Action" column header.
    """

    panel = KeybindingsWidget()
    qtbot.addWidget(panel)
    table = panel._table

    in_cells = {
        id(table.cellWidget(row, 1))
        for row in range(table.rowCount())
        if table.cellWidget(row, 1) is not None
    }
    strays = [w for w in table.findChildren(ShortcutEdit) if id(w) not in in_cells]

    assert not strays


def test_rows_are_one_line_each(qtbot):
    """All 16 actions and their group headers have to fit without scrolling."""

    panel = KeybindingsWidget()
    qtbot.addWidget(panel)
    table = panel._table

    heights = {table.rowHeight(row) for row in range(table.rowCount())}

    assert len(heights) == 1  # uniform, so nothing wrapped
    assert heights.pop() < 40
