from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from funtracks.annotators._regionprops_annotator import (
    DEFAULT_INTENSITY_KEY,
    DEFAULT_POS_KEY,
)
from qtpy.QtWidgets import QDialog, QMessageBox

from motile_tracker.application_menus.feature_widget import (
    FeatureWidget,
    IntensityLayerDialog,
)
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

SEG_SHAPE_2D = (5, 100, 100)


def _frame_index_image() -> np.ndarray:
    """Image whose value is the time index, so any mask at time t has mean intensity t."""
    frames = np.arange(SEG_SHAPE_2D[0], dtype=np.float32).reshape(-1, 1, 1)
    return np.broadcast_to(frames, SEG_SHAPE_2D).copy()


def _answer_dialog(monkeypatch, choose=None, accept: bool = True) -> list:
    """Answer the layer dialog without showing it.

    Args:
        choose: called with the dialog before it is answered, to tick its boxes.
        accept: whether the user presses OK (True) or Cancel (False).

    Returns:
        A list that grows by one dialog every time one is opened.
    """
    opened: list[IntensityLayerDialog] = []

    def fake_exec(dialog):
        opened.append(dialog)
        if choose is not None:
            choose(dialog)
        return QDialog.Accepted if accept else QDialog.Rejected

    monkeypatch.setattr(IntensityLayerDialog, "exec_", fake_exec)
    return opened


def _tick_only(*names: str):
    """A `choose` for _answer_dialog that ticks exactly the named layers."""

    def choose(dialog):
        for layer, checkbox in dialog._checkboxes:
            checkbox.setChecked(layer.name in names)

    return choose


@pytest.fixture
def intensity_widget(make_napari_viewer, solution_tracks_2d):
    """A FeatureWidget over 2D tracks with two matching image layers.

    "raw" reads t at time t, "second" reads 10 * t, so the two channels are telling
    apart in the measured values.
    """
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")

    widget = FeatureWidget(viewer)
    viewer.add_image(_frame_index_image(), name="raw")
    viewer.add_image(_frame_index_image() * 10, name="second")
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


def test_single_intensity_checkbox(intensity_widget):
    """One checkbox for the feature, not one per layer."""
    widget, _, _ = intensity_widget

    assert widget.intensity_checkbox is not None
    assert widget.intensity_checkbox.text() == "Mean intensity"
    assert not widget.intensity_checkbox.isChecked()
    # intensity is never offered as a plain feature checkbox
    assert DEFAULT_INTENSITY_KEY not in widget._checkboxes


def test_dialog_lists_only_matching_image_layers(intensity_widget, monkeypatch):
    """The picker offers image layers shaped like the segmentation, and no others."""
    widget, viewer, _ = intensity_widget
    viewer.add_image(np.zeros((5, 10, 10), dtype=np.float32), name="wrong_shape")
    viewer.add_labels(np.zeros(SEG_SHAPE_2D, dtype=np.uint16), name="not_an_image")

    opened = _answer_dialog(monkeypatch)
    widget.intensity_checkbox.setChecked(True)

    assert len(opened) == 1
    assert [layer.name for layer, _ in opened[0]._checkboxes] == ["raw", "second"]


def test_toggling_on_measures_all_layers_by_default(intensity_widget, monkeypatch):
    """Switching on asks once, and every eligible layer starts ticked."""
    widget, _, tracks = intensity_widget
    opened = _answer_dialog(monkeypatch)

    widget.intensity_checkbox.setChecked(True)

    assert len(opened) == 1
    assert all(checkbox.isChecked() for _, checkbox in opened[0]._checkboxes)

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


def test_toggling_on_measures_only_the_chosen_layers(intensity_widget, monkeypatch):
    """Unticking a layer in the picker leaves it unmeasured."""
    widget, _, tracks = intensity_widget
    _answer_dialog(monkeypatch, choose=_tick_only("second"))

    widget.intensity_checkbox.setChecked(True)

    feature = tracks.features[DEFAULT_INTENSITY_KEY]
    assert feature["num_values"] == 1
    assert feature["display_name"] == "Mean intensity (second)"
    for node_id in tracks.graph_solution.node_ids():
        assert tracks.get_node_attr(node_id, DEFAULT_INTENSITY_KEY) == pytest.approx(
            10 * tracks.get_time(node_id)
        )


def test_toggling_off_and_on_reuses_the_choice(intensity_widget, monkeypatch):
    """The picker only appears the first time; after that the choice is remembered."""
    widget, _, tracks = intensity_widget
    opened = _answer_dialog(monkeypatch, choose=_tick_only("raw"))

    widget.intensity_checkbox.setChecked(True)
    assert DEFAULT_INTENSITY_KEY in tracks.features

    widget.intensity_checkbox.setChecked(False)
    assert DEFAULT_INTENSITY_KEY not in tracks.features

    widget.intensity_checkbox.setChecked(True)
    assert len(opened) == 1  # not asked again
    assert tracks.features[DEFAULT_INTENSITY_KEY]["display_name"] == (
        "Mean intensity (raw)"
    )


def test_cancelling_leaves_the_feature_off(intensity_widget, monkeypatch):
    """Cancelling the picker unticks the checkbox again."""
    widget, _, tracks = intensity_widget
    _answer_dialog(monkeypatch, accept=False)

    widget.intensity_checkbox.setChecked(True)

    assert not widget.intensity_checkbox.isChecked()
    assert DEFAULT_INTENSITY_KEY not in tracks.features


def test_update_button_changes_measured_layers(intensity_widget, monkeypatch):
    """The refresh button reopens the picker and applies the new choice."""
    widget, _, tracks = intensity_widget
    _answer_dialog(monkeypatch)
    widget.intensity_checkbox.setChecked(True)
    assert tracks.features[DEFAULT_INTENSITY_KEY]["num_values"] == 2

    _answer_dialog(monkeypatch, choose=_tick_only("second"))
    widget.intensity_update_btn.click()

    feature = tracks.features[DEFAULT_INTENSITY_KEY]
    assert feature["num_values"] == 1
    assert feature["display_name"] == "Mean intensity (second)"
    assert widget.intensity_checkbox.isChecked()


def test_update_button_with_nothing_ticked_turns_intensity_off(
    intensity_widget, monkeypatch
):
    """Unticking everything in the picker is how you stop measuring from there."""
    widget, _, tracks = intensity_widget
    _answer_dialog(monkeypatch)
    widget.intensity_checkbox.setChecked(True)

    _answer_dialog(monkeypatch, choose=_tick_only())
    widget.intensity_update_btn.click()

    assert DEFAULT_INTENSITY_KEY not in tracks.features
    assert not widget.intensity_checkbox.isChecked()


def test_cancelling_the_update_leaves_the_measurement_alone(
    intensity_widget, monkeypatch
):
    widget, _, tracks = intensity_widget
    _answer_dialog(monkeypatch)
    widget.intensity_checkbox.setChecked(True)

    _answer_dialog(monkeypatch, choose=_tick_only("raw"), accept=False)
    widget.intensity_update_btn.click()

    assert tracks.features[DEFAULT_INTENSITY_KEY]["num_values"] == 2
    assert widget.intensity_checkbox.isChecked()


def test_removing_measured_layer_drops_its_measurement(intensity_widget, monkeypatch):
    """A layer that is gone cannot be measured, so its column goes with it."""
    widget, viewer, tracks = intensity_widget
    _answer_dialog(monkeypatch)
    widget.intensity_checkbox.setChecked(True)

    viewer.layers.remove(viewer.layers["second"])

    assert [layer.name for layer in widget._intensity_layers] == ["raw"]
    feature = tracks.features[DEFAULT_INTENSITY_KEY]
    assert feature["num_values"] == 1
    assert feature["display_name"] == "Mean intensity (raw)"
    for node_id in tracks.graph_solution.node_ids():
        assert tracks.get_node_attr(node_id, DEFAULT_INTENSITY_KEY) == pytest.approx(
            tracks.get_time(node_id)
        )

    # removing the last measured layer switches the feature off
    viewer.layers.remove(viewer.layers["raw"])
    assert DEFAULT_INTENSITY_KEY not in tracks.features
    assert not widget.intensity_checkbox.isChecked()


def test_removing_a_layer_while_off_does_not_switch_it_back_on(
    intensity_widget, monkeypatch
):
    widget, viewer, tracks = intensity_widget
    _answer_dialog(monkeypatch)
    widget.intensity_checkbox.setChecked(True)
    widget.intensity_checkbox.setChecked(False)

    viewer.layers.remove(viewer.layers["second"])

    assert DEFAULT_INTENSITY_KEY not in tracks.features
    assert not widget.intensity_checkbox.isChecked()
    assert [layer.name for layer in widget._intensity_layers] == ["raw"]


def test_renaming_measured_layer_renames_its_column(intensity_widget, monkeypatch):
    """The layer name is the column name, so the tree view follows a rename."""
    widget, viewer, tracks = intensity_widget
    _answer_dialog(monkeypatch, choose=_tick_only("raw"))
    widget.intensity_checkbox.setChecked(True)

    viewer.layers["raw"].name = "renamed"

    assert tracks.features[DEFAULT_INTENSITY_KEY]["display_name"] == (
        "Mean intensity (renamed)"
    )
    # still the same layer, still measured
    assert [layer.name for layer in widget._intensity_layers] == ["renamed"]
    assert widget.intensity_checkbox.isChecked()


def test_no_eligible_image_layers(make_napari_viewer, solution_tracks_2d, monkeypatch):
    """Switching on with nothing to measure explains itself and stays off."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")
    widget = FeatureWidget(viewer)
    widget._update_checkboxes()

    shown = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: shown.append(args)
    )

    widget.intensity_checkbox.setChecked(True)

    assert len(shown) == 1
    assert not widget.intensity_checkbox.isChecked()
    assert DEFAULT_INTENSITY_KEY not in tracks_viewer.tracks.features


def test_intensity_selection_resets_for_new_tracks(
    make_napari_viewer,
    solution_tracks_2d,
    solution_tracks_2d_without_segmentation,
    monkeypatch,
):
    """Loading different tracks clears the measured layers."""
    viewer = make_napari_viewer()
    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.update_tracks(solution_tracks_2d, name="test")

    widget = FeatureWidget(viewer)
    viewer.add_image(_frame_index_image(), name="raw")
    widget._update_checkboxes()
    _answer_dialog(monkeypatch)
    widget.intensity_checkbox.setChecked(True)
    assert widget._intensity_layers

    tracks_viewer.update_tracks(solution_tracks_2d_without_segmentation, name="other")

    assert widget._intensity_layers == []
    assert widget.intensity_checkbox is None


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

    # the feature checkboxes, plus the row holding the intensity checkbox
    assert len(widget_items) == first_count + 1
