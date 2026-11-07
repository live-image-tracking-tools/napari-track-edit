"""The plugin's keyboard shortcut editor.
Collisions are shown as a warning. Edits are saved to
shortcuts.json in the napari-track-edit user config directory. Navigation and mouse bindings
(arrow keys, the X/Y scroll-zoom modifiers, click/drag) are not rebindable and are not
listed here.
"""

from __future__ import annotations

from app_model.backends.qt import qkeysequence2modelkeybinding
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from napari_track_edit.data_views.keybindings_config import (
    KEYBINDING_GROUPS,
    KEYBINDINGS,
    current_shortcuts,
    format_shortcut,
    napari_conflicts,
    restore_default_shortcuts,
    set_shortcut,
    shortcut_text,
)

DOCS_URL = "https://liveimagetrackingtools.org/napari-track-edit/key_bindings.html"


def _shadows_napari(action: str) -> bool:
    """Whether this action can shadow a napari binding at all.

    Only the "tracks_viewer" actions are bound on napari layers and the viewer.
    A lineage-view-only action is dispatched by `TreeWidget.keyPressEvent`, so
    it is live only while that view has focus and never takes a key away from
    napari.
    """
    return "tracks_viewer" in KEYBINDINGS[action]["targets"]


def _label(action: str) -> str:
    """Short name for the table, e.g. "restore_selection" -> "Restore selection"."""
    return action.replace("_", " ").capitalize()


class ShortcutEdit(QKeySequenceEdit):
    """One shortcut cell.

    A `QKeySequenceEdit` captures the key combination, but its own
    `keySequence()` text is Qt-flavoured: it spells Escape "Esc" (which napari
    parses as *no key at all*) and, on macOS, calls the Command key "Ctrl".
    `qkeysequence2modelkeybinding` is the same converter napari uses to read
    that widget, and it resolves both.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMaximumSequenceLength(1)
        self.setClearButtonEnabled(True)

    def shortcut(self) -> str:
        """The captured shortcut as a napari key string, "" if empty."""
        sequence = self.keySequence()
        if sequence.isEmpty():
            return ""
        return str(qkeysequence2modelkeybinding(sequence))

    def set_shortcut(self, shortcut: str) -> None:
        """Show `shortcut` (a napari key string) without emitting a change."""
        blocked = self.blockSignals(True)
        try:
            self.setKeySequence(
                QKeySequence(format_shortcut(shortcut)) if shortcut else QKeySequence()
            )
        finally:
            self.blockSignals(blocked)


class KeybindingsWidget(QDialog):
    """Table of the plugin's rebindable shortcuts"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Napari Track Edit Keybindings")
        self.setModal(False)
        self._editors: dict[str, ShortcutEdit] = {}
        self._rows: dict[str, int] = {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Click a shortcut and press the new key combination. Use the clear "
            "button to unbind it. See the full list, including the fixed mouse "
            f'and navigation bindings, in the <a href="{DOCS_URL}">documentation</a>.'
        )
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)
        layout.addWidget(intro)

        # Display conflicts and other feedback
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._status)

        self._table = self._build_table()
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        restore_btn = QPushButton("Restore defaults")
        restore_btn.setToolTip(
            "Put every Napari Track Edit shortcut back on its default key. "
            "Does not touch napari's own shortcuts."
        )
        restore_btn.clicked.connect(self._restore_defaults)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        buttons.addWidget(restore_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._reload()
        self.resize(450, 620)

    def _build_table(self) -> QTableWidget:
        """One row per action, preceded by a non-selectable group header row."""
        table = QTableWidget(len(KEYBINDINGS) + len(KEYBINDING_GROUPS), 2, self)
        table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 170)
        table.setWordWrap(False)
        header = table.verticalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setDefaultSectionSize(ShortcutEdit().sizeHint().height() + 6)

        row = 0
        for group in KEYBINDING_GROUPS:
            header = QTableWidgetItem(group)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            table.setItem(row, 0, header)
            table.setSpan(row, 0, 1, 2)
            row += 1

            for action, config in KEYBINDINGS.items():
                if config["group"] != group:
                    continue
                label = QTableWidgetItem(_label(action))
                label.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setItem(row, 0, label)

                editor = ShortcutEdit(table)
                editor.editingFinished.connect(lambda a=action: self._commit(a))
                table.setCellWidget(row, 1, editor)
                self._editors[action] = editor
                self._rows[action] = row
                row += 1

        return table

    def _reload(self) -> None:
        """Show the current bindings, and describe each row."""
        for action, editor in self._editors.items():
            shortcuts = current_shortcuts(action)
            editor.set_shortcut(shortcuts[0] if shortcuts else "")
        self._describe_rows()

    def _commit(self, action: str) -> None:
        """Apply the edit to `action`.

        A collision with another of our actions clears that other binding
        rather than refusing this one.
        """
        shortcut = self._editors[action].shortcut()

        cleared = [
            other
            for other in KEYBINDINGS
            if shortcut and other != action and shortcut in current_shortcuts(other)
        ]
        for other in cleared:
            set_shortcut(other, "")

        set_shortcut(action, shortcut)
        self._reload()
        self._report(action, shortcut, cleared)

    def _report(self, action: str, shortcut: str, cleared: list[str]) -> None:
        """Say what the edit did, including anything it took away."""
        if not shortcut:
            self._status.setText(
                f"Unbound <b>{KEYBINDINGS[action]['description']}</b>."
            )
            return

        messages = [f"<b>{format_shortcut(shortcut)}</b> set."]
        for other in cleared:
            messages.append(
                f"Removed it from <b>{KEYBINDINGS[other]['description']}</b>, "
                "which had the same key."
            )
        overlaps = napari_conflicts(shortcut) if _shadows_napari(action) else []
        if overlaps:
            messages.append(
                "Also used by napari for "
                + ", ".join(f"<i>{name}</i>" for name in overlaps)
                + " - the Motile Tracker action wins while a tracking layer is "
                "active."
            )
        self._status.setText(" ".join(messages))

    def _describe_rows(self) -> None:
        """Put the fixed extra keys and any shadowed napari action in tooltips."""
        shadowed = 0
        for action, row in self._rows.items():
            notes = [KEYBINDINGS[action]["description"]]
            extras = [
                format_shortcut(key) for key in KEYBINDINGS[action].get("also", ())
            ]
            if extras:
                notes.append("Also always bound to: " + ", ".join(extras))
            if not _shadows_napari(action):
                notes.append("Only active while the lineage view has focus.")
            else:
                overlaps = {
                    name
                    for shortcut in current_shortcuts(action)
                    for name in napari_conflicts(shortcut)
                }
                if overlaps:
                    shadowed += 1
                    notes.append("Shadows napari's: " + ", ".join(sorted(overlaps)))
            self._table.item(row, 0).setToolTip("\n\n".join(notes))

        if shadowed:
            self._status.setText(
                f"{shadowed} shortcuts also exist in napari (hover and action to see "
                "which). Napari-track-edit shortcuts defined here take priority when a "
                "tracking layer is active; hover an action to see which."
            )

    def _restore_defaults(self) -> None:
        restore_default_shortcuts()
        self._reload()
        self._status.setText(
            "Restored the default shortcuts: "
            + ", ".join(
                shortcut_text(action) for action in KEYBINDINGS if shortcut_text(action)
            )
            + "."
        )


def open_keybindings_panel(parent: QWidget | None = None) -> KeybindingsWidget:
    """Show the keybindings panel.

    Kept non-modal and remembered per parent, so it can stay open next to the
    viewer while the user tries the keys out.
    """
    existing = getattr(parent, "_track_edit_keybindings_panel", None)
    if existing is not None:
        try:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return existing
        except RuntimeError:
            # Qt side already destroyed; fall through and make a new one.
            pass

    panel = KeybindingsWidget(parent)
    if parent is not None:
        parent._track_edit_keybindings_panel = panel
    panel.show()
    panel.raise_()
    return panel
