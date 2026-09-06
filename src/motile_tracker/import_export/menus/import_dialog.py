from pathlib import Path

import numpy as np
from funtracks.import_export import (
    has_embedded_segmentation,
    import_from_geff,
    tracks_from_df,
)
from funtracks.import_export.magic_imread import magic_imread
from geff_spec.utils import axes_from_lists
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.import_export.menus.csv_dimension_widget import (
    DimensionWidget,
)
from motile_tracker.import_export.menus.csv_import_widget import (
    ImportCSVWidget,
)
from motile_tracker.import_export.menus.geff_import_utils import geff_group_path
from motile_tracker.import_export.menus.geff_import_widget import (
    ImportGeffWidget,
)
from motile_tracker.import_export.menus.prop_map_widget import StandardFieldMapWidget
from motile_tracker.import_export.menus.scale_widget import ScaleWidget
from motile_tracker.import_export.menus.segmentation_widgets import (
    CSVSegmentationWidget,
    GeffSegmentationWidget,
)


class ImportDialog(QDialog):
    """Dialog for importing external tracks from CSV or geff."""

    def __init__(self, import_type: str = "csv") -> None:
        """
        Construct import dialog depending on the data type.

        Args:
            import_type (str): either 'geff' or 'csv'
        """

        super().__init__()
        self.import_type = import_type
        self.seg = None
        self.df = None
        self.incl_z = False
        self.source_path: Path | None = None
        self.setWindowTitle(f"Import external tracks from {import_type.upper()}")
        self.name = f"Tracks from {import_type.upper()}"

        # cancel and finish buttons
        self.button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.finish_button = QPushButton("Finish")
        self.finish_button.setEnabled(False)
        self.button_layout.addWidget(self.cancel_button)
        self.button_layout.addWidget(self.finish_button)

        # Connect button signals
        self.cancel_button.clicked.connect(self._cancel)
        self.finish_button.clicked.connect(self._finish)
        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.finish_button.setDefault(False)
        self.finish_button.setAutoDefault(False)

        # Initialize widgets and connect to update signals
        self.prop_map_widget = StandardFieldMapWidget()
        self.prop_map_widget.props_updated.connect(self._update_finish_button)
        self.scale_widget = ScaleWidget()

        if import_type == "geff":
            self.import_widget = ImportGeffWidget()
            self.import_widget.update_buttons.connect(self._update_segmentation_widget)
            self.segmentation_widget = GeffSegmentationWidget(
                root=self.import_widget.root
            )
        else:
            self.import_widget = ImportCSVWidget()
            self.segmentation_widget = CSVSegmentationWidget()
            self.dimension_widget = DimensionWidget()
            self.dimension_widget.update_dims.connect(self._update_field_map_and_scale)

        self.import_widget.update_buttons.connect(self._update_field_map_and_scale)
        self.segmentation_widget.seg_updated.connect(self._update_field_map_and_scale)

        self.content_widget = QWidget()
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.addWidget(self.import_widget)
        if import_type == "csv":
            main_layout.addWidget(self.dimension_widget)
        main_layout.addWidget(self.segmentation_widget)
        main_layout.addWidget(self.prop_map_widget)
        main_layout.addWidget(self.scale_widget)
        main_layout.addLayout(self.button_layout)
        self.content_widget.setLayout(main_layout)

        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.content_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setMinimumWidth(500)
        self.scroll_area.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.MinimumExpanding
        )

        dialog_layout = QVBoxLayout()
        dialog_layout.addWidget(self.scroll_area)
        self.setLayout(dialog_layout)

    def _update_field_map_and_scale(self, checked: bool | None = None) -> None:
        """Update field map and scale widget based on segmentation selection."""

        self.seg = (
            self.segmentation_widget.include_seg() if checked is None else not checked
        )

        if self.import_type == "csv":
            self.incl_z = self.dimension_widget.incl_z
            self.df = self.import_widget.df
            if self.df is not None:
                self.prop_map_widget.extract_csv_property_fields(
                    self.df, self.seg, self.incl_z
                )
                if self.seg:
                    self.scale_widget.update(incl_z=self.incl_z)
            else:
                self.prop_map_widget.setVisible(False)
                self.scale_widget.setVisible(False)

        elif self.import_type == "geff":
            if self.import_widget.root is not None:
                geff_metadata = dict(self.import_widget.root.attrs.get("geff", {}))
                if "axes" not in geff_metadata:
                    self.infer_dims_from_segmentation()  # read dims from segmentation if
                    # no axes are available in geff metadata
                if self.seg:
                    self.scale_widget.update(
                        dict(self.import_widget.root.attrs.get("geff", {})),
                        incl_z=self.incl_z,
                    )

                self.prop_map_widget.extract_geff_property_fields(
                    self.import_widget.root,
                    self.seg,
                    self.incl_z,
                    seg_for_features=self.seg
                    or has_embedded_segmentation(
                        geff_group_path(self.import_widget.root)
                    ),
                )

            else:
                self.prop_map_widget.setVisible(False)
                self.scale_widget.setVisible(False)

        # Check whether we should keep seg_id visible in the fields widget
        if len(self.prop_map_widget.mapping_widgets) > 0:
            self.prop_map_widget.mapping_widgets["seg_id"].setVisible(self.seg)
            self.prop_map_widget.mapping_labels["seg_id"].setVisible(self.seg)

        self._update_finish_button()
        self.scale_widget.setVisible(self.seg)

        self._resize_dialog()

    def infer_dims_from_segmentation(self) -> None:
        """Infer whether to include z dimension based on the selected segmentation file,
        if present. If not present, we do allow incl_z (but the user can select 'None' if
        it is 2D + time data without segmentation.)."""

        # Check if user has selected to include segmentation
        self.seg = self.segmentation_widget.include_seg()

        if not self.seg:
            self.incl_z = (
                True  # when no segmentation is selected, we cannot infer dims,
            )
            # so we keep z in case it is needed
            return

        seg_path = self.segmentation_widget.get_segmentation_path()
        if seg_path is not None and seg_path.exists():
            try:
                # Load segmentation to determine ndim
                seg = magic_imread(seg_path, use_dask=True)
                ndim = seg.ndim
                self.incl_z = ndim == 4

            except (OSError, ValueError, RuntimeError, KeyError) as e:
                # If loading fails, hide the scale widget and show error
                QMessageBox.warning(
                    self,
                    "Invalid Segmentation",
                    f"Could not load segmentation file:\n{seg_path}\n\nError: {e}",
                )
                return

    def _update_segmentation_widget(self) -> None:
        """Refresh the geff segmentation widget based on the geff root group."""

        self.segmentation_widget.setVisible(False)
        if self.import_widget.root is not None:
            self.segmentation_widget.update_root(self.import_widget.root)
        self._update_finish_button()
        self._resize_dialog()

    def _resize_dialog(self) -> None:
        """Dynamic widget resizing depending on the visible contents"""

        self.content_widget.layout().activate()
        self.content_widget.adjustSize()
        self.content_widget.updateGeometry()
        content_hint = self.content_widget.sizeHint()

        # Determine the screen the dialog is currently on
        current_screen = QApplication.screenAt(self.frameGeometry().center())
        if current_screen is None:
            current_screen = QApplication.primaryScreen()
        screen_geometry = current_screen.availableGeometry()

        max_height = int(screen_geometry.height() * 0.85)
        new_height = min(content_hint.height(), max_height)
        new_width = max(content_hint.width(), 700)

        self.resize(new_width, new_height)

        # Center horizontally, but upwards if too tall
        screen_center = screen_geometry.center()
        x = screen_center.x() - self.width() // 2

        if new_height < screen_geometry.height():
            y = screen_center.y() - new_height // 2
        else:
            y = screen_geometry.top() + 50

        self.move(x, y)

    def _update_finish_button(self) -> None:
        """Update the finish button status depending on whether a segmentation is required
        and whether a valid geff root or pandas dataframe is present. Duplicate region
        properties are not allowed."""

        include_seg = self.segmentation_widget.include_seg()
        has_seg = self.segmentation_widget.get_segmentation_path() is not None
        valid_seg = not (include_seg and not has_seg)

        if self.import_type == "geff":
            self.finish_button.setEnabled(
                self.import_widget.root is not None
                and valid_seg
                and not self.prop_map_widget.has_duplicates
            )
        else:
            self.finish_button.setEnabled(
                self.import_widget.df is not None
                and valid_seg
                and not self.prop_map_widget.has_duplicates
            )

    def _cancel(self) -> None:
        """Close the dialog without loading tracks."""
        self.reject()

    def _generate_axes_metadata(
        self,
        name_map: dict[str, str | None],
        scale: list[float] | None,
        segmentation_path: Path,
    ) -> None:
        """Generate axes metadata when missing from geff file.

        Uses the user-provided name_map and scale information to construct
        axes metadata that matches the segmentation dimensionality.

        Args:
            name_map: Mapping from standard fields (t, z, y, x) to node property names
            scale: Scale values from scale widget [t, (z), y, x]
            segmentation_path: Path to segmentation file to determine ndim
        """
        # Load segmentation to get ndim
        seg = magic_imread(segmentation_path, use_dask=True)
        ndim = seg.ndim

        # Build axis names and types based on dimensionality
        # Use "time" to match standard_fields
        if ndim == 3:  # 2D+time
            axis_keys = ["time", "y", "x"]
            axis_types = ["time", "space", "space"]
        else:  # 3D+time (ndim == 4)
            axis_keys = ["time", "z", "y", "x"]
            axis_types = ["time", "space", "space", "space"]

        # Get actual node property names from name_map
        axis_names = []
        for key in axis_keys:
            prop_name = name_map.get(key)
            if prop_name is None:
                # Fall back to standard name if not in name_map
                prop_name = key
            axis_names.append(prop_name)

        # Use provided scale or default to 1.0
        axis_scales = [1.0] * ndim if scale is None else scale

        # Generate axes using geff_spec utility
        axes = axes_from_lists(
            axis_names=axis_names,
            axis_types=axis_types,
            axis_scales=axis_scales,
        )

        # Inject into geff root attrs
        geff_metadata = dict(self.import_widget.root.attrs.get("geff", {}))
        geff_metadata["axes"] = [ax.model_dump(exclude_none=True) for ax in axes]
        self.import_widget.root.attrs["geff"] = geff_metadata

    def _ensure_area_enabled(self) -> None:
        """Enable the area feature when segmentation is present.

        Recomputes only when area is missing from the graph schema (e.g. a GEFF
        imported without an area attribute); otherwise reuses existing values.
        """
        if self.tracks.segmentation is not None and "area" not in self.tracks.features:
            recompute = "area" not in self.tracks.graph.node_attr_keys()
            self.tracks.enable_features(["area"], recompute=recompute)

    def _maybe_convert_legacy_masks(self, geff_dir: Path) -> bool:
        """Offer to convert masks stored in an older, memory-heavy dtype.

        Geff files written by older versions of tracksdata store segmentation
        masks as integers (e.g. ``uint64``) rather than ``bool``, using ~8x more
        memory when read, which can run out of memory on large datasets. If such
        masks are detected, warn the user and offer a lossless, in-place
        conversion of the mask buffer (the rest of the geff is untouched).

        Returns:
            bool: True to continue the import, False if the user cancelled or the
            conversion failed.
        """
        # TODO: the geff dtype helpers are only on tracksdata main
        # (royerlab/tracksdata#319). Once released, add a tracksdata floor to
        # pyproject.toml and import these at module level.
        try:
            from tracksdata.constants import DEFAULT_ATTR_KEYS
            from tracksdata.io import convert_geff_prop_dtype, geff_prop_dtype
        except ImportError:
            return True  # older tracksdata without the utility; import as before

        mask_key = DEFAULT_ATTR_KEYS.MASK
        try:
            dtype = geff_prop_dtype(geff_dir, mask_key)
        except Exception:  # noqa: BLE001
            return True  # detection failed; don't block the import

        if dtype is None or dtype == np.bool_:
            return True

        answer = QMessageBox.question(
            self,
            "Old mask format detected",
            f"This geff stores segmentation masks as '{dtype}', an older format that "
            "uses about 8x more memory when loaded.\n\n"
            "Convert them to boolean now? The conversion is lossless, but it edits "
            f"{geff_dir.name} in place.",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.No:
            return True  # load as-is

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            convert_geff_prop_dtype(geff_dir, mask_key, np.bool_)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Failed to convert masks: {e}")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        return True

    def _finish(self) -> None:
        """Tries to read the csv/geff file and optional segmentation image and apply the
        attribute to column mapping to construct a Tracks object"""

        if self.import_type == "geff":
            if self.import_widget.root is not None:
                store_path = self.import_widget.store_path
                group_path = Path(self.import_widget.root.path)  # e.g. 'tracks'
                geff_dir = store_path / group_path

                if not self._maybe_convert_legacy_masks(geff_dir):
                    return

                self.name = self.import_widget.dir_name
                scale = self.scale_widget.get_scale() if self.seg else None

                segmentation_path = self.segmentation_widget.get_segmentation_path()
                name_map = self.prop_map_widget.get_name_map()
                # Remove entries with "None" value - funtracks doesn't accept None mappings
                name_map = {k: v for k, v in name_map.items() if v != "None"}
                recompute_keys = self.prop_map_widget.get_recompute_keys()

                # When embedded segmentation is present (mask + bbox in graph) and no
                # external segmentation file is provided, ensure those attributes are
                # loaded so funtracks can reconstruct the segmentation as a
                # GraphArrayView.
                if segmentation_path is None and has_embedded_segmentation(geff_dir):
                    name_map.setdefault("mask", "mask")
                    name_map.setdefault("bbox", "bbox")

                # Generate axes metadata if missing (required for funtracks validation)
                geff_metadata = dict(self.import_widget.root.attrs.get("geff", {}))
                if "axes" not in geff_metadata:
                    if segmentation_path is not None:
                        self._generate_axes_metadata(name_map, scale, segmentation_path)
                    else:
                        if "z" not in name_map:
                            pass  # z already removed by filtering above
                try:
                    self.tracks = import_from_geff(
                        geff_dir,
                        name_map,
                        segmentation_path=segmentation_path,
                        scale=scale,
                    )
                    if recompute_keys:
                        self.tracks.enable_features(recompute_keys, recompute=True)
                    self._ensure_area_enabled()
                except Exception as e:  # noqa: BLE001
                    QMessageBox.critical(self, "Error", f"Failed to load tracks: {e}")
                    return
                # Report the geff group we actually read, not the container it
                # was found in: a listener uses this path to find data saved
                # alongside the tracks, and the container may hold several
                # groups.
                self.source_path = geff_dir
                self.accept()
        else:
            if self.df is not None:
                scale = self.scale_widget.get_scale()
                if self.seg:
                    segmentation = self.segmentation_widget.load_segmentation()
                    if segmentation is None:
                        return  # error loading segmentation already shown
                else:
                    segmentation = None
                node_name_map = self.prop_map_widget.get_name_map()
                # Remove entries with "None" value - funtracks doesn't accept None mappings
                node_name_map = {k: v for k, v in node_name_map.items() if v != "None"}
                recompute_keys = self.prop_map_widget.get_recompute_keys()

                try:
                    self.tracks = tracks_from_df(
                        self.df,
                        segmentation=segmentation,
                        scale=scale,
                        node_name_map=node_name_map,
                    )
                    if recompute_keys:
                        self.tracks.enable_features(recompute_keys, recompute=True)
                    self._ensure_area_enabled()
                except Exception as e:  # noqa: BLE001
                    QMessageBox.critical(self, "Error", f"Failed to load tracks: {e}")
                    return
                csv_text = self.import_widget.csv_path_line.text().strip()
                self.source_path = Path(csv_text) if csv_text else None
                self.accept()
