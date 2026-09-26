"""Where every Napari Track Edit keyboard shortcut is defined, stored and dispatched.

``KEYBINDINGS`` is the single source of truth: each entry names the method to
call, its default shortcut, a one-line description and which targets it
reaches. From this, we derive the napari and Qt dispatch tables, the button captions,
the keybindings panel and the documentation table, so a key is only ever written down in
one place.

Keybindings are stored in shortcuts.json in the user's config directory.
The actions are deliberately *not* registered with napari's ``action_manager``.
napari offers no plugin hooks for this.

Dispatch is instance-level: ``bind_keymap`` puts the current shortcuts on the
*instance* keymap of the viewer and of each tracking layer. napari resolves a
key press through the global user keymap, then the active layer's instance
keymap, then its class keymap, then the viewer's instance keymap, and last
``Viewer.class_keymap``. Most of our defaults collide with a built-in napari
action, so only an instance binding reliably wins: shadowing napari while a
tracking layer is active is the intended behaviour. Qt widgets that are not
napari layers (the tree view, the table) dispatch from
``current_general_key_actions`` / ``current_tree_widget_specific_actions``.
"""

from __future__ import annotations

import contextlib
import json
import sys
import weakref
from pathlib import Path
from typing import TYPE_CHECKING

import platformdirs
from app_model.backends.qt import QKeyBindingSequence
from app_model.types import KeyBinding
from napari.utils.action_manager import action_manager
from napari.utils.key_bindings import coerce_keybinding
from psygnal import Signal
from qtpy.QtCore import Qt

if TYPE_CHECKING:
    from napari.layers import Labels, Points

    from napari_track_edit.data_views.views.layers.track_labels import TrackLabels
    from napari_track_edit.data_views.views.layers.track_points import TrackPoints
    from napari_track_edit.data_views.views_coordinator.tracks_viewer import (
        TracksViewer,
    )


# The platform's command modifier, as napari spells it: Ctrl on Windows and
# Linux, Cmd (which napari calls "Meta") on macOS.
CMD = "meta" if sys.platform == "darwin" else "ctrl"

# The table
# - "key": the default shortcut, and the one the panel lets you change.
# - "also": extra shortcuts that are always bound and are not editable, for
#   keys that are conventional rather than chosen.
# - "description": shown in the panel and in the generated docs table.
# - "group": section heading in the panel and the docs.
# - "targets": "tracks_viewer" (napari layers, viewer and the table widget),
#   "tree_widget", or both.
KEYBINDINGS = {
    "request_new_track": {
        "key": "m",
        "description": (
            "Start a new track: assign a new track id, and a new segmentation "
            "label if necessary"
        ),
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "delete_node": {
        "key": "d",
        "also": ["Delete"],
        "description": "Delete the selected nodes",
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "swap_nodes": {
        "key": "s",
        "description": "Swap the incoming edges of two nodes at the same time point",
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "connect_nodes_with_divisions": {
        "key": "c",
        "description": (
            "Connect the selected nodes into one track, keeping existing outgoing "
            "edges as divisions"
        ),
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "connect_nodes_linearly": {
        "key": "shift+c",
        "description": (
            "Connect the selected nodes into one linear track, breaking existing "
            "outgoing edges"
        ),
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "disconnect_nodes": {
        "key": "b",
        "description": (
            "Break the edges between the selected nodes. Edges to nodes outside "
            "the selection are kept"
        ),
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "set_division": {
        "key": "y",
        "description": (
            "Make or break a division between a parent node and its two children"
        ),
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "merge_horizontally": {
        "key": "h",
        "description": (
            "Merge each set of selected nodes that shares a time point into a "
            "single node."
        ),
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "undo": {
        "key": "z",
        "description": "Undo the last editing action",
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "redo": {
        "key": "r",
        "also": [f"{CMD}+shift+z"],
        "description": "Redo the last undone editing action",
        "group": "Editing",
        "targets": ["tracks_viewer"],
    },
    "deselect": {
        "key": "Escape",
        "description": "Clear the selection",
        "group": "Selection",
        "targets": ["tracks_viewer"],
    },
    "restore_selection": {
        "key": "e",
        "description": "Restore the last selection",
        "group": "Selection",
        "targets": ["tracks_viewer"],
    },
    "select_previous": {
        "key": "p",
        "description": "Select the previous node set from the selection history",
        "group": "Selection",
        "targets": ["tracks_viewer"],
    },
    "select_next": {
        "key": "n",
        "description": "Select the next node set from the selection history",
        "group": "Selection",
        "targets": ["tracks_viewer"],
    },
    "hide_panels": {
        "key": "/",
        "description": "Hide or show all currently active widgets",
        "group": "View",
        "targets": ["tracks_viewer"],
    },
    "toggle_display_mode": {
        "key": "q",
        "description": (
            "Cycle the display mode: All to Lineage to Group. Skips Group when no "
            "groups exist"
        ),
        "group": "View",
        # Bound in both places, but to a different method on each.
        "targets": ["tracks_viewer", "tree_widget"],
    },
    "toggle_feature_mode": {
        "key": "w",
        "description": (
            "Switch the lineage view between the tree plot and a feature plot"
        ),
        "group": "Lineage view",
        "targets": ["tree_widget"],
    },
    "flip_axes": {
        "key": "f",
        "description": "Flip the axes of the lineage view",
        "group": "Lineage view",
        "targets": ["tree_widget"],
    },
}

# Section order for the keybindings panel and the generated docs table.
KEYBINDING_GROUPS = ("Editing", "Selection", "View", "Lineage view")

# Keys the tree view handles itself. Not rebindable.
TREE_WIDGET_MODIFIER_ACTIONS = {
    Qt.Key_X: (True, False),  # (x_enabled, y_enabled) mouse zoom constraint
    Qt.Key_Y: (False, True),
}
TREE_WIDGET_NAVIGATION_KEYS = {
    Qt.Key_Left: "left",
    Qt.Key_Right: "right",
    Qt.Key_Up: "up",
    Qt.Key_Down: "down",
}


# Storage
class _Shortcuts:
    """The user's shortcut overrides, and a signal for when they change.

    Stored as ``{action: shortcut}``. Only overrides are written, so an action
    left alone follows its default even if that default later changes; an
    action the user cleared is stored as "".
    """

    changed = Signal()

    def __init__(self) -> None:
        self._overrides: dict[str, str] | None = None

    @property
    def path(self) -> Path:
        return (
            Path(platformdirs.user_config_dir("napari-track-edit")) / "shortcuts.json"
        )

    @property
    def overrides(self) -> dict[str, str]:
        if self._overrides is None:
            self._overrides = {}
            with contextlib.suppress(OSError, ValueError):
                loaded = json.loads(self.path.read_text())
                if isinstance(loaded, dict):
                    self._overrides = {
                        k: str(v) for k, v in loaded.items() if k in KEYBINDINGS
                    }
        return self._overrides

    def set(self, action: str, shortcut: str) -> None:
        """Override `action` (or "" to unbind it), save and notify."""
        self.overrides[action] = shortcut
        self.save()

    def reset(self, actions: list[str] | None = None) -> None:
        """Drop overrides so `actions` (default: all) follow their defaults."""
        for action in KEYBINDINGS if actions is None else actions:
            self.overrides.pop(action, None)
        self.save()

    def save(self) -> None:
        with contextlib.suppress(OSError):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.overrides, indent=2, sort_keys=True))
        self.changed.emit()


SHORTCUTS = _Shortcuts()


def current_shortcuts(action: str) -> list[str]:
    """Every shortcut `action` answers to now: the user's choice (or the
    default) plus any fixed extras. Empty if the user cleared it."""
    config = KEYBINDINGS.get(action)
    if config is None:
        return []
    chosen = SHORTCUTS.overrides.get(action, config["key"])
    return _normalize(([chosen] if chosen else []) + list(config.get("also", ())))


def default_shortcut(action: str) -> str:
    """The editable default for `action`, normalized."""
    return _normalize([KEYBINDINGS[action]["key"]])[0]


def set_shortcut(action: str, shortcut: str) -> None:
    """Bind `action` to `shortcut` ("" to unbind) and persist it."""
    SHORTCUTS.set(action, _normalize([shortcut])[0] if shortcut else "")


def restore_default_shortcuts(actions: list[str] | None = None) -> None:
    """Put `actions` (default: all of ours) back on their defaults."""
    SHORTCUTS.reset(actions)


def _normalize(shortcuts) -> list[str]:
    """Canonical napari spelling for each, e.g. "ctrl+u" -> "Ctrl+U".

    De-duplicated, since a user can pick the key that is already one of the
    action's fixed extras.
    """
    return list(dict.fromkeys(str(coerce_keybinding(str(s))) for s in shortcuts))


# Dispatch: napari layers and the viewer
# Instances whose keymap we keep in sync, and the TracksViewer each dispatches
# to. Weak, so a closed viewer or a removed layer is not kept alive.
_KEY_TARGETS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# What we last bound on each, so a rebind removes exactly our own keys and
# leaves anything the layer bound for other reasons alone. Kept here rather
# than on the target: a napari Viewer is a pydantic model and rejects unknown
# attributes.
_BOUND_KEYS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def bind_keymap(
    target: TrackPoints | Points | TrackLabels | Labels,
    tracks_viewer: TracksViewer,
) -> None:
    """Bind the "tracks_viewer" shortcuts onto `target`'s *instance* keymap and
    keep them there as the user rebinds. The module docstring says why it has
    to be the instance keymap."""
    _KEY_TARGETS[target] = tracks_viewer
    _apply_instance_keymap(target, tracks_viewer)


def _apply_instance_keymap(target, tracks_viewer: TracksViewer) -> None:
    for key in _BOUND_KEYS.get(target, ()):
        target.keymap.pop(key, None)

    bound = []
    for action, config in KEYBINDINGS.items():
        handler = getattr(tracks_viewer, action, None)
        if "tracks_viewer" not in config["targets"] or handler is None:
            continue
        for shortcut in current_shortcuts(action):
            key = coerce_keybinding(shortcut)
            target.bind_key(key, handler, overwrite=True)
            bound.append(key)
    _BOUND_KEYS[target] = bound


def refresh_napari_keymaps(tracks_viewer: TracksViewer) -> None:
    """Re-apply the current shortcuts to everything bound to `tracks_viewer`.

    Scoped to one TracksViewer, because a session can hold several and
    refreshing all of them from each of their listeners would be quadratic.
    """
    sync_blocked_napari_keys()
    for target, owner in list(_KEY_TARGETS.items()):
        if owner is not tracks_viewer:
            continue
        with contextlib.suppress(RuntimeError, ReferenceError):
            _apply_instance_keymap(target, tracks_viewer)


def blocked_napari_binding(_layer=None) -> None:
    """No-op stand-in for a napari binding we deliberately swallow."""


# Keys currently blocked on ContourLabels, so a rebind can lift the old block
# instead of leaving napari's action unreachable on a key we no longer use.
_BLOCKED_KEYS: list = []


def sync_blocked_napari_keys() -> None:
    """Keep napari's "new label" blocked on whatever key starts a new track.

    napari's Labels layer binds [M] to `new_label`, which hands out a label
    with no track id behind it. The block lives on the class keymap so it also
    covers a ContourLabels that is not showing tracks and so has no instance
    binding of ours. It follows the current shortcut: after a rebind the old
    key goes back to napari and the new one is covered.
    """
    from napari_track_edit.data_views.views.layers.contour_labels import ContourLabels

    global _BLOCKED_KEYS
    for key in _BLOCKED_KEYS:
        if ContourLabels.class_keymap.get(key) is blocked_napari_binding:
            del ContourLabels.class_keymap[key]

    keys = [coerce_keybinding(s) for s in current_shortcuts("request_new_track")]
    for key in keys:
        ContourLabels.bind_key(key, blocked_napari_binding, overwrite=True)
    _BLOCKED_KEYS = keys


def napari_conflicts(shortcut: str) -> list[str]:
    """Descriptions of napari's own actions already using `shortcut`.

    Informational only: a plugin shortcut deliberately shadows a built-in layer
    action while a tracking layer is active, so a collision is something to
    tell the user about, not to refuse. Read-only - we register nothing with
    `action_manager`.
    """
    key = str(coerce_keybinding(str(shortcut)))
    found = []
    # Snapshot: `_shortcuts` is a defaultdict napari writes to lazily.
    for action_id, bound in list(action_manager._shortcuts.items()):
        registered = action_manager._actions.get(action_id)
        if registered is not None and key in _normalize(bound):
            found.append(registered.description)
    return found


# Dispatch: Qt widgets that are not napari layers
def qt_event_key(event) -> tuple[int, int]:
    """The (key, modifiers) lookup tuple for a QKeyEvent."""
    return (int(event.key()), int(event.modifiers().value))


def _key_actions_for_target(target: str) -> dict[tuple[int, int], str]:
    return {
        combo: action
        for action, config in KEYBINDINGS.items()
        if target in config["targets"]
        for shortcut in current_shortcuts(action)
        if (combo := _qt_combo(shortcut)) is not None
    }


def current_general_key_actions() -> dict[tuple[int, int], str]:
    """(Qt.Key_*, modifiers) -> tracks_viewer method name."""
    return _key_actions_for_target("tracks_viewer")


def current_tree_widget_specific_actions() -> dict[tuple[int, int], str]:
    """(Qt.Key_*, modifiers) -> tree_widget method name."""
    return _key_actions_for_target("tree_widget")


def _qt_combo(shortcut: str) -> tuple[int, int] | None:
    """A napari shortcut as a (Qt.Key_*, modifiers) tuple, None for a chord.

    Goes through app_model rather than `QKeySequence(shortcut)`, which reads
    the string as Qt spells it, not as napari does. The two disagree on macOS:
    Qt's "Ctrl" is the Command key, napari's is literal Control. Parsing it the
    Qt way bound the *other* modifier, so a chord fired on Cmd in the tree view
    and table while firing on Control in the canvas - the same shortcut needing
    two different keys depending on where the focus was.
    """
    sequence = QKeyBindingSequence(KeyBinding.from_str(shortcut))
    if sequence.count() != 1:
        return None
    combo = sequence[0]
    return (int(combo.key()), int(combo.keyboardModifiers().value))


# Display
# Spelled out rather than shown as the platform glyph.
_KEY_ALIASES = {"Escape": "Esc", "Delete": "Del"}
# napari names modifiers by what they are, not where they sit: "Ctrl" is always
# Control and "Meta" is the Command key. Spell those the way this keyboard does.
_MODIFIER_ALIASES = {"Meta": "Cmd", "Alt": "Option"} if sys.platform == "darwin" else {}
# Conventional reading order for a chord, as printed on keyboards and in menus.
_MODIFIER_ORDER = ["Ctrl", "Meta", "Alt", "Shift"]


def format_shortcut(shortcut: str, platform_names: bool = True) -> str:
    """One shortcut as display text, e.g. "ctrl+shift+z" -> "Ctrl+Shift+Z".

    `platform_names` renames modifiers to what this keyboard calls them. Pass
    False where the text is not for this machine - the generated documentation
    is read on every platform and must not bake in the one that built it.
    """
    parts = str(coerce_keybinding(str(shortcut))).split("+")
    key = _KEY_ALIASES.get(parts[-1], parts[-1])
    # napari canonicalizes to alphabetical order ("Shift+Meta+Z"); show the
    # modifiers the way keyboards label them instead.
    modifiers = sorted(parts[:-1], key=_MODIFIER_ORDER.index)
    if platform_names:
        modifiers = [_MODIFIER_ALIASES.get(m, m) for m in modifiers]
    return "+".join([*modifiers, key])


def shortcut_text(action: str) -> str:
    """The action's current shortcut as text, or "" if it is unbound."""
    shortcuts = current_shortcuts(action)
    return format_shortcut(shortcuts[0]) if shortcuts else ""


def shortcut_label(action: str, text: str) -> str:
    """ "<text> [<key>]", or just `text` when the action is unbound."""
    key = shortcut_text(action)
    return f"{text} [{key}]" if key else text


class _ShortcutCaption:
    """Keeps one widget's caption in sync with an action's current shortcut.

    Holds the widget by weakref and connects by *bound method*, so psygnal
    keeps only a weak reference to this object: `SHORTCUTS.changed` lives for
    the whole process, and a strong closure over the widget would pin it - and,
    since a Qt child wrapper keeps its parent alive, the whole widget tree
    around it.
    """

    def __init__(self, widget, action: str, text: str, setter: str) -> None:
        self._widget = weakref.ref(widget)
        self._action = action
        self._text = text
        self._setter = setter

    def render(self) -> None:
        widget = self._widget()
        if widget is None:
            return
        # RuntimeError: the C++ side is already gone.
        with contextlib.suppress(RuntimeError):
            getattr(widget, self._setter)(shortcut_label(self._action, self._text))


def bind_shortcut_label(widget, action: str, text: str, setter: str = "") -> None:
    """Keep `widget`'s caption showing `action`'s *current* shortcut.

    Replaces hand-written captions like `QPushButton("Delete [D]")`, which go
    stale as soon as the user rebinds.

    `setter` defaults to `setTitle` for a QGroupBox and `setText` otherwise.
    """
    if not setter:
        setter = "setTitle" if hasattr(widget, "setTitle") else "setText"
    caption = _ShortcutCaption(widget, action, text, setter)
    # The widget is the only strong owner, so the connection lasts exactly as
    # long as it does.
    widget._track_edit_shortcut_caption = caption
    caption.render()
    SHORTCUTS.changed.connect(caption.render)


def _doc_shortcut(shortcut: str) -> str:
    """Display text for the docs, which are read on every platform.

    The command modifier is written "Ctrl/Cmd" rather than resolved to
    whichever machine built the docs.
    """
    command = format_shortcut(CMD + "+a", platform_names=False).split("+")[0]
    return format_shortcut(shortcut, platform_names=False).replace(
        f"{command}+", "Ctrl/Cmd+"
    )


def keybindings_rst() -> str:
    """The rebindable actions as reStructuredText, grouped, for the docs.

    Generated so the documentation cannot drift from the code the way a
    hand-written table does. Reports the *defaults*, since this renders at docs
    build time, where the reader's own choices are neither available nor
    relevant.
    """
    lines = [
        ".. This file is generated from napari_track_edit's KEYBINDINGS table by",
        ".. docs/source/conf.py. Edit the descriptions and defaults there.",
        "",
    ]
    for group in KEYBINDING_GROUPS:
        actions = [a for a, c in KEYBINDINGS.items() if c["group"] == group]
        if not actions:
            continue
        lines += [
            group,
            "-" * len(group),
            "",
            ".. list-table::",
            "   :widths: 25 75",
            "   :header-rows: 1",
            "",
            "   * - Default key binding",
            "     - Action",
        ]
        for action in actions:
            config = KEYBINDINGS[action]
            keys = " or ".join(
                _doc_shortcut(key) for key in [config["key"], *config.get("also", ())]
            )
            lines += [f"   * - {keys}", f"     - {config['description']}"]
        lines.append("")
    return "\n".join(lines)
