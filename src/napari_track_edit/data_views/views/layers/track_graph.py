from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import TYPE_CHECKING

import napari
import numpy as np
from tracksdata.constants import DEFAULT_ATTR_KEYS

if TYPE_CHECKING:
    from funtracks.data_model import Tracks

    from napari_track_edit.data_views.views_coordinator.tracks_viewer import (
        TracksViewer,
    )
import polars as pl


def update_napari_tracks(
    tracks: Tracks,
):
    """Function to take a networkx graph with assigned track_ids and return the data
    needed to add to a napari tracks layer.

    Args:
        tracks (Tracks): tracks that have track_ids and have a tree structure

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
        node_ids: list[int]
            The node id of each row of `data`, in the same order, so the layer
            can be colored per node.
    """

    ndim = tracks.ndim - 1
    graph = tracks.graph_solution
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

    return napari_data, napari_edges, node_ids


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
        track_data, track_edges, node_ids = update_napari_tracks(
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

        self.full_division_edges = copy.deepcopy(
            self.graph
        )  # for restoring division edges later
        self.visible_tracks: object = "all"
        self._apply_node_colors(node_ids)

    def _refresh(self):
        """Refreshes the displayed tracks based on the graph in the current
        tracks_viewer.tracks
        """

        track_data, track_edges, node_ids = update_napari_tracks(
            self.tracks_viewer.tracks,
        )

        if len(track_data) == 0:
            # napari's Tracks layer cannot handle empty data (it indexes the first
            # timepoint), so keep a single dummy row when the graph becomes empty
            # (e.g. after undoing the very first action). Same as in __init__.
            track_data = np.zeros((1, track_data.shape[1]), dtype=float)

        self.data = track_data
        self.graph = track_edges
        self.full_division_edges = copy.deepcopy(self.graph)
        # _apply_node_colors recomputes track_colors with full alpha, so every
        # track is visible again: reset the cached visible set to match.
        self.visible_tracks = "all"
        self._apply_node_colors(node_ids)

    def _apply_node_colors(self, node_ids: list[int]) -> None:
        """Color the track lines per node instead of per track id.

        napari colors a Tracks layer by mapping one vertex property array
        through a colormap. We need to color by node id instead of tracklet_id to ensure
         that this colormap follows the other views.

        `node_ids` must be in the same row order as the data that was just
        assigned: napari sorts the vertices by (track id, time) and reorders
        the properties to match, using the order it recorded for that data.
        """

        if len(node_ids) == len(self.data):
            node_id_property = np.asarray(node_ids, dtype=np.int64)
        else:
            # single dummy row for empty graph (black)
            node_id_property = np.zeros(len(self.data), dtype=np.int64)

        # Setting properties re-adds track_id itself (update_track_visibility
        # needs it), taken from the already-sorted data.
        self.properties = {"node_id": node_id_property}
        self.colormaps_dict["node_id"] = SimpleNamespace(
            map=self.tracks_viewer.colormap.get_colors
        )
        # always call, even if already on node_id, to trigger refresh
        self.color_by = "node_id"

    def _set_division_edges(self, division_edges: dict[int, list[int]]) -> None:
        """Hand the graph to napari.

        The `Tracks.graph` setter revalidates every entry and then rebuilds every
        graph vertex, looking each track id up against all points: 2.0 s for
        34k entries over 325k points. Only called by `update_track_visibility` once
        it has confirmed the visible set actually changed, so that cost is paid
        only when it must be.
        """
        self.graph = division_edges

        # empty dicts do not trigger update (bug?) so disable the div edges entirely as a
        # workaround. Assigned only on a change: the setter emits unconditionally.
        display_div_edges = len(self.graph) > 0
        if self.display_graph != display_div_edges:
            self.display_graph = display_div_edges

    def _set_track_alpha(self, visible: list[int] | str) -> None:
        """Set track opacity so that only `visible` tracks are drawn."""
        colors = self.track_colors
        if visible == "all":
            colors[:, 3] = 1
        else:
            track_id_mask = np.isin(self.properties["track_id"], visible)
            colors[:, 3] = 0
            colors[track_id_mask, 3] = 1
        # The writes above mutate the array in place, which bypasses the
        # track_colors setter and so never emits `color_by` - the event that
        # makes the vispy layer re-upload the colour buffer. Until this
        # assignment the new alphas only existed on our side: `rebuild_graph`,
        # which used to be emitted here by the graph assignment, re-uploads the
        # *graph* subvisual only, and in a hard-coded white.
        self.track_colors = colors

    def update_track_visibility(self, visible: list[int] | str) -> None:
        """Optionally show only the tracks of a current lineage.

        Do nothing if the set is already visible, to avoid unnecessary computation.
        """
        key = "all" if visible == "all" else frozenset(visible)

        # The cached key stays trustworthy because the only two things that could
        # invalidate it - a new `full_division_edges` or new `data` - are written
        # only in __init__ and _refresh, and both of those reset the key too. So
        # there is no path where the underlying data changes without the key
        # changing alongside it.
        if key == self.visible_tracks:
            return
        self.visible_tracks = key

        self._set_track_alpha(visible)

        if visible == "all":
            self._set_division_edges(self.full_division_edges)
        else:
            self._set_division_edges(
                {
                    track_id: self.full_division_edges[track_id]
                    for track_id in visible
                    if track_id in self.full_division_edges
                }
            )
