from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from funtracks.annotators._regionprops_annotator import (
    DEFAULT_INTENSITY_KEY,
    DEFAULT_POS_KEY,
)

from motile_tracker.application_menus.feature_widget import FeatureWidget
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

SEG_SHAPE_2D = (5, 100, 100)


def _frame_index_image() -> np.ndarray:
    """Image whose value is the time index, so any mask at time t has mean intensity t."""
    frames = np.arange(SEG_SHAPE_2D[0], dtype=np.float32).reshape(-1, 1, 1)
    return np.broadcast_to(frames, SEG_SHAPE_2D).copy()


@pytest.fixture
def intensity_widget(make_napari_viewer, solution_tracks_2d):
    """A FeatureWidget over 2D tracks with one matching image layer named "raw"."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")

    widget = FeatureWidget(viewer)
    viewer.add_image(_frame_index_image(), name="raw")
    widget._update_checkboxes()

    return widget, viewer, tracks_viewer.tracks


@pytest.fixture
def feature_widget_factory(make_napari_viewer, request):
    """
    Factory-style fixture to reduce repetitive setup across tests.
    Expects request.param = tracks fixture name.
    """
    viewer = make_napari_viewer()
    tracks = request.getfixturevalue(request.param)

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(tracks, name="test")

    widget = FeatureWidget(viewer)
    widget._update_checkboxes()

    return widget, tracks_viewer


@pytest.mark.parametrize(
    "feature_widget_factory, expected_names",
    [
        (
            "solution_tracks_2d",
            {"Area", "Circularity", "Perimeter", "Ellipse axis radii"},
        ),
        (
            "solution_tracks_3d",
            {"Volume", "Sphericity", "Surface Area", "Ellipsoid axis radii"},
        ),
    ],
    indirect=["feature_widget_factory"],
)
def test_feature_display_names(feature_widget_factory, expected_names):
    widget, _ = feature_widget_factory
    checkbox_names = {cb.text() for cb in widget._checkboxes.values()}
    # Subset check rather than equality: new regionprops features (e.g. intensity)
    # may be registered by funtracks without this test needing to track every one.
    assert expected_names <= checkbox_names


def test_3d_names_only(make_napari_viewer, solution_tracks_3d):
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_3d, name="test")

    widget = FeatureWidget(viewer)
    widget._update_checkboxes()

    names = {cb.text() for cb in widget._checkboxes.values()}

    assert {"Volume", "Ellipsoid axis radii", "Surface Area", "Sphericity"} <= names
    assert {"Area", "Ellipse axis radii", "Perimeter", "Circularity"} & names == set()


def test_checkbox_state_reflects_enabled_features(
    make_napari_viewer, solution_tracks_2d, solution_tracks_2d_without_segmentation
):
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")

    tracks = tracks_viewer.tracks
    tracks.enable_features(["area", "circularity"])

    widget = FeatureWidget(viewer)
    widget._update_checkboxes()

    assert widget._checkboxes["area"].isChecked()
    assert widget._checkboxes["circularity"].isChecked()
    assert not widget._checkboxes["perimeter"].isChecked()
    assert not widget._checkboxes["ellipse_axis_radii"].isChecked()

    # Also check a case where no features should be available because there is no segmentation
    tracks_viewer.update_tracks(
        solution_tracks_2d_without_segmentation, "test without features"
    )
    assert len(widget._checkboxes) == 0


def test_enable_feature_calls_tracks_methods(
    make_napari_viewer,
    solution_tracks_2d,
):
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")

    tracks = tracks_viewer.tracks

    enable_mock = MagicMock()
    disable_mock = MagicMock()
    update_df_mock = MagicMock()

    tracks.enable_features = enable_mock
    tracks.disable_features = disable_mock
    tracks_viewer.update_track_df = update_df_mock

    widget = FeatureWidget(viewer)
    widget._update_checkboxes()

    # DEFAULT_POS_KEY should never appear
    assert DEFAULT_POS_KEY not in widget._checkboxes

    checkbox = widget._checkboxes["circularity"]
    assert not checkbox.isChecked()

    checkbox.setChecked(True)

    enable_mock.assert_called_once_with(["circularity"])

    # now turn off and verify that the right mock is called
    enable_mock.reset_mock()
    disable_mock.reset_mock()
    update_df_mock.reset_mock()

    checkbox.setChecked(False)
    disable_mock.assert_called_once_with(["circularity"])
    enable_mock.assert_not_called()
    update_df_mock.assert_called_once_with(
        initialization=False,
        refresh_view=False,
    )


def test_only_matching_image_layers_are_listed(intensity_widget):
    """Only image layers shaped like the segmentation get an intensity checkbox."""
    widget, viewer, _ = intensity_widget

    viewer.add_image(np.zeros((5, 10, 10), dtype=np.float32), name="wrong_shape")
    viewer.add_labels(np.zeros(SEG_SHAPE_2D, dtype=np.uint16), name="not_an_image")
    widget._update_checkboxes()

    labels = {cb.text() for cb in widget._intensity_checkboxes.values()}
    assert labels == {"Mean intensity (raw)"}
    # intensity is never offered as a plain feature checkbox
    assert DEFAULT_INTENSITY_KEY not in widget._checkboxes


def test_toggling_layer_measures_intensity(intensity_widget):
    """Checking a layer measures it; unchecking removes the feature again."""
    widget, viewer, tracks = intensity_widget
    checkbox = widget._intensity_checkboxes[viewer.layers["raw"]]

    checkbox.setChecked(True)

    assert DEFAULT_INTENSITY_KEY in tracks.features
    for node_id in tracks.graph_solution.node_ids():
        assert tracks.get_node_attr(node_id, DEFAULT_INTENSITY_KEY) == pytest.approx(
            tracks.get_time(node_id)
        )

    checkbox.setChecked(False)

    assert DEFAULT_INTENSITY_KEY not in tracks.features
    assert tracks.regionprops_annotator.intensity_images is None


def test_two_layers_measured_as_channels(intensity_widget):
    """Two checked layers become two channels, one column each."""
    widget, viewer, tracks = intensity_widget
    viewer.add_image(_frame_index_image() * 10, name="second")
    widget._update_checkboxes()

    widget._intensity_checkboxes[viewer.layers["raw"]].setChecked(True)
    widget._intensity_checkboxes[viewer.layers["second"]].setChecked(True)

    feature = tracks.features[DEFAULT_INTENSITY_KEY]
    assert feature["num_values"] == 2
    assert list(feature["value_names"]) == [
        "Mean intensity (raw)",
        "Mean intensity (second)",
    ]
    for node_id in tracks.graph_solution.node_ids():
        time = tracks.get_time(node_id)
        value = list(tracks.get_node_attr(node_id, DEFAULT_INTENSITY_KEY))
        assert value == pytest.approx([time, 10 * time])


def test_checkboxes_follow_added_layer(intensity_widget):
    """A layer added after the widget was built gets its own checkbox."""
    widget, viewer, _ = intensity_widget

    viewer.add_image(_frame_index_image(), name="later")

    labels = {cb.text() for cb in widget._intensity_checkboxes.values()}
    assert labels == {"Mean intensity (raw)", "Mean intensity (later)"}


def test_removing_measured_layer_stops_measuring_it(intensity_widget):
    """Removing a measured layer drops it as a channel."""
    widget, viewer, tracks = intensity_widget
    viewer.add_image(_frame_index_image() * 10, name="second")
    widget._update_checkboxes()
    widget._intensity_checkboxes[viewer.layers["raw"]].setChecked(True)
    widget._intensity_checkboxes[viewer.layers["second"]].setChecked(True)

    viewer.layers.remove(viewer.layers["second"])

    assert [layer.name for layer in widget._intensity_layers] == ["raw"]
    assert tracks.features[DEFAULT_INTENSITY_KEY]["num_values"] == 1
    labels = {cb.text() for cb in widget._intensity_checkboxes.values()}
    assert labels == {"Mean intensity (raw)"}

    # Removing the last measured layer disables the feature entirely
    viewer.layers.remove(viewer.layers["raw"])
    assert DEFAULT_INTENSITY_KEY not in tracks.features


def test_rename_updates_checkbox_and_feature(intensity_widget):
    """Renaming a measured layer renames its checkbox and its feature column."""
    widget, viewer, tracks = intensity_widget
    widget._intensity_checkboxes[viewer.layers["raw"]].setChecked(True)

    viewer.layers["raw"].name = "renamed"

    labels = {cb.text() for cb in widget._intensity_checkboxes.values()}
    assert labels == {"Mean intensity (renamed)"}
    assert (
        tracks.features[DEFAULT_INTENSITY_KEY]["display_name"]
        == "Mean intensity (renamed)"
    )
    # the checkbox for the renamed layer is still checked
    assert widget._intensity_checkboxes[viewer.layers["renamed"]].isChecked()


def test_intensity_selection_resets_for_new_tracks(
    make_napari_viewer, solution_tracks_2d, solution_tracks_2d_without_segmentation
):
    """Loading different tracks clears the measured layers."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")

    widget = FeatureWidget(viewer)
    viewer.add_image(_frame_index_image(), name="raw")
    widget._update_checkboxes()
    widget._intensity_checkboxes[viewer.layers["raw"]].setChecked(True)
    assert widget._intensity_layers

    tracks_viewer.update_tracks(solution_tracks_2d_without_segmentation, name="other")

    assert widget._intensity_layers == []
    assert widget._intensity_checkboxes == {}


def test_update_checkboxes_recreates_widgets(
    make_napari_viewer,
    solution_tracks_2d,
):
    viewer = make_napari_viewer()
    widget = FeatureWidget(viewer)

    # Should not raise
    widget._update_checkboxes()
    assert widget._checkboxes == {}

    # Add tracks
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")

    widget._update_checkboxes()
    first_count = len(widget._checkboxes)

    widget._update_checkboxes()
    second_count = len(widget._checkboxes)

    assert first_count == second_count

    # layout should not accumulate duplicates (checkboxes + single stretch)
    widget_items = [
        widget.checkbox_layout.itemAt(i).widget()
        for i in range(widget.checkbox_layout.count())
        if widget.checkbox_layout.itemAt(i).widget() is not None
    ]

    assert len(widget_items) == first_count
