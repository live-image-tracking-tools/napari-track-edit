"""Unified keybindings configuration for both napari layers and Qt widgets.

This module defines all keybindings in a unified way, specifying:
- The action to perform (method name)
- Keys for napari layers (string format)
- Keys for Qt widgets (Qt.Key constants)
- Optionally the Qt modifier that must be held ("qt_modifiers", default: none)
- The target(s) for the action: "tracks_viewer", "tree_widget", or both

An action can target multiple objects. It will be available in the following ways:
- napari layers: if "tracks_viewer" is in targets
- Qt table_widget: if "tracks_viewer" is in targets
- Qt tree_widget: if "tree_widget" is in targets
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt

if TYPE_CHECKING:
    from napari.layers import Labels, Points
    from qtpy.QtGui import QKeyEvent

    from motile_tracker.data_views.views.layers.track_labels import TrackLabels
    from motile_tracker.data_views.views.layers.track_points import TrackPoints
    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


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


KEYBINDINGS = {
    # General actions: apply to both napari layers and tree_widget (via tracks_viewer)
    "delete_node": {
        "napari_keys": ["d", "Delete"],
        "qt_keys": [Qt.Key_D, Qt.Key_Delete],
        "targets": ["tracks_viewer"],
    },
    "connect_nodes_with_divisions": {
        "napari_keys": ["c"],
        "qt_keys": [Qt.Key_C],
        "targets": ["tracks_viewer"],
    },
    "connect_nodes_linearly": {
        "napari_keys": ["Shift-C"],
        "qt_keys": [Qt.Key_C],
        "qt_modifiers": Qt.ShiftModifier,
        "targets": ["tracks_viewer"],
    },
    "swap_nodes": {
        "napari_keys": ["s"],
        "qt_keys": [Qt.Key_S],
        "targets": ["tracks_viewer"],
    },
    "undo": {
        "napari_keys": ["z"],
        "qt_keys": [Qt.Key_Z],
        "targets": ["tracks_viewer"],
    },
    "redo": {
        "napari_keys": ["r"],
        "qt_keys": [Qt.Key_R],
        "targets": ["tracks_viewer"],
    },
    "deselect": {
        "napari_keys": ["Escape"],
        "qt_keys": [Qt.Key_Escape],
        "targets": ["tracks_viewer"],
    },
    "restore_selection": {
        "napari_keys": ["e"],
        "qt_keys": [Qt.Key_E],
        "targets": ["tracks_viewer"],
    },
    "hide_panels": {
        "napari_keys": ["/"],
        "qt_keys": [Qt.Key_Slash],
        "targets": ["tracks_viewer"],
    },
    "select_previous": {
        "napari_keys": ["p"],  # Previous: Navigate backwards in selection history
        "qt_keys": [Qt.Key_P],
        "targets": ["tracks_viewer"],
    },
    "select_next": {
        "napari_keys": ["n"],  # Next: Navigate forwards in selection history
        "qt_keys": [Qt.Key_N],
        "targets": ["tracks_viewer"],
    },
    # Actions available in both napari and tree_widget (but connected to different functions)
    "toggle_display_mode": {
        "napari_keys": ["q"],
        "qt_keys": [Qt.Key_Q],
        "targets": ["tracks_viewer", "tree_widget"],
    },
    # Tree-widget-specific actions
    "toggle_feature_mode": {
        "napari_keys": ["w"],
        "qt_keys": [Qt.Key_W],
        "targets": ["tree_widget"],
    },
    "flip_axes": {
        "napari_keys": ["f"],
        "qt_keys": [Qt.Key_F],
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

# Napari KEYMAP: action -> list of napari key strings
KEYMAP = {
    action: config["napari_keys"]
    for action, config in KEYBINDINGS.items()
    if config["napari_keys"] and "tracks_viewer" in config["targets"]
}

# Qt General Key Actions: (Qt key constant, shift held) -> tracks_viewer method names
GENERAL_KEY_ACTIONS = {}
for action, config in KEYBINDINGS.items():
    if "tracks_viewer" in config["targets"] and config["qt_keys"]:
        shift = bool(config.get("qt_modifiers", Qt.NoModifier) & Qt.ShiftModifier)
        for key in config["qt_keys"]:
            GENERAL_KEY_ACTIONS[key, shift] = action

# Qt Tree-Widget Specific Actions: (key, shift held) -> tree_widget method names
TREE_WIDGET_SPECIFIC_ACTIONS = {}
for action, config in KEYBINDINGS.items():
    if "tree_widget" in config["targets"] and config["qt_keys"]:
        shift = bool(config.get("qt_modifiers", Qt.NoModifier) & Qt.ShiftModifier)
        for key in config["qt_keys"]:
            TREE_WIDGET_SPECIFIC_ACTIONS[key, shift] = action


def resolve_key_action(actions: dict, event: QKeyEvent) -> str | None:
    """Look up the action name bound to a Qt key event in `actions`, which is keyed by
    (Qt key constant, whether shift is held)."""

    shift = bool(event.modifiers() & Qt.ShiftModifier)
    return actions.get((event.key(), shift))


# Qt Modifier Actions: for mouse zoom constraints
TREE_WIDGET_MODIFIER_ACTIONS = SPECIAL_KEYBINDS["qt_modifier_zoom"]

# Qt Navigation Actions: arrow keys
TREE_WIDGET_NAVIGATION_KEYS = SPECIAL_KEYBINDS["qt_navigation"]
