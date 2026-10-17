from __future__ import annotations

import numpy as np
from napari.layers import Labels, Points, Tracks as NapariTracksLayer

VIEWONLY_SUFFIX = " (view only)"
VIEWONLY_POINTS_COLOR = "cyan"


class ViewOnlyTracksGroup:
    """Plain, read-only napari layers for a Tracks object shown alongside the
    editable one.

    Unlike TracksLayerGroup, this does not use TrackLabels/TrackPoints/TrackGraph:
    there is no click handling, no editing, and no per-node colormap management
    needed, so plain napari.layers.Labels/Points/Tracks are enough. Each layer is
    rebuilt (not updated) when set_tracks() is called again, which is fine for
    view-only overlays that do not change often.
    """

    def __init__(self, viewer, tracks, name: str):
        self.viewer = viewer
        self.tracks = None
        self.name = ""
        self.seg_layer: Labels | None = None
        self.points_layer: Points | None = None
        self.tracks_layer: NapariTracksLayer | None = None
        self.set_tracks(tracks, name)

    def set_tracks(self, tracks, name: str) -> None:
        """Replace the tracks shown by this overlay, rebuilding its layers."""
        self.remove_napari_layers()
        self.tracks = tracks
        self.name = name
        display_name = f"{name}{VIEWONLY_SUFFIX}"

        if tracks is None:
            self.seg_layer = None
            self.points_layer = None
            self.tracks_layer = None
            return

        if tracks.segmentation is not None:
            self.seg_layer = Labels(
                np.asarray(tracks.segmentation),
                name=display_name + "_seg",
                opacity=0.9,
                scale=tracks.scale,
            )
        else:
            self.seg_layer = None

        if tracks.graph_solution is not None and len(tracks.nodes()) > 0:
            nodes = tracks.nodes()
            positions = tracks.get_positions(nodes, incl_time=True)
            self.points_layer = Points(
                data=positions,
                name=display_name + "_points",
                face_color=VIEWONLY_POINTS_COLOR,
                border_color=VIEWONLY_POINTS_COLOR,
                size=5,
                scale=[1.0, *tracks.scale[1:]] if tracks.scale else None,
            )
            self.tracks_layer = self._build_tracks_layer(tracks, nodes, display_name)
        else:
            self.points_layer = None
            self.tracks_layer = None

        self.add_napari_layers()

    @staticmethod
    def _build_tracks_layer(tracks, nodes, display_name: str) -> NapariTracksLayer | None:
        """Build a plain napari Tracks layer (lineage lines), skipped if the
        track/parent id bookkeeping needed to build it is not available."""
        try:
            track_ids = [int(tracks.get_track_id(node)) for node in nodes]
            positions = tracks.get_positions(nodes, incl_time=True)
            data = np.column_stack([track_ids, positions])
        except Exception:  # noqa: BLE001 - lineage lines are a nice-to-have overlay
            return None
        return NapariTracksLayer(
            data=data,
            name=display_name + "_tracks",
            colormap="gray",
            tail_width=2,
        )

    def remove_napari_layer(self, layer) -> None:
        if layer is not None and layer in self.viewer.layers:
            self.viewer.layers.remove(layer)

    def remove_napari_layers(self) -> None:
        self.remove_napari_layer(self.seg_layer)
        self.remove_napari_layer(self.points_layer)
        self.remove_napari_layer(self.tracks_layer)

    def add_napari_layers(self) -> None:
        if self.tracks_layer is not None:
            self.viewer.add_layer(self.tracks_layer)
        if self.points_layer is not None:
            self.viewer.add_layer(self.points_layer)
        if self.seg_layer is not None:
            self.viewer.add_layer(self.seg_layer)
