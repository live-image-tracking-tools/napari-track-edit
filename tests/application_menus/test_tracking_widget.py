"""Tests for TrackingWidget - the tab widget holding the two ways of making tracks."""

import numpy as np
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph
from qtpy.QtWidgets import QGroupBox

from motile_tracker.application_menus.tracking_from_scratch_widget import (
    TrackingFromScratch,
)
from motile_tracker.application_menus.tracking_widget import TrackingWidget
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.motile.backend import MotileRun, SolverParams
from motile_tracker.motile.menus.motile_widget import MotileWidget


def test_tabs(make_napari_viewer):
    """Both tracking menus are tabs of this widget, motile first."""

    viewer = make_napari_viewer()
    widget = TrackingWidget(viewer)

    assert widget.count() == 2
    assert widget.widget(0) is widget.motile_widget
    assert widget.widget(1) is widget.tracking_from_scratch
    assert isinstance(widget.motile_widget, MotileWidget)
    assert isinstance(widget.tracking_from_scratch, TrackingFromScratch)
    assert widget.tabText(0) == "Track with Motile"
    assert widget.tabText(1) == "Track from Scratch"
    # the motile run editor is what the user sees when the menu opens
    assert widget.currentIndex() == 0


def test_from_scratch_tab_does_not_stretch(make_napari_viewer, qtbot):
    """The from-scratch controls stay at their natural height instead of being
    stretched over the whole tab, which is what a QVBoxLayout without a trailing
    stretch does to its only widget."""

    viewer = make_napari_viewer()
    widget = TrackingWidget(viewer)
    qtbot.addWidget(widget)
    widget.setCurrentIndex(1)
    widget.resize(300, 900)
    widget.show()
    qtbot.waitExposed(widget)

    box = widget.tracking_from_scratch.findChild(QGroupBox)
    assert box is not None
    # a couple of pixels of slack for layout spacing/margins
    assert box.height() <= box.sizeHint().height() + 2
    assert box.height() < widget.tracking_from_scratch.height() / 2


def test_motile_settings_stay_visible_for_manual_tracks(make_napari_viewer, qtbot):
    """Selecting manual tracks after a motile run must bring the run editor back:
    there is no run to view, but the solver settings still have to be reachable."""

    viewer = make_napari_viewer()
    viewer.add_image(np.zeros((5, 10, 10), dtype=np.uint16), name="img")
    widget = TrackingWidget(viewer)
    qtbot.addWidget(widget)
    widget.show()
    motile_widget = widget.motile_widget

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.tracks_list.add_tracks(
        MotileRun(
            graph=create_empty_graphview_graph(),
            run_name="run",
            solver_params=SolverParams(),
            ndim=3,
        ),
        "run",
    )
    assert motile_widget.view_run_widget.isVisible()
    assert not motile_widget.edit_run_widget.isVisible()

    widget.tracking_from_scratch.size_layer_dropdown.setCurrentText("img")
    widget.tracking_from_scratch._start_tracking("points")

    assert not motile_widget.view_run_widget.isVisible()
    assert motile_widget.edit_run_widget.isVisible()
