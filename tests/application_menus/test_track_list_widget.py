"""Tests for TrackListWidget (the application menu wrapper)."""

from motile_tracker.application_menus.track_list_widget import TrackListWidget
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class TestTrackListWidget:
    def test_init_contains_tracks_list(self, make_napari_viewer):
        viewer = make_napari_viewer()
        widget = TrackListWidget(viewer)
        tracks_viewer = TracksViewer.get_instance(viewer)
        assert widget.layout().itemAt(1).widget() is tracks_viewer.tracks_list
