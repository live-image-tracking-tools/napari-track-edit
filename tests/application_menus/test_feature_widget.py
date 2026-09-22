from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from funtracks.annotators._regionprops_annotator import DEFAULT_POS_KEY

from motile_tracker.application_menus.feature_widget import FeatureWidget
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
