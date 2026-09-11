import contextlib

import napari
import numpy as np
import pandas as pd
from qtpy.QtCore import (
    QAbstractTableModel,
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    Qt,
)
from qtpy.QtGui import QColor, QKeyEvent, QMouseEvent, QPen
from qtpy.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.data_views.colormap import TrackColormap
from motile_tracker.data_views.keybindings_config import GENERAL_KEY_ACTIONS
from motile_tracker.data_views.views.layers.click_utils import (
    detect_side_button,
)
from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    get_features_from_tracks,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TrackTableModel(QAbstractTableModel):
    """Lazy table model backing the tracks table.

    Holds the data as columns of numpy arrays (one row per node) and serves
    values/colors on demand, so the view only ever realizes the handful of rows
    currently visible. This keeps memory and populate-time O(visible rows)
    regardless of the total node count (a ``QTableWidget`` would instead create
    one ``QTableWidgetItem`` per cell, which blows up memory and freezes the UI
    for large datasets).
    """

    def __init__(self, parent=None, decimals: int = 3):
        super().__init__(parent)
        self._table: dict[str, np.ndarray] = {}
        self._columns: list[str] = []
        self._nrows = 0
        self._decimals = decimals
        self._bg: list[QColor] = []
        self._fg: list[QColor] = []

    def set_table(self, table: dict[str, np.ndarray], colormap: TrackColormap) -> None:
        """Replace the table contents and precompute per-row colors."""
        self.beginResetModel()
        self._table = table
        self._columns = list(table.keys())
        self._nrows = len(next(iter(table.values()))) if table else 0

        # Precompute one background/foreground color per row (O(rows), cheap;
        # no per-cell widget objects are created).
        self._bg = []
        self._fg = []
        ids = table.get("ID")
        if ids is not None and len(ids) > 0 and colormap is not None:
            # Single vectorized get_colors call over all row node ids:
            # per-node lookups have a large fixed overhead, so mapping
            # row-by-row is O(rows) slow. Map once, then build per-row QColors.
            mapped = colormap.get_colors(np.asarray(ids))
            for rgba in mapped:
                if rgba[3] == 0:
                    rgba = [0, 0, 0, 0]
                r, g, b = int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
                self._bg.append(QColor(r, g, b))
                luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
                self._fg.append(
                    QColor(0, 0, 0) if luminance > 140 else QColor(255, 255, 255)
                )
        self.endResetModel()

    def rowCount(self, parent=None) -> int:
        if parent is not None and parent.isValid():
            return 0  # flat table: child rows don't exist
        return self._nrows

    def columnCount(self, parent=None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._columns[section]
        return None

    def _format(self, value) -> str:
        try:
            number = float(value)
        except (ValueError, TypeError):
            return str(value)
        if float(number).is_integer():
            return str(int(number))
        return f"{number:.{self._decimals}f}"

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if role == Qt.DisplayRole:
            return self._format(self._table[self._columns[col]][row])
        if role == Qt.BackgroundRole:
            return self._bg[row] if row < len(self._bg) else None
        if role == Qt.ForegroundRole:
            return self._fg[row] if row < len(self._fg) else None
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled


class NoSelectionHighlightDelegate(QStyledItemDelegate):
    """Prevents Qt from painting the default selection background,
    preserving each row's custom background color, and draws a cyan border instead."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)

        # Read the selection state straight off the style option: Qt already
        # computed it for this cell. Asking the view instead (via
        # selectedIndexes()) would rebuild the full selection on every single
        # cell paint, making each repaint O(visible cells x selected cells) --
        # ~15s for a 25k-row table with everything selected.
        # With SelectRows behavior every cell of a selected row carries this
        # flag, so a whole-row border still gets drawn.
        selected = bool(opt.state & QStyle.State_Selected)
        opt.state &= ~QStyle.State_Selected

        # Paint normally first (preserving the model's Background + Foreground roles)
        super().paint(painter, opt, index)

        # Draw a cyan border around the *entire row* if selected
        if selected:
            painter.setPen(QPen(Qt.cyan, 2))
            painter.drawRect(opt.rect.adjusted(1, 1, -2, -2))


class CustomTableWidget(QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verticalHeader().setSectionsClickable(False)
        self._drag_start_row = None

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse click events and check modifiers for different behaviors:
        - Plain click: single selection, toggle if already selected
        - Shift: append to selection.
        - Ctrl/CMD: center node, should not affect selection.
        - Side buttons (back/forward): navigate selection history.
        """
        # Intercept mouse side buttons for selection history navigation
        side_button = detect_side_button(event)

        if side_button is not None:
            self.parent().tracks_viewer.select_node_set_from_history(
                previous=side_button == 4
            )
            return

        # Handle other clicks for new selection and centering
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        row = index.row()
        modifiers = event.modifiers()

        ctrl = modifiers & Qt.ControlModifier
        shift = modifiers & Qt.ShiftModifier

        sel_model = self.selectionModel()
        model_index = self.model().index(row, 0)

        if ctrl:
            self.parent().center_node(model_index)
            event.accept()
            return

        if shift:
            # Append single row
            sel_model.select(
                model_index, QItemSelectionModel.Select | QItemSelectionModel.Rows
            )
            self._drag_start_row = row
            event.accept()
            return

        # Plain click: single selection, toggle if already selected
        if sel_model.isSelected(model_index):
            sel_model.select(
                model_index, QItemSelectionModel.Deselect | QItemSelectionModel.Rows
            )
            self._drag_start_row = None
        else:
            sel_model.clearSelection()
            sel_model.select(
                model_index, QItemSelectionModel.Select | QItemSelectionModel.Rows
            )
            self._drag_start_row = row

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Record mouse drag events to select a range. In combination with shift, it is
        possible to select multiple ranges.
        """

        if not (event.buttons() & Qt.LeftButton):
            return

        index = self.indexAt(event.pos())
        if not index.isValid() or self._drag_start_row is None:
            return

        current_row = index.row()
        start = self._drag_start_row
        end = current_row

        top = min(start, end)
        bottom = max(start, end)

        selection = QItemSelection(
            self.model().index(top, 0),
            self.model().index(bottom, self.model().columnCount() - 1),
        )

        modifiers = event.modifiers()

        if modifiers & Qt.ShiftModifier:
            # add range
            self.selectionModel().select(selection, QItemSelectionModel.Select)
        else:
            # replace selection with this range
            self.selectionModel().select(selection, QItemSelectionModel.ClearAndSelect)

        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start_row = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events for common tracksviewer actions."""
        # Get the parent ColoredTableWidget to access tracks_viewer
        parent = self.parent()
        if parent is None or not hasattr(parent, "tracks_viewer"):
            super().keyPressEvent(event)
            return

        tracks_viewer = parent.tracks_viewer

        # Get the action name from the general keybind mapping
        action_name = GENERAL_KEY_ACTIONS.get(event.key())
        if action_name:
            method = getattr(tracks_viewer, action_name, None)
            if method:
                method()
                event.accept()
                return

        # Allow parent class to handle other events
        super().keyPressEvent(event)


class ColoredTableWidget(QWidget):
    """Customized table widget with colored rows based on label colors in a napari Labels layer"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.update_track_df(
            initialization=True, refresh_view=True
        )  # make sure tracks_viewer initializes/updates the track df
        self.tracks_viewer.table_widget_present = True
        self.tracks_viewer.tracks_updated.connect(self.update_data)

        self._table = {}
        self._id_to_row: dict[int, int] = {}
        self.ascending = False  # for choosing whether to sort ascending or descending
        self._syncing = False

        self._table_widget = CustomTableWidget()
        self._model = TrackTableModel(self._table_widget)
        self._table_widget.setModel(self._model)

        # Custom delegate: preserve per-row background color and draw the cyan
        # selection border (set once; the model handles formatting/colors).
        self._table_widget.setItemDelegate(
            NoSelectionHighlightDelegate(self._table_widget)
        )

        self.update_data()

        # Connect to single click in the header to sort the table.
        self._table_widget.horizontalHeader().sectionClicked.connect(self._sort_table)

        # Instruction label to explain mouse and keyboard functions.
        label = QLabel(
            "Use left mouse click to select and center a label. Use Ctrl/CMD to center a node, Shift to append to selection. Use mouse drag to select a range."
        )
        label.setWordWrap(True)
        font = label.font()
        font.setItalic(True)
        label.setFont(font)

        main_layout = QVBoxLayout()
        main_layout.addWidget(label)
        main_layout.addWidget(self._table_widget)
        self.setLayout(main_layout)
        self.setMinimumHeight(300)

        # Selection behavior
        self._table_widget.setStyleSheet("""
            QTableView::item:selected {
                border: 2px solid cyan;
            }
        """)

        self._table_widget.verticalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: rgb(40,40,40);       /* normal */
                color: white;
                padding: 4px;
                border: 1px solid #555;
            }

            QHeaderView::section:selected {            /* when the row is selected */
                background-color: cyan;
                color: black;
            }

            QHeaderView::section:pressed {
                background-color: cyan;
                color: black;
            }
        """)

        self._table_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        self._table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)

        self._table_widget.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.tracks_viewer.node_selection_updated.connect(self._update_selected)
        self.tracks_viewer.center_node.connect(self.scroll_to_node)

    def cleanup(self) -> None:
        """Stop following the TracksViewer.

        Called by MenuManager when the dock is destroyed, so we can stop listening to
        TracksViewer update signals to rebuild the table.
        """
        self.tracks_viewer.table_widget_present = False
        for signal, slot in (
            (self.tracks_viewer.tracks_updated, self.update_data),
            (self.tracks_viewer.node_selection_updated, self._update_selected),
            (self.tracks_viewer.center_node, self.scroll_to_node),
        ):
            with contextlib.suppress(ValueError, KeyError, RuntimeError):
                signal.disconnect(slot)

    def update_data(self, **kwargs) -> None:
        """Update the displayed data based on the tracks_df on TracksViewer"""

        columns_to_display = ["node_id"] + get_features_from_tracks(
            self.tracks_viewer.tracks, features_to_ignore=["Bounding box"]
        )
        self.set_data(self.tracks_viewer.track_df, columns_to_display)

    def _update_selected(self) -> None:
        """Select the rows belonging to the nodes that are in the selection list of the
        TracksViewer
        """
        if self._syncing:
            return

        self._syncing = True
        try:
            selected_nodes = self.tracks_viewer.selected_nodes.as_list
            rows = [
                self._find_row(ID=node) for node in selected_nodes if node is not None
            ]

            self._table_widget.clearSelection()
            self._select_rows(rows)

        finally:
            self._syncing = False

    def _select_rows(self, rows: list[int]) -> None:
        """Replace current table selection with given rows.

        Args:
            rows (list[int]): list of indices to be selected.
        """

        if not rows:
            return

        model = self._table_widget.model()
        selection_model = self._table_widget.selectionModel()

        selection = QItemSelection()

        for row in rows:
            if row is None:
                continue
            index = model.index(row, 0)
            selection.select(index, index)

        selection_model.select(
            selection,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )

    def _on_selection_changed(self, *args) -> None:
        """Update the node selection list on TracksViewer based on the rows selected in
        the table.
        """
        if self._syncing:
            return  # skip if selection was changed programmatically

        rows = sorted({index.row() for index in self._table_widget.selectedIndexes()})
        if not rows:
            return

        labels = [self._table["ID"][row] for row in rows]

        # Ensure we do not call this when it is still updating.
        self._syncing = True
        try:
            self.tracks_viewer.selected_nodes.add_list(labels)
        finally:
            self._syncing = False

    def center_node(self, index: int) -> None:
        """Call TracksViewer to center Viewer on the node of current index

        Args:
            index (int): the index in the table corresponding to the to be centered node.
        """
        if self._syncing:
            return

        self._syncing = True
        try:
            row = index.row()
            node = self._table["ID"][row]
            self.tracks_viewer.center_on_node(node)
        finally:
            self._syncing = False

    def scroll_to_node(self, node: int) -> None:
        """Identify the index of the node that was selected, and scroll to that index.

        Args:
            node (int): the node to scroll to.
        """

        if self._syncing:
            return

        self._syncing = True
        try:
            index = self._find_row(ID=node)
            if index is not None:
                selection_model = self._table_widget.selectionModel()

                model_index = self._table_widget.model().index(index, 0)

                if (
                    selection_model.isSelected(model_index)
                    and len(selection_model.selectedRows()) == 1
                ):
                    return

                self.scroll_to_row(index)

        finally:
            self._syncing = False

    def scroll_to_row(self, index: int) -> None:
        """Scroll to make sure the row is in view

        Args:
            index (int): the index to scroll to
        """
        self._table_widget.scrollTo(
            self._table_widget.model().index(index, 0),
            QAbstractItemView.PositionAtCenter,
        )

    def _find_row(self, **conditions) -> int | None:
        """
        Find the first row matching the given conditions (e.g. label=12, time_point=5)
        Returns: row index or None
        """

        # Fast path: lookup by node id (the only condition used in practice).
        if set(conditions) == {"ID"} and conditions["ID"] is not None:
            try:
                return self._id_to_row.get(int(conditions["ID"]))
            except (ValueError, TypeError):
                return None

        n_rows = len(self._table.get("ID", []))
        for row in range(n_rows):
            # Only check conditions that are not None
            if all(
                float(self._table[col][row]) == float(val)
                for col, val in conditions.items()
                if val is not None
            ):
                return row

        return None

    def set_data(
        self, df: pd.DataFrame, columns_to_display: list[str] | None = None
    ) -> None:
        """Set the content of the table from a dataframe.

        Args:
            df (pd.DataFrame): dataframe holding the tree widget data, one row per node.
            columns_to_display (list[str] | None): optional list of column headers to
                filter on (should correspond to the tracks features). Column 'node_id'
                should always be included.
        """

        if columns_to_display is not None and len(df.columns) > 0:
            df = df[[col for col in columns_to_display if col in df.columns]]
            df = df.rename(columns={"node_id": "ID"})
        table: dict[str, np.ndarray] = {col: df[col].to_numpy() for col in df.columns}

        self._table = table

        # Fast id -> row lookup for selection syncing / scrolling.
        if "ID" in table:
            self._id_to_row = {int(v): i for i, v in enumerate(table["ID"])}
        else:
            self._id_to_row = {}

        # Hand the data to the lazy model (no per-cell widgets are created).
        # tracks_viewer.colormap is kept in sync (set_tracks) by TracksViewer
        # itself on every tracks update/refresh.
        self._model.set_table(table, self.tracks_viewer.colormap)

    def _sort_table(self, column_index: int) -> None:
        """Sorts the table in ascending or descending order

        Args:
            column_index (int): The index of the clicked column header
        """

        selected_column = list(self._table.keys())[column_index]
        df = pd.DataFrame(self._table).sort_values(
            by=selected_column, ascending=self.ascending
        )
        self.ascending = not self.ascending

        self.set_data(df)
