"""Integration test for CSV and GEFF import workflow.
Tests the full round-trip: export tracks using motile_tracker's method,
then import them back through the import dialog.
Also test for the visibility of various widgets based on 2D/3D and
segmentation inclusion.
"""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
import tifffile
import zarr
from funtracks.data_model import Tracks
from funtracks.import_export import (
    export_to_csv,
    export_to_geff,
    has_embedded_segmentation,
)

from motile_tracker.import_export.menus.import_dialog import ImportDialog
from motile_tracker.motile.backend.motile_run import MotileRun
from motile_tracker.motile.backend.solver_params import SolverParams


def _remove_geff_shape(root):
    """Remove the shape from a geff store's extra.tracksdata metadata (in place).

    Simulates a GEFF with mask/bbox but no shape (e.g. from an external tool).
    """
    geff_meta = dict(root.attrs["geff"])
    extra = dict(geff_meta.get("extra", {}))
    tracksdata = dict(extra.get("tracksdata", {}))
    tracksdata.pop("shape", None)
    extra["tracksdata"] = tracksdata
    geff_meta["extra"] = extra
    root.attrs["geff"] = geff_meta
    # funtracks also writes a legacy top-level "segmentation_shape" attr; drop it
    # too so the store truly has no shape metadata.
    if "segmentation_shape" in root.attrs:
        del root.attrs["segmentation_shape"]


@pytest.fixture(autouse=True)
def mock_qmessagebox(monkeypatch):
    """Mock QMessageBox to prevent blocking popups in all tests.

    Raises AssertionError if a critical dialog is shown, surfacing the error message.
    """
    mock_msgbox = MagicMock()

    def critical_side_effect(parent, title, message):
        raise AssertionError(f"Unexpected error dialog: {title} - {message}")

    mock_msgbox.critical.side_effect = critical_side_effect
    monkeypatch.setattr(
        "motile_tracker.import_export.menus.import_dialog.QMessageBox",
        mock_msgbox,
    )
    monkeypatch.setattr(
        "motile_tracker.import_export.menus.geff_import_widget.QMessageBox",
        mock_msgbox,
    )
    return mock_msgbox


@pytest.fixture
def small_csv(tmp_path: Path) -> Path:
    p = tmp_path / "test.csv"
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "parent_id": [None, 1],
            "time": [0, 1],
            "y": [10.0, 20.0],
            "x": [5.0, 15.0],
            "area": [100.0, 150.0],
            "group": [True, False],
        }
    )
    df.to_csv(p, index=False)
    return p


@pytest.mark.parametrize("dim_3d", [False, True])
@pytest.mark.parametrize("include_seg", [False, True])
def test_import_dialog_csv(qtbot, small_csv, dim_3d, include_seg):
    """Test CSV import, 2D/3D, with/without segmentation."""

    dialog = ImportDialog(import_type="csv")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    # Prepare import
    dialog.import_widget._load_csv(str(small_csv))

    # Set dimensions & segmentation state
    if include_seg:
        dialog.segmentation_widget.include_seg = lambda: True
    else:
        dialog.segmentation_widget.include_seg = lambda: False
    dialog.dimension_widget.incl_z = dim_3d

    # Trigger update
    dialog._update_field_map_and_scale(not include_seg)

    # Assertions
    # Scale widget visibility
    assert dialog.scale_widget.isVisible() is (include_seg)
    # seg_id visibility
    assert dialog.prop_map_widget.mapping_widgets["seg_id"].isVisible() is include_seg
    # z field included in 3D
    if dim_3d:
        assert "z" in dialog.prop_map_widget.standard_fields
    else:
        assert "z" not in dialog.prop_map_widget.standard_fields

    # Optional features behavior
    optional = dialog.prop_map_widget.optional_features
    if "area" in optional:
        combo = optional["area"]["feature_option"]
        combo.setCurrentIndex(combo.count() - 1)
        assert combo.currentText() == "Custom"
        assert optional["area"]["recompute"].isEnabled() is False
        combo.setCurrentIndex(0)
        if include_seg:
            assert optional["area"]["recompute"].isEnabled() is True
        else:
            assert optional["area"]["recompute"].isEnabled() is False


class TestPropMapWidgetKeys:
    """Test that prop_map_widget methods return correct feature keys."""

    def _setup_dialog(self, qtbot, small_csv, include_seg=True):
        """Helper to set up a dialog with the small_csv loaded."""
        dialog = ImportDialog(import_type="csv")
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitExposed(dialog)
        dialog.import_widget._load_csv(str(small_csv))

        if include_seg:
            dialog.segmentation_widget.include_seg = lambda: True
        else:
            dialog.segmentation_widget.include_seg = lambda: False
        dialog.dimension_widget.incl_z = False
        dialog._update_field_map_and_scale(not include_seg)
        return dialog

    def test_recompute_keys_uses_default_keys(self, qtbot, small_csv):
        """When a computed feature is selected with recompute, get_recompute_keys
        should use the annotator's default key (e.g. 'area')."""
        dialog = self._setup_dialog(qtbot, small_csv, include_seg=True)
        prop_map = dialog.prop_map_widget
        optional = prop_map.optional_features

        assert "area" in optional
        combo = optional["area"]["feature_option"]
        combo.setCurrentIndex(0)
        assert combo.currentText() == "Area"
        optional["area"]["attr_checkbox"].setChecked(True)
        optional["area"]["recompute"].setChecked(True)

        result = prop_map.get_recompute_keys()
        # Key should be "area" (default key), not "Area" (display name)
        assert "area" in result

    def test_load_from_column_in_name_map(self, qtbot, small_csv):
        """When loading a computed feature from a column (no recompute),
        it should appear in get_name_map as default_key -> column_name."""
        dialog = self._setup_dialog(qtbot, small_csv, include_seg=True)
        prop_map = dialog.prop_map_widget
        optional = prop_map.optional_features

        assert "area" in optional
        combo = optional["area"]["feature_option"]
        combo.setCurrentIndex(0)
        optional["area"]["attr_checkbox"].setChecked(True)
        optional["area"]["recompute"].setChecked(False)

        name_map = prop_map.get_name_map()
        assert "area" in name_map
        assert name_map["area"] == "area"  # column name

        # Not recomputing, so should not be in recompute_keys
        assert "area" not in prop_map.get_recompute_keys()

    def test_custom_feature_no_collision(self, qtbot, small_csv):
        """Custom feature with a name that doesn't collide uses its own name
        in get_name_map, and is excluded from get_recompute_keys."""
        dialog = self._setup_dialog(qtbot, small_csv, include_seg=True)
        prop_map = dialog.prop_map_widget
        optional = prop_map.optional_features

        # "group" column doesn't collide with any default key
        assert "group" in optional
        combo = optional["group"]["feature_option"]
        combo.setCurrentText("Custom")
        optional["group"]["attr_checkbox"].setChecked(True)

        name_map = prop_map.get_name_map()
        assert "group" in name_map
        assert name_map["group"] == "group"

        # Custom features are only in name_map, not in recompute_keys
        assert "group" not in prop_map.get_recompute_keys()

    def test_custom_feature_collision_gets_prefixed(self, qtbot, small_csv):
        """Custom feature whose name collides with a default key gets
        'custom_' prefix in get_name_map."""
        dialog = self._setup_dialog(qtbot, small_csv, include_seg=True)
        prop_map = dialog.prop_map_widget
        optional = prop_map.optional_features

        # "area" collides with the default area key
        assert "area" in optional
        combo = optional["area"]["feature_option"]
        combo.setCurrentText("Custom")
        optional["area"]["attr_checkbox"].setChecked(True)

        name_map = prop_map.get_name_map()
        assert "custom_area" in name_map
        assert name_map["custom_area"] == "area"
        assert "area" not in name_map or name_map.get("area") != "area"

        # Custom features are only in name_map, not in recompute_keys
        assert "custom_area" not in prop_map.get_recompute_keys()


def test_csv_import_2d_with_segmentation(
    qtbot, tmp_path, solution_tracks_2d, monkeypatch
):
    """Test exporting and re-importing 2D tracks with segmentation.
    This tests whether the full workflow works end-to-end.
    """
    # Mock _resize_dialog to avoid screen access in headless CI
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    # Create tracks and export to CSV (as motile_tracker does in tracks_list.py:208)
    tracks = solution_tracks_2d
    csv_path = tmp_path / "test_tracks.csv"
    export_to_csv(tracks, csv_path)

    # Also save the segmentation
    tifffile.imwrite(tmp_path / "segmentation.tif", np.asarray(tracks.segmentation))

    # Create import dialog and load the GEFF file
    dialog = ImportDialog(import_type="csv")
    qtbot.addWidget(dialog)

    # Load the CSV file
    dialog.import_widget._load_csv(csv_path)

    # Verify CSV root was loaded
    assert dialog.import_widget.df is not None, "Failed to load CSV df"

    # Select "Use external segmentation" option and set path
    dialog.segmentation_widget.external_segmentation_radio.setChecked(True)
    seg_path = tmp_path / "segmentation.tif"
    dialog.segmentation_widget.segmentation_widget.image_path_line.setText(
        str(seg_path)
    )
    dialog.segmentation_widget.segmentation_widget.valid = True
    dialog.segmentation_widget.segmentation_widget.seg_path_updated.emit()

    # Verify that seg and incl_z are True
    assert dialog.seg is True
    assert dialog.incl_z is False

    # Verify finish button is enabled
    assert dialog.finish_button.isEnabled() is True, (
        "Finish button should be enabled with valid CSV and segmentation"
    )

    # Map seg_id to the node "id" column since node id == seg_id
    prop_map = dialog.prop_map_widget
    seg_combo = prop_map.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("id")

    # Import the tracks
    dialog._finish()

    # Verify tracks were imported successfully
    assert hasattr(dialog, "tracks"), "Dialog should have tracks attribute after import"
    assert dialog.tracks is not None, "Tracks should not be None"
    assert dialog.tracks.graph.num_nodes() == solution_tracks_2d.graph.num_nodes()
    assert dialog.tracks.graph.num_edges() == solution_tracks_2d.graph.num_edges()
    assert dialog.tracks.ndim == 3

    # Area should be enabled and computed even though it was not in the CSV
    assert "area" in dialog.tracks.features
    for node_id in dialog.tracks.graph.node_ids():
        assert dialog.tracks.graph.nodes[node_id]["area"] > 0


def test_csv_import_3d_with_segmentation(
    qtbot, tmp_path, solution_tracks_3d, monkeypatch
):
    """Test exporting and re-importing 3D tracks with segmentation.
    This tests whether the full workflow works end-to-end.
    """
    # Mock _resize_dialog to avoid screen access in headless CI
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    # Create tracks and export to CSV (as motile_tracker does in tracks_list.py:208)
    tracks = solution_tracks_3d
    csv_path = tmp_path / "test_tracks.csv"
    export_to_csv(tracks, csv_path)

    # Also save the segmentation
    tifffile.imwrite(tmp_path / "segmentation.tif", np.asarray(tracks.segmentation))

    # Create import dialog and load the GEFF file
    dialog = ImportDialog(import_type="csv")
    qtbot.addWidget(dialog)

    # Load the CSV file
    dialog.import_widget._load_csv(csv_path)

    # Verify CSV root was loaded
    assert dialog.import_widget.df is not None, "Failed to load CSV df"

    # Make sure the dimension is set to 3D
    dialog.dimension_widget.radio_3D.setChecked(True)

    # Select "Use external segmentation" option and set path
    dialog.segmentation_widget.external_segmentation_radio.setChecked(True)
    seg_path = tmp_path / "segmentation.tif"
    dialog.segmentation_widget.segmentation_widget.image_path_line.setText(
        str(seg_path)
    )
    dialog.segmentation_widget.segmentation_widget.valid = True
    dialog.segmentation_widget.segmentation_widget.seg_path_updated.emit()

    # Verify that seg and incl_z are True
    assert dialog.seg is True
    assert dialog.incl_z is True

    # Verify finish button is enabled
    assert dialog.finish_button.isEnabled() is True, (
        "Finish button should be enabled with valid CSV and segmentation"
    )

    # Set seg_id mapping to "None" since node id == seg_id (automapping is incorrect)
    prop_map = dialog.prop_map_widget
    seg_combo = prop_map.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("id")
    prop_map._update_props_left()

    # Import the tracks
    dialog._finish()

    # Verify tracks were imported successfully
    assert hasattr(dialog, "tracks"), "Dialog should have tracks attribute after import"
    assert dialog.tracks is not None, "Tracks should not be None"
    assert dialog.tracks.graph.num_nodes() == solution_tracks_3d.graph.num_nodes()
    assert dialog.tracks.graph.num_edges() == solution_tracks_3d.graph.num_edges()
    assert dialog.tracks.ndim == 4


def test_csv_import_without_segmentation(
    qtbot, tmp_path, solution_tracks_2d_without_segmentation, monkeypatch
):
    """Test importing without segmentation."""
    # Mock _resize_dialog to avoid screen access in headless CI
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    # Create tracks and export to CSV (as motile_tracker does in tracks_list.py:208)
    tracks = solution_tracks_2d_without_segmentation
    csv_path = tmp_path / "test_tracks.csv"
    export_to_csv(tracks, csv_path)

    # Create import dialog and load the GEFF file
    dialog = ImportDialog(import_type="csv")
    qtbot.addWidget(dialog)

    # Load the CSV file
    dialog.import_widget._load_csv(csv_path)

    # Verify CSV root was loaded
    assert dialog.import_widget.df is not None, "Failed to load CSV df"

    # Select None for the segmentation, assert seg and incl_z are False, assert seg_id
    # mapping is hidden
    dialog.segmentation_widget.none_radio.setChecked(True)
    assert not dialog.seg
    assert not dialog.incl_z

    # Verify finish button is enabled
    assert dialog.finish_button.isEnabled() is True, (
        "Finish button should be enabled with valid CSV and segmentation"
    )

    # Import the tracks
    dialog._finish()

    # Verify tracks were imported successfully
    assert hasattr(dialog, "tracks"), "Dialog should have tracks attribute after import"
    assert dialog.tracks is not None, "Tracks should not be None"
    assert (
        dialog.tracks.graph.num_nodes()
        == solution_tracks_2d_without_segmentation.graph.num_nodes()
    )
    assert (
        dialog.tracks.graph.num_edges()
        == solution_tracks_2d_without_segmentation.graph.num_edges()
    )
    assert dialog.tracks.ndim == 3


@pytest.mark.parametrize(
    "graph_fixture, seg_fixture, ndim",
    [
        ("graph_2d_without_segmentation", "segmentation_2d", 3),
        ("graph_3d_without_segmentation", "segmentation_3d", 4),
    ],
)
def test_geff_import_with_segmentation(
    qtbot, tmp_path, graph_fixture, seg_fixture, ndim, monkeypatch, request
):
    """Test exporting and re-importing tracks with external segmentation.
    This tests whether the full workflow works end-to-end for 2D and 3D.
    """
    graph = request.getfixturevalue(graph_fixture)
    segmentation = request.getfixturevalue(seg_fixture)

    # Mock _resize_dialog to avoid screen access in headless CI
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    # Create tracks and export to GEFF (as motile_tracker does in tracks_list.py:237)
    tracks = Tracks(graph, ndim=ndim, time_attr="t", tracklet_attr="track_id")
    geff_path = tmp_path / "test_tracks.zarr"
    export_to_geff(tracks, geff_path)

    # Create import dialog and load the GEFF file
    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)

    # Load the geff file
    dialog.import_widget._load_geff(geff_path)

    # Verify geff root was loaded
    assert dialog.import_widget.root is not None, "Failed to load GEFF root"

    # Select "Use external segmentation" option and set path
    dialog.segmentation_widget.external_segmentation_radio.setChecked(True)
    seg_path = tmp_path / "segmentation.zarr"
    zarr.save_array(seg_path, segmentation)
    dialog.segmentation_widget.segmentation_widget.image_path_line.setText(
        str(seg_path)
    )
    dialog.segmentation_widget.segmentation_widget.seg_path_updated.emit()

    # Verify finish button is enabled
    assert dialog.finish_button.isEnabled() is True

    # Set seg_id mapping to "None" since node id == seg_id (automapping is incorrect)
    prop_map = dialog.prop_map_widget
    seg_combo = prop_map.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("None")
    prop_map._update_props_left()

    # Import the tracks
    dialog._finish()

    # Verify tracks were imported successfully
    assert hasattr(dialog, "tracks"), "Dialog should have tracks attribute after import"
    assert dialog.tracks is not None, "Tracks should not be None"
    assert dialog.tracks.graph.num_nodes() == graph.num_nodes()
    assert dialog.tracks.graph.num_edges() == graph.num_edges()
    assert dialog.tracks.ndim == ndim
    for node_id in dialog.tracks.graph.node_ids():
        dialog.tracks.get_time(node_id)

    # Area should be enabled and computed when segmentation is present
    assert "area" in dialog.tracks.features
    for node_id in dialog.tracks.graph.node_ids():
        assert dialog.tracks.graph.nodes[node_id]["area"] > 0


def test_geff_import_source_path_is_geff_group_not_container(
    qtbot, tmp_path, graph_2d, monkeypatch
):
    """source_path must name the geff group that was read, not the zarr
    container it was found inside.

    export_to_geff writes a container with the graph in a nested `tracks.geff`
    group. Listeners on TracksList.tracks_loaded use this path to find data
    stored alongside the tracks, so pointing at the container would be
    ambiguous when it holds more than one group.
    """
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    tracks = Tracks(graph_2d, ndim=3, time_attr="t", tracklet_attr="track_id")
    container = tmp_path / "container.zarr"
    export_to_geff(tracks, container)

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    dialog.import_widget._load_geff(container)
    assert dialog.import_widget.root is not None

    seg_combo = dialog.prop_map_widget.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("None")
    dialog.prop_map_widget._update_props_left()

    dialog._finish()

    assert dialog.tracks is not None
    assert dialog.source_path is not None
    # the geff group lives inside the container, not at its root
    assert dialog.source_path != container
    assert container in dialog.source_path.parents
    assert (dialog.source_path / ".zattrs").exists() or (
        dialog.source_path / "zarr.json"
    ).exists()


def test_geff_import_without_area_computes_area(
    qtbot, tmp_path, graph_2d_without_segmentation, segmentation_2d, monkeypatch
):
    """Test that area is computed on import when the GEFF has no area attribute.

    Exports a graph that has no area and no mask/bbox, then imports it with
    external segmentation. Area should be computed from the segmentation.
    """
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    graph_2d_without_segmentation.remove_node_attr_key("area")
    tracks = Tracks(graph_2d_without_segmentation, ndim=3, time_attr="t")
    geff_path = tmp_path / "test_no_area.zarr"
    export_to_geff(tracks, geff_path)

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    dialog.import_widget._load_geff(geff_path)
    assert dialog.import_widget.root is not None

    # Provide external segmentation
    dialog.segmentation_widget.external_segmentation_radio.setChecked(True)
    seg_path = tmp_path / "segmentation.tif"
    tifffile.imwrite(seg_path, segmentation_2d)
    dialog.segmentation_widget.segmentation_widget.image_path_line.setText(
        str(seg_path)
    )
    dialog.segmentation_widget.segmentation_widget.valid = True
    dialog.segmentation_widget.segmentation_widget.seg_path_updated.emit()

    assert dialog.finish_button.isEnabled()

    prop_map = dialog.prop_map_widget
    seg_combo = prop_map.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("None")
    prop_map._update_props_left()

    dialog._finish()

    assert dialog.tracks is not None
    assert dialog.tracks.graph.num_nodes() == graph_2d_without_segmentation.num_nodes()

    # Area must be in features and computed (positive values, not defaults)
    assert "area" in dialog.tracks.features
    for node_id in dialog.tracks.graph.node_ids():
        assert dialog.tracks.graph.nodes[node_id]["area"] > 0


def test_geff_import_without_segmentation(
    qtbot, tmp_path, solution_tracks_2d_without_segmentation, monkeypatch
):
    """Test importing without segmentation."""
    # Mock _resize_dialog to avoid screen access in headless CI
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    # Create tracks and export to GEFF (no segmentation)
    tracks = solution_tracks_2d_without_segmentation
    geff_path = tmp_path / "test_tracks_no_seg.zarr"
    export_to_geff(tracks, geff_path)

    # Create import dialog and load the GEFF file
    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)

    # Load the geff file
    dialog.import_widget._load_geff(geff_path)

    # Verify geff root was loaded
    assert dialog.import_widget.root is not None, "Failed to load GEFF root"

    # Select "None" for segmentation (should be default)
    assert dialog.segmentation_widget.none_radio.isChecked() is True

    # Verify finish button is enabled (segmentation is optional)
    assert dialog.finish_button.isEnabled() is True

    # Set seg_id mapping to "None" since node id == seg_id (automapping is incorrect)
    prop_map = dialog.prop_map_widget
    seg_combo = prop_map.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("None")
    prop_map._update_props_left()

    # Import the tracks
    dialog._finish()

    # Verify tracks were imported successfully
    assert hasattr(dialog, "tracks"), "Dialog should have tracks attribute after import"
    assert dialog.tracks is not None, "Tracks should not be None"
    assert dialog.tracks.graph.num_nodes() == tracks.graph.num_nodes()
    assert dialog.tracks.graph.num_edges() == tracks.graph.num_edges()
    for node_id in dialog.tracks.graph.node_ids():
        dialog.tracks.get_time(node_id)


def test_geff_import_without_axes_metadata(
    qtbot, tmp_path, graph_2d_without_segmentation, segmentation_2d, monkeypatch
):
    """Test importing a geff that has no axes metadata.
    This tests the automatic axes generation when metadata is missing.
    """
    # Mock _resize_dialog to avoid screen access in headless CI
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    # Create tracks and export to GEFF (this creates valid axes metadata)
    tracks = Tracks(
        graph_2d_without_segmentation, ndim=3, time_attr="t", tracklet_attr="track_id"
    )
    geff_path = tmp_path / "test_tracks_no_axes.zarr"
    export_to_geff(tracks, geff_path)

    # Remove axes metadata from the geff file
    root = zarr.open_group(geff_path / "tracks.geff", mode="r+")
    geff_metadata = dict(root.attrs.get("geff", {}))
    del geff_metadata["axes"]
    root.attrs["geff"] = geff_metadata

    # Create import dialog and load the GEFF file
    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)

    # Load the geff file
    dialog.import_widget._load_geff(geff_path)

    # Verify geff root was loaded
    assert dialog.import_widget.root is not None, "Failed to load GEFF root"

    # Verify axes metadata is missing
    loaded_metadata = dict(dialog.import_widget.root.attrs.get("geff", {}))
    assert "axes" not in loaded_metadata, "Axes should be missing from metadata"

    # Select "Use external segmentation" option and set path
    dialog.segmentation_widget.external_segmentation_radio.setChecked(True)
    seg_path = tmp_path / "segmentation.zarr"
    zarr.save_array(seg_path, segmentation_2d)
    dialog.segmentation_widget.segmentation_widget.image_path_line.setText(
        str(seg_path)
    )
    dialog.segmentation_widget.segmentation_widget.seg_path_updated.emit()

    # Verify finish button is enabled
    assert dialog.finish_button.isEnabled() is True

    # Set seg_id mapping to "None" since node id == seg_id (automapping is incorrect)
    prop_map = dialog.prop_map_widget
    seg_combo = prop_map.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("None")
    prop_map._update_props_left()

    # Import the tracks (this should auto-generate axes metadata)
    dialog._finish()

    # Verify tracks were imported successfully
    assert hasattr(dialog, "tracks"), "Dialog should have tracks attribute after import"
    assert dialog.tracks is not None, "Tracks should not be None"
    assert dialog.tracks.graph.num_nodes() == graph_2d_without_segmentation.num_nodes()
    assert dialog.tracks.graph.num_edges() == graph_2d_without_segmentation.num_edges()
    assert dialog.tracks.ndim == 3

    # Verify axes metadata was generated
    final_metadata = dict(dialog.import_widget.root.attrs.get("geff", {}))
    assert "axes" in final_metadata, "Axes should have been generated"
    assert len(final_metadata["axes"]) == 3, "Should have 3 axes for 2D+time"
    for node_id in dialog.tracks.graph.node_ids():
        dialog.tracks.get_time(node_id)


def test_geff_import_embedded_segmentation(qtbot, tmp_path, graph_2d, monkeypatch):
    """Test that embedded segmentation (mask/bbox + shape) is reconstructed.

    Regression test for the bug where mask/bbox were not included in the name_map
    passed to import_from_geff, causing tracks.segmentation to be None even though
    the GEFF contained embedded mask data and a recorded shape.
    """
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    tracks = Tracks(graph_2d, ndim=3, time_attr="t")
    geff_path = tmp_path / "test_embedded_seg.zarr"
    export_to_geff(tracks, geff_path, save_segmentation=False)

    # Verify that the geff has embedded segmentation (precondition)
    assert has_embedded_segmentation(geff_path / "tracks.geff"), (
        "Precondition: geff should have mask/bbox and shape"
    )

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    dialog.import_widget._load_geff(geff_path)

    assert dialog.import_widget.root is not None

    # Embedded segmentation detected: info label shown, radios hidden.
    # Use isHidden() because the dialog itself is not shown (parent is hidden),
    # so isVisible() would return False for all children regardless.
    assert not dialog.segmentation_widget._embedded_info_label.isHidden()
    assert dialog.segmentation_widget.external_segmentation_radio.isHidden()

    # mask/bbox should not appear as optional features (they are handled automatically)
    assert "mask" not in dialog.prop_map_widget.optional_features
    assert "bbox" not in dialog.prop_map_widget.optional_features

    # Even though include_seg() returns False (no external seg path), regionprops options
    # should be available for numeric features because embedded segmentation is present.
    assert dialog.prop_map_widget.seg_for_features is True
    assert dialog.prop_map_widget.seg is False  # scale widget / seg_id still hidden

    # Recompute must be disabled for embedded segmentation: funtracks does not register
    # a RegionPropsAnnotator when segmentation_path=None, so recompute would fail.
    for widgets in dialog.prop_map_widget.optional_features.values():
        assert not widgets["recompute"].isEnabled()

    assert dialog.finish_button.isEnabled()

    dialog._finish()

    assert dialog.tracks is not None
    assert dialog.tracks.segmentation is not None, (
        "Segmentation should be reconstructed from embedded mask/bbox data"
    )
    assert dialog.tracks.graph.num_nodes() == graph_2d.num_nodes()
    assert dialog.tracks.graph.num_edges() == graph_2d.num_edges()


def test_geff_import_old_geff_warning(qtbot, tmp_path, graph_2d, monkeypatch):
    """Test that the old GEFF warning is shown when mask/bbox is present but
    the shape is missing (simulating a GEFF from an external tool).
    """
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    tracks = Tracks(graph_2d, ndim=3, time_attr="t")
    geff_path = tmp_path / "old_geff.zarr"
    export_to_geff(tracks, geff_path, save_segmentation=False)

    # Remove the shape to simulate a GEFF without shape metadata
    root = zarr.open_group(geff_path / "tracks.geff", mode="r+")
    _remove_geff_shape(root)

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    dialog.import_widget._load_geff(geff_path)

    assert dialog.import_widget.root is not None

    # Old GEFF warning should be shown (mask/bbox present, no shape)
    assert not dialog.segmentation_widget._old_geff_warning_label.isHidden()
    assert dialog.segmentation_widget._embedded_info_label.isHidden()
    assert not dialog.segmentation_widget.none_radio.isHidden()
    assert not dialog.segmentation_widget.external_segmentation_radio.isHidden()

    # None radio is the default (no related_objects since save_segmentation=False)
    assert dialog.segmentation_widget.none_radio.isChecked()
    assert dialog.finish_button.isEnabled()

    dialog._finish()

    assert dialog.tracks is not None
    assert dialog.tracks.graph.num_nodes() == graph_2d.num_nodes()
    assert dialog.tracks.graph.num_edges() == graph_2d.num_edges()


def test_geff_import_with_related_data(qtbot, tmp_path, graph_2d, monkeypatch):
    """Test that related object radio buttons are shown for old GEFF with
    related_objects metadata, and that selecting one loads the segmentation.
    """
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    tracks = Tracks(graph_2d, ndim=3, time_attr="t")
    geff_path = tmp_path / "old_geff_with_related.zarr"
    # save_segmentation=True writes segmentation + adds related_objects to geff metadata.
    # seg_relabel=None preserves node IDs as pixel values (consistent with other tests).
    export_to_geff(tracks, geff_path, save_segmentation=True, seg_relabel=None)

    # Simulate an old GEFF that has related_objects but no embedded mask/bbox
    # or FeatureDict (these are features of newer funtracks exports).
    import shutil

    root = zarr.open_group(geff_path / "tracks.geff", mode="r+")

    geff_meta = dict(root.attrs["geff"])
    node_props_meta = dict(geff_meta["node_props_metadata"])
    for key in ("mask", "bbox"):
        node_props_meta.pop(key, None)
    geff_meta["node_props_metadata"] = node_props_meta
    extra = dict(geff_meta.get("extra", {}))
    extra.pop("funtracks", None)
    extra.pop("tracksdata", None)  # drop the recorded shape
    geff_meta["extra"] = extra
    root.attrs["geff"] = geff_meta

    for key in ("mask", "bbox"):
        prop_path = geff_path / "tracks.geff" / "nodes" / "props" / key
        if prop_path.exists():
            shutil.rmtree(prop_path)

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    dialog.import_widget._load_geff(geff_path)

    assert dialog.import_widget.root is not None

    # Old GEFF warning should NOT be shown (no mask/bbox columns)
    assert dialog.segmentation_widget._old_geff_warning_label.isHidden()
    # Related radio buttons populated from related_objects metadata
    assert len(dialog.segmentation_widget.related_object_radio_buttons) > 0

    # Related radio is auto-checked -> include_seg() is True
    assert dialog.segmentation_widget.include_seg() is True

    # Resolved path must exist on disk
    seg_path = dialog.segmentation_widget.get_segmentation_path()
    assert seg_path is not None
    assert seg_path.exists()

    assert dialog.finish_button.isEnabled()

    # seg_id is visible; map it to None (node id == seg id, funtracks handles it)
    prop_map = dialog.prop_map_widget
    seg_combo = prop_map.mapping_widgets["seg_id"]
    seg_combo.setCurrentText("None")
    prop_map._update_props_left()

    dialog._finish()

    assert dialog.tracks is not None
    assert dialog.tracks.segmentation is not None
    assert dialog.tracks.graph.num_nodes() == graph_2d.num_nodes()
    assert dialog.tracks.graph.num_edges() == graph_2d.num_edges()


def test_geff_import_no_mask_with_segmentation_shape(
    qtbot, tmp_path, graph_2d_without_segmentation, monkeypatch
):
    """Test that injecting a shape without mask/bbox shows the normal flow
    (no warning, no embedded info) and produces no segmentation on import.

    Uses the legacy top-level ``segmentation_shape`` zarr attribute, which also
    exercises the legacy shape-detection fallback.
    """
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    tracks = Tracks(graph_2d_without_segmentation, ndim=3, time_attr="t")
    geff_path = tmp_path / "no_mask_with_shape.zarr"
    export_to_geff(tracks, geff_path, save_segmentation=False)

    # Manually inject a (legacy) shape attr even though no mask/bbox exist
    root = zarr.open_group(geff_path / "tracks.geff", mode="r+")
    root.attrs["segmentation_shape"] = [5, 100, 100]

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    dialog.import_widget._load_geff(geff_path)

    assert dialog.import_widget.root is not None

    # Normal flow: no warning, no embedded info
    assert dialog.segmentation_widget._embedded_info_label.isHidden()
    assert dialog.segmentation_widget._old_geff_warning_label.isHidden()
    assert not dialog.segmentation_widget.none_radio.isHidden()
    assert not dialog.segmentation_widget.external_segmentation_radio.isHidden()

    # None radio is the default
    assert dialog.segmentation_widget.none_radio.isChecked()
    assert dialog.finish_button.isEnabled()

    dialog._finish()

    assert dialog.tracks is not None
    assert dialog.tracks.segmentation is None
    assert dialog.tracks.graph.num_nodes() == graph_2d_without_segmentation.num_nodes()
    assert dialog.tracks.graph.num_edges() == graph_2d_without_segmentation.num_edges()


def test_motile_run_save_load(tmp_path, graph_2d):
    """Test full MotileRun save/load round-trip."""
    run = MotileRun(
        graph=graph_2d,
        run_name="test_run",
        solver_params=SolverParams(),
        ndim=3,
        time_attr="t",
    )
    run_dir = run.save(tmp_path / "test_run.geff")

    # the run dir is itself the geff store, with the run's own files inside it
    assert (run_dir / "nodes").exists()
    assert (run_dir / "solver_params.json").exists()
    assert (run_dir / "attrs.json").exists()

    loaded = MotileRun.load(run_dir)
    assert loaded.run_name == run.run_name
    assert loaded.graph.num_nodes() == graph_2d.num_nodes()
    assert loaded.graph.num_edges() == graph_2d.num_edges()
    assert loaded.solver_params is not None


def test_motile_run_load_backward_compat(tmp_path, graph_2d):
    """Test that MotileRun.load falls back to 'tracks' when 'tracks.geff' is absent."""
    run = MotileRun(
        graph=graph_2d,
        run_name="old_run",
        solver_params=SolverParams(),
        ndim=3,
        time_attr="t",
    )
    saved = run.save(tmp_path / "old_run.geff")

    # Simulate the old save format: the graph in a 'tracks' subdirectory of a
    # run directory, rather than the run directory being the geff store itself
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    saved.rename(run_dir / "tracks")
    for name in ("solver_params.json", "attrs.json"):
        (run_dir / "tracks" / name).rename(run_dir / name)
    assert not (run_dir / "tracks.geff").exists()

    loaded = MotileRun.load(run_dir)
    assert loaded.run_name == "old_run"
    assert loaded.graph.num_nodes() == graph_2d.num_nodes()
    assert loaded.graph.num_edges() == graph_2d.num_edges()


# --- legacy (non-bool) mask conversion -------------------------------------


def _write_geff(tracks: Tracks, path: Path) -> Path:
    """Export tracks to a geff and return the inner geff group directory."""
    export_to_geff(tracks, path)
    return path / "tracks.geff"


@pytest.fixture
def legacy_mask_geff(tmp_path, graph_2d) -> Path:
    """A geff whose masks are stored as uint64, as older tracksdata wrote them."""
    from tracksdata.io import convert_geff_prop_dtype, geff_prop_dtype

    tracks = Tracks(graph_2d, ndim=3, time_attr="t", tracklet_attr="track_id")
    geff_dir = _write_geff(tracks, tmp_path / "legacy.zarr")
    convert_geff_prop_dtype(geff_dir, "mask", np.uint64)
    assert geff_prop_dtype(geff_dir, "mask") == np.dtype(np.uint64)
    return geff_dir


def _mask_dtype(geff_dir: Path) -> np.dtype:
    from tracksdata.io import geff_prop_dtype

    return geff_prop_dtype(geff_dir, "mask")


def test_legacy_masks_converted_in_place_on_yes(
    qtbot, legacy_mask_geff, mock_qmessagebox
):
    """Answering Yes rewrites the mask buffer to bool in place, without a copy."""
    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    mock_qmessagebox.question.return_value = mock_qmessagebox.Yes

    assert dialog._maybe_convert_legacy_masks(legacy_mask_geff) is True

    assert _mask_dtype(legacy_mask_geff) == np.dtype(bool)
    # No duplicate geff written next to the original
    siblings = [p.name for p in legacy_mask_geff.parent.glob("*.geff")]
    assert siblings == [legacy_mask_geff.name]


@pytest.mark.parametrize("answer_attr, expected", [("No", True), ("Cancel", False)])
def test_legacy_masks_not_converted_on_no_or_cancel(
    qtbot, legacy_mask_geff, mock_qmessagebox, answer_attr, expected
):
    """No imports the file as-is; Cancel aborts the import. Neither converts."""
    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    mock_qmessagebox.question.return_value = getattr(mock_qmessagebox, answer_attr)

    assert dialog._maybe_convert_legacy_masks(legacy_mask_geff) is expected
    assert _mask_dtype(legacy_mask_geff) == np.dtype(np.uint64)


def test_bool_masks_are_not_offered_for_conversion(
    qtbot, tmp_path, graph_2d, mock_qmessagebox
):
    """Masks already written as bool need no dialog and no conversion."""
    tracks = Tracks(graph_2d, ndim=3, time_attr="t", tracklet_attr="track_id")
    geff_dir = _write_geff(tracks, tmp_path / "current.zarr")
    assert _mask_dtype(geff_dir) == np.dtype(bool)

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)

    assert dialog._maybe_convert_legacy_masks(geff_dir) is True
    mock_qmessagebox.question.assert_not_called()


def test_missing_mask_prop_is_not_offered_for_conversion(
    qtbot, tmp_path, graph_2d_without_segmentation, mock_qmessagebox
):
    """A geff without a mask prop (points-only tracks) is imported unchanged."""
    tracks = Tracks(
        graph_2d_without_segmentation, ndim=3, time_attr="t", tracklet_attr="track_id"
    )
    geff_dir = _write_geff(tracks, tmp_path / "points_only.zarr")
    assert _mask_dtype(geff_dir) is None

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)

    assert dialog._maybe_convert_legacy_masks(geff_dir) is True
    mock_qmessagebox.question.assert_not_called()


def test_failed_conversion_aborts_import(
    qtbot, legacy_mask_geff, monkeypatch, mock_qmessagebox
):
    """A conversion error (e.g. a read-only store) is reported and aborts the import."""
    import tracksdata.io

    def boom(*args, **kwargs):
        raise RuntimeError("zarr store is read-only")

    monkeypatch.setattr(tracksdata.io, "convert_geff_prop_dtype", boom)
    mock_qmessagebox.critical.side_effect = None  # allow the error dialog
    mock_qmessagebox.question.return_value = mock_qmessagebox.Yes

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)

    assert dialog._maybe_convert_legacy_masks(legacy_mask_geff) is False
    assert mock_qmessagebox.critical.called
    assert _mask_dtype(legacy_mask_geff) == np.dtype(np.uint64)


def test_missing_tracksdata_helpers_do_not_block_import(
    qtbot, legacy_mask_geff, monkeypatch, mock_qmessagebox
):
    """Against a tracksdata without the helpers, the import proceeds untouched.

    Released tracksdata does not yet have them, so the dialog imports them
    defensively; this covers that fallback.
    """
    import tracksdata.io

    monkeypatch.delattr(tracksdata.io, "geff_prop_dtype", raising=False)
    monkeypatch.delattr(tracksdata.io, "convert_geff_prop_dtype", raising=False)

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)

    assert dialog._maybe_convert_legacy_masks(legacy_mask_geff) is True
    mock_qmessagebox.question.assert_not_called()


def test_legacy_mask_geff_imports_after_conversion(
    qtbot, legacy_mask_geff, monkeypatch, mock_qmessagebox
):
    """Full import path: a uint64-mask geff converts and still loads its segmentation."""
    monkeypatch.setattr(ImportDialog, "_resize_dialog", lambda self: None)

    dialog = ImportDialog(import_type="geff")
    qtbot.addWidget(dialog)
    dialog.import_widget._load_geff(legacy_mask_geff.parent)
    mock_qmessagebox.question.return_value = mock_qmessagebox.Yes

    dialog._finish()

    assert _mask_dtype(legacy_mask_geff) == np.dtype(bool)
    assert dialog.tracks is not None
    assert dialog.tracks.segmentation is not None
