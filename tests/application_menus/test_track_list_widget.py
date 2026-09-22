"""Tests for TrackListWidget (the application menu wrapper)."""

from motile_tracker.application_menus.track_list_widget import TrackListWidget
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TestTrackListWidget:
    def test_init_contains_tracks_list(self, make_napari_viewer):
        viewer = make_napari_viewer()
        widget = TrackListWidget(viewer)
        tracks_viewer = TracksViewer.get_instance(viewer)
        # the tracks list is the only thing in this menu: the from-scratch controls
        # moved to the Tracking menu.
        assert widget.layout().count() == 1
        assert widget.layout().itemAt(0).widget() is tracks_viewer.tracks_list
