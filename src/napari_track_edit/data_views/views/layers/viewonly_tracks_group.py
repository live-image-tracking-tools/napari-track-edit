from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from napari_track_edit.data_views.views_coordinator.tracks_viewer import (
        TracksViewer,
    )

VIEWONLY_SUFFIX = " (view only)"


class ViewOnlyTracksGroup:
    """Read-only, fully colored napari layers for a Tracks object shown
    alongside the editable one.

    Owns a second, non-singleton TracksViewer (constructed directly, not via
    TracksViewer.get_instance) so that its TracksLayerGroup produces the same
    colored TrackLabels/TrackPoints/TrackGraph layers as the main editable
    tracks, without affecting the one TracksViewer the rest of the app
    (menus, tree view, table) treats as active. Keys are not bound: pressing
    e.g. "d" while a view-only layer is active would otherwise delete a node
    from this overlay's tracks, which has no visible table/tree feedback and
    is never what the user means by "view only".
    """

    def __init__(self, viewer, tracks, name: str):
        # Deferred import: tracks_viewer.py imports this module to type-hint
        # TracksViewer.viewonly_tracks, so importing it back at module level
        # would be circular.
        from napari_track_edit.data_views.views_coordinator.tracks_viewer import (
            TracksViewer,
        )

        self.viewer = viewer
        # Only used to host a colormap + TracksLayerGroup; never registered as
        # TracksViewer._instance, and update_tracks()/set_display_mode() etc. are
        # never called on it, since those touch viewer-wide state (text overlay,
        # visibility of every Labels/Points layer) that belongs to the real,
        # active TracksViewer.
        self.tracks_viewer: TracksViewer = TracksViewer(viewer, bind_keys=False)
        self.set_tracks(tracks, name)

    @property
    def tracks(self):
        return self.tracks_viewer.tracks

    @property
    def seg_layer(self):
        return self.tracks_viewer.tracking_layers.seg_layer

    @property
    def points_layer(self):
        return self.tracks_viewer.tracking_layers.points_layer

    @property
    def tracks_layer(self):
        return self.tracks_viewer.tracking_layers.tracks_layer

    def set_tracks(self, tracks, name: str) -> None:
        """Replace the tracks shown by this overlay, rebuilding its layers."""
        display_name = f"{name}{VIEWONLY_SUFFIX}"
        self.tracks_viewer.tracks = tracks
        self.tracks_viewer.colormap.set_tracks(None)
        if tracks is not None:
            self.tracks_viewer.set_color_feature(
                tracks.features.tracklet_key, refresh=False
            )
            self.tracks_viewer.colormap.set_tracks(tracks)
        self.tracks_viewer.tracking_layers.set_tracks(tracks, display_name)

    def remove_napari_layers(self) -> None:
        self.tracks_viewer.tracking_layers.remove_napari_layers()
