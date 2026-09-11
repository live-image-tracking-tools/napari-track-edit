from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from warnings import warn

from appdirs import AppDirs
from fonticon_fa6 import FA6S
from funtracks.data_model import SolutionTracks, Tracks
from funtracks.import_export import import_from_geff
from napari._qt.qt_resources import QColoredSVGIcon
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon as qticon

from motile_tracker.import_export.geff_io import write_geff_over
from motile_tracker.import_export.menus.export_dialog import ExportDialog
from motile_tracker.import_export.menus.import_dialog import (
    ImportDialog,
)
from motile_tracker.import_export.sql_io import (
    SQL_SUFFIX,
    is_sql_backed,
    sql_database_path,
    tracks_from_sql,
)
from motile_tracker.motile.backend.motile_run import MotileRun

GEFF_SUFFIX = ".geff"

SQL_LOAD_OPTION = "SQL database"


def default_save_dir() -> Path:
    """Directory the save path starts in.

    The same appdirs location the sample data is downloaded to, so that saved
    tracks land somewhere the application already owns rather than in the
    user's home directory.
    """
    return Path(AppDirs("motile-tracker").user_data_dir)


def _as_solution_tracks(tracks: Tracks) -> SolutionTracks:
    """Return a SolutionTracks view of the given tracks.

    The list stores plain Tracks, but the views and actions downstream of
    view_tracks still require track IDs, so they are handed a SolutionTracks.
    Objects that are already SolutionTracks (including MotileRun) are passed
    through unchanged, so a solved run keeps its solver params and identity.

    Constructs directly rather than using SolutionTracks.from_tracks, which in
    funtracks 2.0.x reads features.tracklet_key off the graph before building
    anything. tracklet_key only declares which attribute *would* hold the
    tracklet id; whether it exists is a separate question (whether that key is
    in the FeatureDict). Tracks whose tracklet column was never created
    therefore raise KeyError there.

    TODO: remove once motile_tracker operates on Tracks directly and consumers
    call tracks.graph_solution themselves.
    """
    if isinstance(tracks, SolutionTracks):
        return tracks
    graph = tracks.graph_full
    if tracks.segmentation is not None and graph.metadata.get("shape") is None:
        # the new object needs to build its own segmentation view, assigning one via
        # _segmentation binds the old one, and then the user cannot update it via painting
        graph._update_metadata(shape=tuple(tracks.segmentation.shape))
    solution_tracks = SolutionTracks(
        graph,
        scale=tracks.scale,
        ndim=tracks.ndim,
        features=tracks.features,
    )
    # Only needed on funtracks < 2.1, where passing a FeatureDict makes
    # __init__ activate the declared features without computing the missing
    # ones. From 2.1 every Tracks already has track ids, so this finds nothing.
    features = solution_tracks.features
    missing = [
        key
        for key in (features.tracklet_key, features.lineage_key)
        if key is not None and key not in solution_tracks.graph.node_attr_keys()
    ]
    if missing:
        solution_tracks.enable_features(missing)
    return solution_tracks


class TracksButton(QWidget):
    # https://doc.qt.io/qt-5/qlistwidget.html#setItemWidget
    # I think this means if we want static buttons we can just make the row here
    # but if we want to change the buttons we need to do something more complex
    # Columns: Run name, save, export, delete buttons
    def __init__(self, tracks: Tracks, name: str):
        super().__init__()
        self.tracks = tracks
        self.name = QLabel(name)
        self.name.setFixedHeight(20)
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(20, 20)
        self.delete.setToolTip("Remove track result")
        save_icon = qticon(FA6S.floppy_disk, color="white")
        self.save = QPushButton(icon=save_icon)
        self.save.setToolTip("Save tracks")
        self.save.setFixedSize(20, 20)
        export_icon = qticon(FA6S.file_export, color="white")
        self.export = QPushButton(icon=export_icon)
        self.export.setFixedSize(20, 20)
        self.export.setToolTip("Export tracks to CSV, geff or a SQL database")
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.addWidget(self.name)
        layout.addWidget(self.save)
        layout.addWidget(self.export)
        layout.addWidget(self.delete)
        self.setLayout(layout)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint


class TracksList(QGroupBox):
    """Widget for holding in-memory Tracks. Emits a view_tracks signal whenever
    a run is selected in the list, useful for telling the TracksViewer to display the
    selected tracks.
    """

    view_tracks = Signal(Tracks, str)
    request_colormap = Signal()

    tracks_saved = Signal(object, Path)
    """Emitted after tracks are saved to disk. Arguments: (tracks, path).
    Dependent applications can connect to this signal to save additional
    data (e.g. solver parameters) alongside the tracks.

    The path is the geff store the tracks were written to. A geff is a zarr
    directory, and writing one only replaces geff-controlled groups, so
    listeners should write their own data *inside* this path: it survives the
    tracks being saved again over the same store."""

    tracks_loaded = Signal(object, Path)
    """Emitted after tracks are loaded from disk. Arguments: (tracks, path).
    Dependent applications can connect to this signal to load additional
    data (e.g. solver parameters) from the same location.

    The path is the geff store the tracks were read from, matching what
    tracks_saved reports for the same tracks, so data written inside it by a
    tracks_saved listener is found here. It is never a container a geff merely
    happened to be found inside.

    The exceptions are a CSV import, which reports the .csv file, and a v1 motile
    run directory, which reports the directory holding the networkx graph json. Listeners
    should tolerate a file as well as a directory."""

    def __init__(self):
        super().__init__(title="Results List")

        self.colormap = None
        self.file_dialog = QFileDialog()
        self.file_dialog.setFileMode(QFileDialog.Directory)
        self.file_dialog.setOption(QFileDialog.ShowDirsOnly, True)

        # Where the save button writes to. Auto-filled, but the user can point
        # it anywhere; edits last for the session. The label and browse button
        # sit above the directory field so that the path, which is long, gets
        # the full width of the dock.
        self._save_name_edited = False

        self.save_browse_button = QPushButton("Browse")
        self.save_browse_button.setAutoDefault(0)
        self.save_browse_button.clicked.connect(self._browse_save_dir)

        save_dir_header = QHBoxLayout()
        save_dir_header.addWidget(QLabel("Save directory:"))
        save_dir_header.addStretch()
        save_dir_header.addWidget(self.save_browse_button)

        self.save_dir_line = QLineEdit(str(default_save_dir()))

        # The .geff suffix is shown as a fixed label rather than being typed,
        # so the user cannot omit or misspell it. save_path() adds it back.
        self.save_name_line = QLineEdit()
        self.save_name_line.textEdited.connect(self._on_save_name_edited)

        save_name_row = QHBoxLayout()
        save_name_row.addWidget(QLabel("Save filename:"))
        save_name_row.addWidget(self.save_name_line)
        save_name_row.addWidget(QLabel(GEFF_SUFFIX))

        # Shown only for tracks stored in a database, where the save fields above
        # are about taking a geff snapshot rather than about not losing work.
        self.on_disk_label = QLabel()
        self.on_disk_label.setWordWrap(True)
        self.on_disk_label.setVisible(False)

        self.tracks_list = QListWidget()
        self.tracks_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tracks_list.itemSelectionChanged.connect(self._selection_changed)

        load_menu = QHBoxLayout()
        self.dropdown_menu = QComboBox()
        self.dropdown_menu.addItems(
            [
                "Tracks (geff)",
                SQL_LOAD_OPTION,
                "Motile Run",
                "External tracks from CSV",
                "External tracks from geff",
            ]
        )

        load_button = QPushButton("Load")
        load_button.clicked.connect(self.load_tracks)

        load_menu.addWidget(self.dropdown_menu)
        load_menu.addWidget(load_button)

        layout = QVBoxLayout()
        layout.addLayout(save_dir_header)
        layout.addWidget(self.save_dir_line)
        layout.addLayout(save_name_row)
        layout.addWidget(self.on_disk_label)
        layout.addWidget(self.tracks_list)
        layout.addLayout(load_menu)
        self.setLayout(layout)

    def _load_tracks(self, import_type: str) -> tuple[Tracks, str, Path | None] | None:
        """Load externally generated tracks (CSV or geff) via the import dialog.

        Returns (tracks, name, path), where the path may be None because the
        import dialog does not always know the file the tracks came from.
        """
        dialog = ImportDialog(import_type)
        if dialog.exec_() != QDialog.Accepted or dialog.tracks is None:
            return None
        return dialog.tracks, dialog.name, dialog.source_path

    def _browse_save_dir(self) -> None:
        """Let the user pick the directory that saved tracks are written to."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select save directory", self.save_dir_line.text()
        )
        if directory:
            self.save_dir_line.setText(directory)

    def _confirm_overwrite(self, path: Path) -> bool:
        """Ask before replacing something already at the save path.

        Saving no longer goes through a file dialog, so this is the only thing
        standing between a stray click and an overwritten store.
        """
        answer = QMessageBox.question(
            self,
            "Replace existing tracks?",
            f"{path} already exists. Replace it?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _on_save_name_edited(self) -> None:
        """Stop auto-filling the name once the user has typed their own.

        Connected to textEdited rather than textChanged, so that the
        programmatic setText in _update_save_name does not count as an edit.
        """
        self._save_name_edited = True

    def _update_save_name(self, name: str) -> None:
        """Point the save name at the given tracks, unless the user renamed it.

        Names in the list are not unique, so this only ever changes the name
        field: the directory stays put, and a collision shows up as a visible
        name the user can edit rather than silently redirecting the save.

        The name is shown without its .geff suffix, which the UI displays as a
        fixed label beside the field.
        """
        if not self._save_name_edited:
            self.save_name_line.setText(name.removesuffix(GEFF_SUFFIX))

    def save_path(self) -> Path | None:
        """The geff store that the save button writes to.

        Combines the save directory with the filename and re-attaches the
        .geff suffix that the UI shows as a fixed label. Returns None if
        either field is blank.
        """
        directory = self.save_dir_line.text().strip()
        name = self.save_name_line.text().strip().removesuffix(GEFF_SUFFIX)
        if not directory or not name:
            return None
        return Path(directory) / f"{name}{GEFF_SUFFIX}"

    def _selection_changed(self):
        selected = self.tracks_list.selectedItems()
        # Updated even with nothing selected: removing the last database-backed
        # row would otherwise leave the note up, still claiming edits are being
        # written to a database that is no longer open.
        self._update_on_disk_label(
            self.tracks_list.itemWidget(selected[0]).tracks if selected else None
        )
        if selected:
            tracks_button = self.tracks_list.itemWidget(selected[0])
            name = tracks_button.name.text()
            self._update_save_name(name)
            self.view_tracks.emit(_as_solution_tracks(tracks_button.tracks), name)

    def _update_on_disk_label(self, tracks: Tracks | None) -> None:
        """Say so when the selected tracks are already stored in a database.

        Saving still writes a geff for every backend, so without this the save
        fields read as the only thing standing between the user and lost work,
        which for a database-backed session is not true.

        Args:
            tracks (Tracks | None): The tracks now selected, or None if the
                selection was cleared.
        """
        database = (
            sql_database_path(tracks)
            if tracks is not None and is_sql_backed(tracks)
            else None
        )
        if database is None:
            self.on_disk_label.setVisible(False)
            return
        self.on_disk_label.setText(
            f"<i>Stored in <b>{database}</b> and saved there as you edit. "
            f"Saving writes a separate geff snapshot.</i>"
        )
        self.on_disk_label.setVisible(True)

    def add_tracks(self, tracks: Tracks, name: str, select=True):
        """Add tracks to the list and optionally select them. Will make a new
        row in the list UI representing the given tracks.

        Accepts any Tracks object directly (SolutionTracks, MotileRun, etc.).

        Note: selecting the tracks will also emit the selection changed event on
        the list.

        Args:
            tracks (Tracks): the tracks object to add to the results list.
            name (str): the name of the tracks to display
            select (bool, optional): Whether or not to select the new tracks item in the
                list (and thus display it in the tracks viewer). Defaults to True.
        """
        item = QListWidgetItem(self.tracks_list)
        tracks_row = TracksButton(tracks, name)
        self.tracks_list.setItemWidget(item, tracks_row)
        item.setSizeHint(tracks_row.minimumSizeHint())
        self.tracks_list.addItem(item)
        tracks_row.delete.clicked.connect(partial(self.remove_tracks, item))
        tracks_row.export.clicked.connect(partial(self.show_export_dialog, item))
        tracks_row.save.clicked.connect(partial(self.save_tracks, item))
        if select:
            self.tracks_list.setCurrentRow(len(self.tracks_list) - 1)

    def show_export_dialog(self, item: QListWidgetItem) -> None:
        """Prompt user to choose export format (csv, geff or SQL database), then
        export the tracks object from the list accordingly.
        You must pass the list item that represents the tracks, not the tracks object
        itself.

        Exporting to a database can also switch the session over to it, in which
        case the dialog hands back a new tracks object and the row is repointed
        at it.

        Args:
            item (QListWidgetItem):  The list item containing the TracksButton that
                represents a set of tracks.
        """

        widget: TracksButton = self.tracks_list.itemWidget(item)
        tracks: Tracks = widget.tracks
        name: str = widget.name.text()
        self.request_colormap.emit()
        colormap = self.colormap

        result = ExportDialog.show_export_dialog(
            self, tracks=tracks, name=name, colormap=colormap
        )
        if isinstance(result, Tracks):
            self._replace_tracks(item, result)

    def _replace_tracks(self, item: QListWidgetItem, tracks: Tracks) -> None:
        """Point a row at a different tracks object and redisplay it.

        Re-selecting is what makes the swap visible: it drives _selection_changed,
        which re-emits view_tracks, which has TracksViewer rebuild the layers and
        the tree against the new graph.

        Args:
            item (QListWidgetItem): The row to repoint.
            tracks (Tracks): The tracks it should now hold.
        """
        widget: TracksButton = self.tracks_list.itemWidget(item)
        widget.tracks = tracks
        if self.tracks_list.currentItem() is item:
            # Already selected, so setCurrentItem would not emit anything.
            self._selection_changed()
        else:
            self.tracks_list.setCurrentItem(item)

    def save_tracks(self, item: QListWidgetItem):
        """Saves a tracks object from the list. You must pass the list item that
        represents the tracks, not the tracks object itself.

        Writes a geff store at the path shown in the save fields above the
        list, confirming first if something is already there. A MotileRun
        additionally stores its solver params inside that store.

        After saving, emits the tracks_saved signal with the geff store that
        was written, so that downstream code can save additional data inside
        it.

        Args:
            item (QListWidgetItem): The list item to save. This list item
                contains the TracksButton that represents a set of tracks.
        """
        saved_path = self.save_path()
        if saved_path is None:
            warn(
                "Cannot save without both a save directory and a filename.",
                stacklevel=2,
            )
            return
        if saved_path.exists() and not self._confirm_overwrite(saved_path):
            return

        widget: TracksButton = self.tracks_list.itemWidget(item)
        tracks: Tracks = widget.tracks
        saved_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(tracks, MotileRun):
            tracks.save(saved_path)
        else:
            write_geff_over(tracks, saved_path)
        self.tracks_saved.emit(tracks, saved_path)

    def remove_tracks(self, item: QListWidgetItem):
        """Remove a tracks object from the list. You must pass the list item that
        represents the tracks, not the tracks object itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the TracksButton that represents a set of tracks.
        """
        row = self.tracks_list.indexFromItem(item).row()
        self.tracks_list.takeItem(row)

    def load_tracks(self):
        """Load tracks from disk, depending on the choice in the dropdown menu.

        Each loader returns the loaded tracks along with the name to display and
        the path they came from, or None if the user cancelled or the load
        failed. Adding the tracks to the list and announcing them via
        tracks_loaded happens here, so every load route behaves the same way.
        """
        selection = self.dropdown_menu.currentText()
        if selection == "Tracks (geff)":
            result = self.load_internal_tracks()
        elif selection == SQL_LOAD_OPTION:
            result = self.load_sql_tracks()
        elif selection == "Motile Run":
            result = self.load_motile_run()
        elif selection == "External tracks from CSV":
            result = self._load_tracks(import_type="csv")
        elif selection == "External tracks from geff":
            result = self._load_tracks("geff")
        else:
            return

        if result is None:
            return
        tracks, name, source_path = result
        self.add_tracks(tracks, name, select=True)
        if source_path is not None:
            self.tracks_loaded.emit(tracks, source_path)

    def _load_from_dialog(
        self,
        loader: Callable[[Path], Tracks],
        geff_path: Callable[[Path], Path | None] | None = None,
    ) -> tuple[Tracks, str, Path] | None:
        """Ask the user for a directory and load tracks from it with `loader`.

        The name shown in the list comes from the directory the user picked. The
        reported path is the geff store that was actually read, which `geff_path`
        resolves when the user picks a directory containing one rather than the
        store itself.

        Returns (tracks, name, path), or None if the user cancelled or the
        directory did not contain loadable tracks.
        """
        if not self.file_dialog.exec_():
            return None
        directory = Path(self.file_dialog.selectedFiles()[0])
        try:
            tracks = loader(directory)
        except (ValueError, FileNotFoundError) as e:
            warn(f"Could not load tracks from {directory}: {e}", stacklevel=2)
            return None
        source = directory if geff_path is None else geff_path(directory)
        return tracks, directory.stem, source or directory

    def load_internal_tracks(self) -> tuple[Tracks, str, Path] | None:
        """Load tracks saved in internal format. The user selects the GEFF
        store directly (the path written by :func:`write_to_geff`).
        """
        return self._load_from_dialog(import_from_geff)

    def load_sql_tracks(self) -> tuple[Tracks, str, Path] | None:
        """Open an existing tracks database.

        The database is opened in place rather than read into memory, so from
        here on every edit is written to that file as it is made. Cannot go
        through _load_from_dialog, which asks for a directory: a database is a
        single file.

        A database that records no scale loads without one, exactly as loading a
        geff does - tracks with no scale are an ordinary state throughout the
        application, so this is not worth interrupting the load to ask about.
        """
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open tracks database",
            str(default_save_dir()),
            f"SQLite database (*{SQL_SUFFIX});;All files (*)",
        )
        if not path_str:
            return None
        path = Path(path_str)

        try:
            tracks = tracks_from_sql(path)
        except Exception as e:  # noqa: BLE001 - any driver error means "not loadable"
            warn(f"Could not load tracks from {path}: {e}", stacklevel=2)
            return None
        return tracks, path.stem, path

    def load_motile_run(self) -> tuple[Tracks, str, Path] | None:
        """Load a MotileRun from disk. The user selects the directory created
        by MotileRun.save(), and the geff store inside it is reported.
        """
        return self._load_from_dialog(MotileRun.load, geff_path=MotileRun.geff_path)
