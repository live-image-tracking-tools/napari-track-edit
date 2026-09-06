from __future__ import annotations

from typing import Any

import napari.layers
import numpy as np
import pandas as pd
import tracksdata as td
from funtracks.data_model import Tracks
from tracksdata.constants import DEFAULT_ATTR_KEYS

from motile_tracker.data_views.node_type import NodeType


def get_tracklets(
    parent_to_children: dict[int, list[int]],
    child_to_parent: dict[int, int],
    node_ids: list[int],
    dividing_node_set: set[int],
    node_to_track_id: dict[int, int],
) -> list[set[int]]:
    """Group nodes into tracklets by BFS, cutting at division nodes.

    A tracklet is a maximal linear segment of the track graph — it does not
    cross a division point. The returned sets contain node IDs; callers are
    responsible for sorting by time if needed.

    Args:
        parent_to_children: maps each parent node_id to its list of child node_ids.
        child_to_parent: maps each child node_id to its single parent node_id.
        node_ids: all node IDs to partition.
        dividing_node_set: set of node IDs that have ≥2 children (division nodes).
        node_to_track_id: maps each node_id to its pre-computed tracklet ID.

    Returns:
        List of sets, one set of node IDs per tracklet.
    """
    visited: set[int] = set()
    tracklets: list[set[int]] = []
    for start_node in node_ids:
        if start_node in visited:
            continue
        component: set[int] = set()
        queue = [start_node]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            pred = child_to_parent.get(node)
            if (
                pred is not None
                and pred not in visited
                and pred not in dividing_node_set
                and node_to_track_id.get(pred) == node_to_track_id.get(node)
            ):
                queue.append(pred)
            if node not in dividing_node_set:
                for succ in parent_to_children.get(node, []):
                    if succ not in visited and node_to_track_id.get(
                        succ
                    ) == node_to_track_id.get(node):
                        queue.append(succ)
        tracklets.append(component)
    return tracklets


def extract_sorted_tracks(
    tracks: Tracks,
    colormap: napari.utils.CyclicLabelColormap,
    prev_axis_order: list[int] | None = None,
) -> pd.DataFrame | None:
    """
    Extract the information of individual tracks required for constructing the tree
    plot. Follows the same logic as the relabel_segmentation function from the Motile
    toolbox.

    Args:
        tracks (funtracks.data_model.Tracks): A tracks object containing a graph
            to be converted into a dataframe.
        colormap (napari.utils.CyclicLabelColormap): The colormap to use to
            extract the color of each node from the track ID
        prev_axis_order (list[int], Optional). The previous axis order.

    Returns:
        pd.DataFrame | None: data frame with all the information needed to
        construct the tree plot. Columns are: 't', 'node_id', 'track_id',
        'color', 'x', 'y', ('z'), 'index', 'parent_id', 'parent_track_id',
        'state', 'symbol', and 'x_axis_pos'
    """

    if tracks is None or tracks.graph is None:
        return None

    solution_nx_graph = tracks.graph
    time_key = tracks.features.time_key
    tracklet_key = tracks.features.tracklet_key

    # Batch-fetch all node attributes in one SQL query instead of per-node calls.
    node_feature_keys = [
        key
        for key, feature in tracks.features.items()
        if feature.get("feature_type") != "edge"
        and key in solution_nx_graph.node_attr_keys()
    ]
    all_keys = list(
        {DEFAULT_ATTR_KEYS.NODE_ID, time_key, tracklet_key} | set(node_feature_keys)
    )
    df_attrs = solution_nx_graph.node_attrs(attr_keys=all_keys)

    node_ids_list = df_attrs[DEFAULT_ATTR_KEYS.NODE_ID].to_list()
    node_to_time = dict(zip(node_ids_list, df_attrs[time_key].to_list(), strict=True))
    node_to_track_id = dict(
        zip(node_ids_list, df_attrs[tracklet_key].to_list(), strict=True)
    )
    feat_cols = {key: df_attrs[key].to_list() for key in node_feature_keys}
    node_to_feat = {
        node: {key: feat_cols[key][i] for key in node_feature_keys}
        for i, node in enumerate(node_ids_list)
    }

    # Batch-fetch all edges in one query and build adjacency maps.
    # This replaces all per-node predecessors/successors/in_degree/out_degree calls.
    edge_df = solution_nx_graph.edge_attrs(
        attr_keys=[DEFAULT_ATTR_KEYS.EDGE_SOURCE, DEFAULT_ATTR_KEYS.EDGE_TARGET]
    )
    sources = edge_df[DEFAULT_ATTR_KEYS.EDGE_SOURCE].to_list()
    targets = edge_df[DEFAULT_ATTR_KEYS.EDGE_TARGET].to_list()
    child_to_parent: dict[int, int] = {}
    parent_to_children: dict[int, list[int]] = {}
    for src, tgt in zip(sources, targets, strict=True):
        child_to_parent[tgt] = src
        parent_to_children.setdefault(src, []).append(tgt)

    track_list = []
    parent_mapping = []

    # Identify parent nodes (nodes with more than one child) and end nodes
    parent_nodes = [n for n in node_ids_list if len(parent_to_children.get(n, [])) > 1]
    end_nodes = [n for n in node_ids_list if n not in parent_to_children]

    # BFS to collect tracklets, cutting edges at division (parent) nodes
    tracklets = get_tracklets(
        parent_to_children,
        child_to_parent,
        node_ids_list,
        set(parent_nodes),
        node_to_track_id,
    )

    # Map every track id to its color in one vectorized colormap.map call, then
    # look up per tracklet. colormap.map has a large fixed per-call overhead, so
    # a single array call is far faster than calling it once per tracklet.
    unique_track_ids = list(set(node_to_track_id.values()))
    tid_to_color = dict(
        zip(unique_track_ids, colormap.map(np.asarray(unique_track_ids)), strict=True)
    )

    for node_set in tracklets:
        # Sort nodes in each tracklet by time using the precomputed dict
        sorted_nodes = sorted(node_set, key=lambda node: node_to_time[node])

        # track_id and color are the same for all nodes in a node_set
        parent_track_id = None
        track_id = node_to_track_id[sorted_nodes[0]]
        color = np.concatenate((tid_to_color[track_id][:3] * 255, [255]))

        for node in sorted_nodes:
            if node in parent_nodes:
                state = NodeType.SPLIT
                symbol = "t1"
            elif node in end_nodes:
                state = NodeType.END
                symbol = "x"
            else:
                state = NodeType.CONTINUE
                symbol = "o"

            track_dict = {
                "t": node_to_time[node],
                "node_id": node,
                "track_id": track_id,
                "color": color,
                "parent_id": 0,
                "parent_track_id": 0,
                "state": state,
                "symbol": symbol,
            }

            for feature_key, feature in tracks.features.items():
                if feature.get("feature_type") == "edge":
                    continue
                if feature_key not in node_to_feat[node]:
                    continue
                display_name = feature.get("display_name", feature_key)
                value_names = feature.get("value_names", None)
                val = node_to_feat[node][feature_key]
                num_values = feature.get("num_values", 1)
                if num_values > 1:
                    for i in range(num_values):
                        v = val[i]
                        if isinstance(display_name, list | tuple):
                            name = display_name[i]
                        elif (
                            isinstance(value_names, list)
                            and len(value_names) == num_values
                        ):
                            name = f"{value_names[i]}"
                        else:
                            name = f"{display_name}_{i}"
                        track_dict[name] = v
                else:
                    track_dict[display_name] = val

            # Determine parent_id and parent_track_id
            parent_id = child_to_parent.get(node)
            if parent_id is not None:
                track_dict["parent_id"] = parent_id

                if parent_track_id is None:
                    parent_track_id = node_to_track_id[parent_id]
                track_dict["parent_track_id"] = parent_track_id

            else:
                parent_track_id = 0
                track_dict["parent_id"] = 0
                track_dict["parent_track_id"] = parent_track_id

            track_list.append(track_dict)

        parent_mapping.append(
            {"track_id": track_id, "parent_track_id": parent_track_id, "node_id": node}
        )

    x_axis_order = get_sorted_track_ids(
        node_ids_list,
        node_to_track_id,
        child_to_parent,
        parent_to_children,
        prev_axis_order,
    )

    for node in track_list:
        node["x_axis_pos"] = x_axis_order.index(node["track_id"])

    df = pd.DataFrame(track_list)
    return df, x_axis_order


def find_root(track_id: int, parent_map: dict) -> int:
    """Function to find the root associated with a track by tracing its lineage"""

    # Keep traversing a track is found where parent_track_id == 0 (i.e., it's a root)
    current_track = track_id
    while parent_map.get(current_track) != 0:
        current_track = parent_map.get(current_track)
    return current_track


def order_roots_by_prev(prev_axis_order: list[int], roots: list[int]) -> list[int]:
    """Order a list of root nodes by the previous order, insert missing orders immediately
    to the right of the closest smaller numerical element.

    Args:
        prev_axis_order (list[int]): the previous order of root nodes.
        roots (list[int]): the to be sorted list of root nodes.

    Returns:
        list[int]: sorted list of root nodes.
    """

    roots_in_prev = [r for r in prev_axis_order if r in roots]
    missing = sorted(set(roots) - set(roots_in_prev))

    for r in missing:
        # find the index of the rightmost smaller element in roots_in_prev
        smaller = [x for x in roots_in_prev if x < r]
        idx = roots_in_prev.index(max(smaller)) + 1 if smaller else 0
        roots_in_prev.insert(idx, r)

    return roots_in_prev


def get_sorted_track_ids(
    node_ids: list[int],
    node_to_track_id: dict,
    child_to_parent: dict[int, int],
    parent_to_children: dict[int, list[int]],
    prev_axis_order: list[int] | None = None,
) -> list[Any]:
    """
    Extract the lineage tree plot order of the tracklet_ids on the graph, ensuring that
    each tracklet_id is placed in between its daughter tracklet_ids and adjacent to its
    parent track id.

    Args:
        node_ids: list of all node IDs.
        node_to_track_id (dict): precomputed mapping from node_id to track_id.
        child_to_parent: precomputed mapping from child node_id to parent node_id.
        parent_to_children: precomputed mapping from parent node_id to child node_ids.
        prev_axis_order (list[int], Optional). The previous axis order.

    Returns:
        list[Any] of ordered tracklet_ids.
    """

    # Topological sort via Kahn's algorithm (BFS from roots)
    in_degree = {n: (1 if n in child_to_parent else 0) for n in node_ids}
    queue = [n for n, d in in_degree.items() if d == 0]
    topo_order = []
    while queue:
        node = queue.pop(0)
        topo_order.append(node)
        for succ in parent_to_children.get(node, []):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    # Create tracklet_id to parent_tracklet_id mapping (0 if tracklet has no parent)
    tracklet_to_parent_tracklet = {}
    for node in topo_order:
        tracklet = node_to_track_id[node]
        if tracklet in tracklet_to_parent_tracklet:
            continue
        parent_id = child_to_parent.get(node)
        parent_tracklet_id = node_to_track_id[parent_id] if parent_id is not None else 0
        tracklet_to_parent_tracklet[tracklet] = parent_tracklet_id

    # Final sorted order of roots
    roots = sorted(
        [tid for tid, ptid in tracklet_to_parent_tracklet.items() if ptid == 0]
    )

    # Optionally sort roots according to their position in prev_axis_order
    if prev_axis_order is not None:
        roots = order_roots_by_prev(prev_axis_order, roots)

    x_axis_order = list(roots)

    # Find the children of each of the starting points, and work down the tree.
    while len(roots) > 0:
        children_list = []
        for tracklet_id in roots:
            children = [
                tid
                for tid, ptid in tracklet_to_parent_tracklet.items()
                if ptid == tracklet_id
            ]
            for i, child in enumerate(children):
                [children_list.append(child)]
                x_axis_order.insert(x_axis_order.index(tracklet_id) + i, child)
        roots = children_list

    return x_axis_order


def extract_lineage_tree(graph: td.GraphView, node_id: str) -> list[str]:
    """Extract the entire lineage tree including horizontal relations for a given node"""

    # Walk up to root — one SQL call per step (unavoidable for linear parent chains)
    root_node = int(node_id)
    while True:
        preds = graph.predecessors(root_node)
        if not preds:
            break
        root_node = int(preds[0])

    # BFS downward batched by level — O(num_levels) SQL calls instead of O(N_descendants)
    nodes: set[int] = set()
    level = [root_node]
    while level:
        nodes.update(level)
        children_map: dict[int, list[int]] = graph.successors(level)
        next_level = [
            int(child)
            for children in children_map.values()
            for child in children
            if int(child) not in nodes
        ]
        level = next_level

    return list(nodes)


def get_features_from_tracks(
    tracks: Tracks | None = None, features_to_ignore: list[str] | None = None
) -> list[str]:
    """Extract the regionprops feature display names currently activated on Tracks.

    Args:
        tracks (Tracks | None): the Tracks instance to extract features from

    Returns:
        features_to_plot (list[str]): list of the feature names to plot, or an empty list
        if tracks is None
    """

    if features_to_ignore is None:
        features_to_ignore = []
    features_to_plot = []
    if tracks is not None:
        for key, feature in tracks.features.items():
            # Skip edge features - only show node features in dropdown
            if feature["feature_type"] == "edge":
                continue
            name = feature.get("display_name", key)
            if feature["value_type"] in ("float", "int"):
                if feature["num_values"] > 1:
                    value_names = feature.get("value_names", None)
                    for i in range(feature["num_values"]):
                        if isinstance(name, list | tuple):
                            features_to_plot.append(name[i])
                        elif (
                            value_names is not None
                            and len(value_names) == feature["num_values"]
                        ):
                            features_to_plot.append(value_names[i])
                        else:
                            features_to_plot.append(f"{name}_{i}")
                else:
                    features_to_plot.append(name)

    features_to_plot = [
        feature
        for feature in features_to_plot
        if not any(ig in feature for ig in features_to_ignore)
    ]

    return features_to_plot
