from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import napari
import numpy as np
from tracksdata.constants import DEFAULT_ATTR_KEYS

if TYPE_CHECKING:
    from funtracks.data_model import SolutionTracks

    from motile_tracker.data_views.views_coordinator.tracks_viewer import (
        TracksViewer,
    )
import polars as pl


def update_napari_tracks(
    tracks: SolutionTracks,
):
    """Function to take a networkx graph with assigned track_ids and return the data
    needed to add to a napari tracks layer.

    Args:
        tracks (SolutionTracks): tracks that have track_ids and have a tree structure

    Returns:
        data: array (N, D+1)
            Coordinates for N points in D+1 dimensions. ID,T,(Z),Y,X. The first
            axis is the integer ID of the track. D is either 3 or 4 for planar
            or volumetric timeseries respectively.
        graph: dict {int: list}
            Graph representing associations between tracks. Dictionary defines the
            mapping between a track ID and the parents of the track. This can be
            one (the track has one parent, and the parent has >=1 child) in the
            case of track splitting, or more than one (the track has multiple
            parents, but only one child) in the case of track merging.
    """

    ndim = tracks.ndim - 1
    graph = tracks.graph
    napari_edges = {}

    time_key = tracks.features.time_key
    tracklet_key = tracks.features.tracklet_key
    position_key = tracks.features.position_key

    pos_keys = list(position_key) if isinstance(position_key, list) else [position_key]

    # One batch query instead of O(N) per-node queries
    if len(graph.node_ids()) > 0:
        df = graph.node_attrs(
            attr_keys=[DEFAULT_ATTR_KEYS.NODE_ID, time_key, tracklet_key] + pos_keys
        )
    else:
        df = pl.DataFrame(
            schema=[DEFAULT_ATTR_KEYS.NODE_ID, time_key, tracklet_key] + pos_keys
        )

    node_ids = df[DEFAULT_ATTR_KEYS.NODE_ID].to_list()
    track_ids_arr = df[tracklet_key].to_numpy()
    times_arr = df[time_key].to_numpy()

    if len(pos_keys) == 1:
        pos_col = df[pos_keys[0]]
        # Single position key may be a scalar column or a fixed-size array column
        positions_arr = pos_col.to_numpy()
        if positions_arr.ndim == 1:
            positions_arr = positions_arr[:, np.newaxis]
    else:
        positions_arr = np.stack([df[k].to_numpy() for k in pos_keys], axis=1)

    napari_data = np.zeros((len(node_ids), ndim + 2))
    napari_data[:, 0] = track_ids_arr
    napari_data[:, 1] = times_arr
    napari_data[:, 2:] = positions_arr

    # Build inter-track edges for divisions (parents with ≥2 children)
    node_to_track_id = dict(zip(node_ids, track_ids_arr.tolist(), strict=True))

    # Query only dividing nodes via GROUP BY HAVING COUNT==2, then fetch their
    # children with a single JOIN — avoids scanning every edge in the graph.
    dividing = graph.dividing_nodes()
    if dividing:
        children_per_parent: dict[int, list[int]] = graph.successors(dividing)
        for parent, children in children_per_parent.items():
            parent_track_id = node_to_track_id[parent]
            for child in children:
                napari_edges.setdefault(node_to_track_id[child], []).append(
                    parent_track_id
                )

    return napari_data, napari_edges


class TrackGraph(napari.layers.Tracks):
    """Extended tracks layer that holds the track information and emits and responds
    to dynamics visualization signals"""

    _type_string = "tracks"

    def __init__(
        self,
        name: str,
        tracks_viewer: TracksViewer,
    ):
        self.tracks_viewer = tracks_viewer
        track_data, track_edges = update_napari_tracks(
            self.tracks_viewer.tracks,
        )

        if len(track_data) == 0:
            # a single dummy row is needed for the empty layer, but its column count
            # must match the tracks dimensionality (id, t, [z], y, x).
            track_data = np.zeros((1, track_data.shape[1]), dtype=float)

        super().__init__(
            data=track_data,
            graph=track_edges,
            name=name,
            tail_length=3,
            color_by="track_id",
        )

        self.colormaps_dict["track_id"] = self.tracks_viewer.colormap
        self.tracks_layer_graph = copy.deepcopy(self.graph)  # for restoring graph later
        # just to 'refresh' the track_id colormap, we do not actually use turbo
        self.colormap = "turbo"

    def _refresh(self):
        """Refreshes the displayed tracks based on the graph in the current
        tracks_viewer.tracks
        """

        track_data, track_edges = update_napari_tracks(
            self.tracks_viewer.tracks,
        )

        if len(track_data) == 0:
            # napari's Tracks layer cannot handle empty data (it indexes the first
            # timepoint), so keep a single dummy row when the graph becomes empty
            # (e.g. after undoing the very first action). Same as in __init__.
            track_data = np.zeros((1, track_data.shape[1]), dtype=float)

        self.data = track_data
        self.graph = track_edges
        self.tracks_layer_graph = copy.deepcopy(self.graph)
        self.colormaps_dict["track_id"] = self.tracks_viewer.colormap
        # just to 'refresh' the track_id colormap, we do not actually use turbo
        self.colormap = "turbo"

    def update_track_visibility(self, visible: list[int] | str) -> None:
        """Optionally show only the tracks of a current lineage"""

        if visible == "all":
            self.track_colors[:, 3] = 1
            self.graph = self.tracks_layer_graph
        else:
            track_id_mask = np.isin(
                self.properties["track_id"],
                visible,
            )
            self.graph = {
                key: self.tracks_layer_graph[key]
                for key in visible
                if key in self.tracks_layer_graph
            }

            self.track_colors[:, 3] = 0
            self.track_colors[track_id_mask, 3] = 1
            # empty dicts to not trigger update (bug?) so disable the graph entirely as a
            # workaround
            if len(self.graph.items()) == 0:
                self.display_graph = False
            else:
                self.display_graph = True
