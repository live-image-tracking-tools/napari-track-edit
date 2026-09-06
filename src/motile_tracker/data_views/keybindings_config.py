"""Unified keybindings configuration for both napari layers and Qt widgets.

This module defines all keybindings in a unified way, specifying:
- The action to perform (method name)
- Keys for napari layers (string format)
- Keys for Qt widgets (Qt.Key constants)
- The target(s) for the action: "tracks_viewer", "tree_widget", or both

An action can target multiple objects. It will be available in the following ways:
- napari layers: if "tracks_viewer" is in targets
- Qt table_widget: if "tracks_viewer" is in targets
- Qt tree_widget: if "tree_widget" is in targets

PROTOTYPE: all actions (both "tracks_viewer" and "tree_widget" targets) are
registered with napari's ``action_manager`` and seeded into
``napari.settings.get_settings().shortcuts``. This means:
- they persist across sessions in napari's own settings YAML
- they are rebindable/resettable via napari's built-in
  Preferences -> Shortcuts dialog, with napari's own conflict warnings -
  including cross-checking a "tracks_viewer" rebind against a
  "tree_widget"-only default and vice versa (e.g. rebinding something to
  "w" now warns about colliding with toggle_feature_mode)
- the Qt-side dispatch tables (``current_general_key_actions`` /
  ``current_tree_widget_specific_actions``) are rebuilt from the *current*
  napari settings/action_manager state, so a rebind made in the
  Preferences dialog also updates Qt widget dispatch, not just napari
  layers/viewer.

"tree_widget"-only actions have no real napari keymap to bind to (their
"keymapprovider" would have to be a Qt widget class with `bind_key`, which
napari's `action_manager` doesn't support). They're registered against
`_TreeWidgetKeymapProvider`, a bare `KeymapProvider` subclass that exists
only so `action_manager` has somewhere to park the binding - this makes the
action visible and conflict-checked in napari's Preferences dialog (which
otherwise skips any action with `keymapprovider=None`), without ever
actually being triggered through napari's own keymap dispatch. The real
dispatch stays in `TreeWidget.keyPressEvent`, reading the same
settings-backed source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from napari.settings import get_settings
from napari.utils.action_manager import action_manager
from napari.utils.key_bindings import KeymapProvider, coerce_keybinding
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence

if TYPE_CHECKING:
    from napari.layers import Labels, Points

    from motile_tracker.data_views.views.layers.track_labels import TrackLabels
    from motile_tracker.data_views.views.layers.track_points import TrackPoints
    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

ACTION_PREFIX = "motile-tracker"
# Shown as a prefix on the "Action" column in napari's Preferences ->
# Shortcuts dialog, so our actions are visually grouped/identifiable among
# napari's own and other plugins'. Update when the package is renamed
# (napari-track-edit / NTE).
DESCRIPTION_PREFIX = "Motile Tracker"


class _TreeWidgetKeymapProvider(KeymapProvider):
    """Dummy keymapprovider so tree-widget-only actions show up in napari's
    Preferences -> Shortcuts dialog and get conflict-checked there, even
    though no real napari keymap dispatch ever reads `class_keymap` here -
    `TreeWidget.keyPressEvent` is the actual executor.
    """


def _action_id(name: str) -> str:
    return f"{ACTION_PREFIX}:{name}"


def bind_keymap(
    target: TrackPoints | Points | TrackLabels | Labels,
    keymap: dict[str, str],
    tracks_viewer: TracksViewer,
):
    """Bind all keys in `keymap` to the corresponding methods on `tracks_viewer` to the
    target layer. This should be an instance of (Track)Labels or (Track)Points"""

    for method_name, keys in keymap.items():
        handler = getattr(tracks_viewer, method_name, None)
        if handler is not None:
            for key in keys:
                target.bind_key(key)(handler)


def register_napari_actions(
    keymap_provider: type,
    tracks_viewer: TracksViewer,
    tree_widget: object | None = None,
) -> None:
    """Register all actions with napari's action_manager, scoped by target.

    "tracks_viewer"-targeted actions are registered against `keymap_provider`
    (a real napari `Viewer`/layer class), so a shortcut actually triggers
    the napari-level keymap dispatch. "tree_widget"-targeted actions are
    registered against `_TreeWidgetKeymapProvider` (a dummy `KeymapProvider`
    with no real dispatch reading it) purely so they're visible and
    conflict-checked in napari's Preferences -> Shortcuts dialog; the real
    trigger stays `TreeWidget.keyPressEvent`, which is why `tree_widget` is
    only needed to resolve the handler method, not for real key binding.

    Seeds napari's persisted shortcut settings with our defaults the first
    time an action is seen, then binds from whatever is currently in
    settings (so a previously user-rebound shortcut is honored on restart).
    """
    settings = get_settings().shortcuts.shortcuts
    seeded_new_defaults = False
    for action, config in KEYBINDINGS.items():
        targets = config["targets"]
        if "tracks_viewer" in targets:
            provider, handler_obj, description_prefix = (
                keymap_provider,
                tracks_viewer,
                DESCRIPTION_PREFIX,
            )
        elif "tree_widget" in targets:
            provider, handler_obj, description_prefix = (
                _TreeWidgetKeymapProvider,
                tree_widget,
                f"{DESCRIPTION_PREFIX} (Tree Widget)",
            )
        else:
            continue
        if not config["napari_keys"] or handler_obj is None:
            continue

        action_id = _action_id(action)
        handler = getattr(handler_obj, action, None)
        if handler is None:
            continue

        action_manager.register_action(
            name=action_id,
            command=handler,
            description=f"{description_prefix}: {action.replace('_', ' ')}",
            keymapprovider=provider,
        )

        if action_id not in settings:
            settings[action_id] = [
                coerce_keybinding(key) for key in config["napari_keys"]
            ]
            seeded_new_defaults = True
        for shortcut in settings[action_id]:
            action_manager.bind_shortcut(action_id, str(shortcut))

    if seeded_new_defaults:
        # Assigning triggers the evented model's changed signal (and
        # therefore autosave) only when the value differs from what's
        # already set; re-assigning an unchanged dict is a no-op for
        # persistence. Force a save so first-run defaults actually land in
        # napari's settings file, not just in memory for this session.
        get_settings().shortcuts.shortcuts = settings
        get_settings().save()

    get_settings().shortcuts.shortcuts = settings


def qt_event_key(event) -> tuple[int, int]:
    """Build the (key, modifiers) lookup tuple for a QKeyEvent.

    Use this on the receiving end (e.g. `event.key()`/`event.modifiers()`
    in a `keyPressEvent` override) to look up `current_general_key_actions()`.
    """
    return (int(event.key()), int(event.modifiers().value))


def _current_key_actions_for_target(target: str) -> dict[tuple[int, int], str]:
    """(Qt.Key_*, modifiers) -> method name, for all actions with `target`
    in their "targets", reflecting live napari settings.

    Rebuilt from napari's settings/action_manager state (rather than a
    static dict) so a rebind made via napari's Preferences dialog is picked
    up by the Qt-side keyPressEvent dispatch too. Keys are (key, modifiers)
    tuples so e.g. "d" and "ctrl+d" don't collide.
    """
    shortcuts = get_settings().shortcuts.shortcuts
    result: dict[tuple[int, int], str] = {}
    for action, config in KEYBINDINGS.items():
        if target not in config["targets"]:
            continue
        action_id = _action_id(action)
        bound = shortcuts.get(action_id)
        if not bound:
            # not yet registered/seeded (e.g. called before viewer init) -
            # fall back to the static defaults so Qt widgets still work.
            bound = [coerce_keybinding(key) for key in config["napari_keys"]]
        for shortcut in bound:
            qt_combo = _napari_shortcut_to_qt_key(str(shortcut))
            if qt_combo is not None:
                result[qt_combo] = action
    return result


def current_general_key_actions() -> dict[tuple[int, int], str]:
    """(Qt.Key_*, modifiers) -> tracks_viewer method name, reflecting live
    napari settings. See `_current_key_actions_for_target`.
    """
    return _current_key_actions_for_target("tracks_viewer")


def current_tree_widget_specific_actions() -> dict[tuple[int, int], str]:
    """(Qt.Key_*, modifiers) -> tree_widget method name, reflecting live
    napari settings. See `_current_key_actions_for_target`.
    """
    return _current_key_actions_for_target("tree_widget")


def _napari_shortcut_to_qt_key(shortcut: str) -> tuple[int, int] | None:
    """Convert a napari shortcut string to a (Qt.Key_*, modifiers) tuple.

    Handles a single key plus any combination of modifiers (e.g. "d",
    "ctrl+d", "ctrl+shift+d"). Does NOT handle chords (multi-key sequences
    like "ctrl+k p") - `QKeySequence` doesn't model those as a single combo,
    and none of today's actions need them.
    """
    qt_seq = QKeySequence(shortcut)
    if qt_seq.count() != 1:
        return None
    combo = qt_seq[0]
    return (int(combo.key()), int(combo.keyboardModifiers().value))


KEYBINDINGS = {
    # General actions: apply to both napari layers and tree_widget (via tracks_viewer)
    # PROTOTYPE NOTE: "tracks_viewer"-only actions no longer need "qt_keys" -
    # Qt dispatch for these is derived from "napari_keys" at runtime via
    # `current_general_key_actions()`/`_napari_shortcut_to_qt_key`, so there
    # is exactly one place a key is specified (removes a duplication that
    # was a latent bug source: editing one list and forgetting the other).
    "delete_node": {
        "napari_keys": ["d", "Delete"],
        "targets": ["tracks_viewer"],
    },
    "create_edge": {
        # plain "a" collides with napari's built-in
        # "napari:select_all_in_slice" (Points-layer action); use a
        # modifier combo to avoid the conflict.
        "napari_keys": ["shift+a"],
        "targets": ["tracks_viewer"],
    },
    "delete_edge": {
        "napari_keys": ["b"],
        "targets": ["tracks_viewer"],
    },
    "swap_nodes": {
        "napari_keys": ["s"],
        "targets": ["tracks_viewer"],
    },
    "undo": {
        "napari_keys": ["z"],
        "targets": ["tracks_viewer"],
    },
    "redo": {
        # "ctrl+shift+z" demonstrates a modifier-combo default binding.
        "napari_keys": ["r", "ctrl+shift+z"],
        "targets": ["tracks_viewer"],
    },
    "deselect": {
        "napari_keys": ["Escape"],
        "targets": ["tracks_viewer"],
    },
    "restore_selection": {
        "napari_keys": ["e"],
        "targets": ["tracks_viewer"],
    },
    "hide_panels": {
        "napari_keys": ["/"],
        "targets": ["tracks_viewer"],
    },
    "select_previous": {
        "napari_keys": ["p"],  # Previous: Navigate backwards in selection history
        "targets": ["tracks_viewer"],
    },
    "select_next": {
        "napari_keys": ["n"],  # Next: Navigate forwards in selection history
        "targets": ["tracks_viewer"],
    },
    # Actions available in both napari and tree_widget (but connected to different functions)
    "toggle_display_mode": {
        "napari_keys": ["q"],
        "targets": ["tracks_viewer", "tree_widget"],
    },
    # Tree-widget-specific actions
    "toggle_feature_mode": {
        "napari_keys": ["w"],
        "targets": ["tree_widget"],
    },
    "flip_axes": {
        "napari_keys": ["f"],
        "targets": ["tree_widget"],
    },
}

# Special treeview keybinds that don't call simple methods
SPECIAL_KEYBINDS = {
    "qt_modifier_zoom": {
        # Mouse zoom constraints (Qt only)
        Qt.Key_X: (True, False),  # (x_enabled, y_enabled)
        Qt.Key_Y: (False, True),
    },
    "qt_navigation": {
        # Arrow keys for navigation (Qt only)
        Qt.Key_Left: "left",
        Qt.Key_Right: "right",
        Qt.Key_Up: "up",
        Qt.Key_Down: "down",
    },
}

# Napari KEYMAP: action -> list of napari key strings.
# PROTOTYPE NOTE: kept only as the static fallback/seed default; the live
# napari-side bindings for "tracks_viewer" actions now go through
# `register_napari_actions` / `action_manager` instead of `bind_keymap`, so
# they can be persisted and rebound via napari's settings.
KEYMAP = {
    action: config["napari_keys"]
    for action, config in KEYBINDINGS.items()
    if config["napari_keys"] and "tracks_viewer" in config["targets"]
}

# PROTOTYPE NOTE: the old static "Qt General Key Actions" and "Qt
# Tree-Widget Specific Actions" dicts (built once at import time) are gone.
# Both are now functions - `current_general_key_actions()` and
# `current_tree_widget_specific_actions()` - that read live napari settings
# so Qt dispatch reflects user rebinds made in napari's Preferences dialog.
# Callers should call the function instead of importing a module-level dict.

# Qt Modifier Actions: for mouse zoom constraints
TREE_WIDGET_MODIFIER_ACTIONS = SPECIAL_KEYBINDS["qt_modifier_zoom"]

# Qt Navigation Actions: arrow keys
TREE_WIDGET_NAVIGATION_KEYS = SPECIAL_KEYBINDS["qt_navigation"]
