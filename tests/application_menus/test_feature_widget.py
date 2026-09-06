from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from funtracks.annotators._regionprops_annotator import DEFAULT_POS_KEY

from motile_tracker.application_menus.feature_widget import (
    FeatureScaleWidget,
    FeatureWidget,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


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
    assert checkbox_names == expected_names


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


@pytest.fixture
def scale_widget(make_napari_viewer, solution_tracks_2d):
    """A ConfirmableScaleWidget on a viewer showing 2D tracks with an area feature."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")
    tracks_viewer.tracks.enable_features(["area"])
    # the dataframe behind the tree and table views is only kept up to date when one
    # of those views is present
    tracks_viewer.tree_widget_present = True
    tracks_viewer.update_track_df(initialization=False, refresh_view=True)

    # hold on to the combined widget: dropping it deletes its Qt children
    combined = FeatureScaleWidget(viewer)
    yield combined.scale_widget, tracks_viewer


def _areas(tracks) -> list[float]:
    return [tracks.get_node_attr(node, "area") for node in tracks.graph_full.node_ids()]


def test_scale_widget_prefills_from_tracks(scale_widget):
    widget, tracks_viewer = scale_widget

    # tracks without a scale are unscaled, and the widget says so rather than hiding
    assert tracks_viewer.tracks.scale is None
    assert widget.isVisibleTo(widget.parentWidget())
    assert widget.get_scale() == [1, 1.0, 1.0]
    assert not widget.z_spin_box.isVisibleTo(widget)


def test_confirm_scale_updates_tracks_layers_and_dataframe(scale_widget):
    widget, tracks_viewer = scale_widget
    tracks = tracks_viewer.tracks

    areas_before = _areas(tracks)
    df_before = tracks_viewer.track_df.copy()

    widget.y_spin_box.setValue(2.0)
    widget.x_spin_box.setValue(3.0)
    widget.confirm_scale_btn.click()

    assert tracks.scale == [1.0, 2.0, 3.0]

    # areas are in world units, so they follow the new voxel size
    for before, after in zip(areas_before, _areas(tracks), strict=True):
        assert after == pytest.approx(before * 6.0)

    # every napari layer is rescaled
    layers = tracks_viewer.tracking_layers
    for layer in (layers.points_layer, layers.tracks_layer, layers.seg_layer):
        assert layer is not None
        np.testing.assert_array_equal(layer.scale, [1.0, 2.0, 3.0])

    # and the dataframe behind the tree and table views shows world coordinates
    df_after = tracks_viewer.track_df
    np.testing.assert_allclose(df_after["y"], df_before["y"] * 2.0)
    np.testing.assert_allclose(df_after["x"], df_before["x"] * 3.0)
    np.testing.assert_allclose(df_after["Area"], df_before["Area"] * 6.0)

    # the spin boxes are rebuilt from the tracks, so they still agree
    assert widget.get_scale() == [1, 2.0, 3.0]


def test_confirm_scale_reports_failure_and_leaves_tracks_alone(
    scale_widget, monkeypatch
):
    """skimage cannot measure a perimeter under anisotropic spacing."""
    widget, tracks_viewer = scale_widget
    tracks = tracks_viewer.tracks
    tracks.enable_features(["perimeter"])

    warned = MagicMock()
    monkeypatch.setattr(
        "motile_tracker.application_menus.feature_widget.QMessageBox.warning", warned
    )

    widget.y_spin_box.setValue(2.0)
    widget.x_spin_box.setValue(3.0)
    widget.confirm_scale_btn.click()

    warned.assert_called_once()
    assert tracks.scale is None
    # the rejected values are replaced by the scale the tracks actually have
    assert widget.get_scale() == [1, 1.0, 1.0]
