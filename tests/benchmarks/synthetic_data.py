"""Synthetic "large" tracking dataset generator for benchmarks.

Builds a :class:`funtracks.data_model.SolutionTracks` of dividing spheres directly
as an in-memory tracksdata graph, following the same construction pattern used in
``tests/conftest.py``. Masks and bounding boxes live on the graph nodes, so the
segmentation is exposed lazily as a ``td.array.GraphArrayView`` (exactly the
real-app path) -- no dense segmentation array is ever materialized. This means
``frame_shape`` can be realistically large at negligible cost; only the per-node
sphere masks consume memory.

The generator is deterministic given ``seed`` so benchmark timings are comparable
across runs and platforms.

Run directly to print dataset statistics and build time::

    python tests/benchmarks/synthetic_data.py
    python tests/benchmarks/synthetic_data.py --preset small
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import tracksdata as td
from funtracks.data_model import SolutionTracks
from funtracks.utils.tracksdata_utils import create_empty_graphview_graph
from tracksdata.nodes._mask import Mask

# Node attributes mirror tests/conftest.py. The TrackAnnotator inside SolutionTracks
# recomputes tracklet_id / lineage_id from graph topology, so track_id / lineage_id
# here are informational; edges are the source of truth for divisions.
_NODE_ATTRS = [
    "pos",
    "area",
    "track_id",
    "lineage_id",
    td.DEFAULT_ATTR_KEYS.MASK,
    td.DEFAULT_ATTR_KEYS.BBOX,
]


@dataclass(frozen=True)
class SyntheticParams:
    """Parameters controlling the synthetic dataset size and shape."""

    n_frames: int
    n_start_cells: int
    division_prob: float  # per-cell, per-frame probability of dividing
    frame_shape: tuple[int, ...]  # spatial shape (2D: (y, x); 3D: (z, y, x))
    radius: int
    max_cells: int  # cap on simultaneously active cells (bounds exponential growth)
    step_std: float = 3.0  # random-walk std per frame (pixels)
    seed: int = 42

    @property
    def ndim(self) -> int:
        """Number of dimensions including time (2D+t -> 3, 3D+t -> 4)."""
        return len(self.frame_shape) + 1


# Default benchmark size: ~14k nodes / ~100 divisions over 100 frames at a large
# spatial scale (lazy segmentation makes the big frame free).
# Tuned so the heaviest single measured op (delete + full refresh) is ~5s, keeping
# the whole suite practical to run repeatedly across three CI platforms.
LARGE = SyntheticParams(
    n_frames=100,
    n_start_cells=80,
    division_prob=0.01,
    frame_shape=(64, 512, 512),
    radius=6,
    max_cells=250,
)

# Opt-in stress size (~59k nodes). Heavy ops take tens of seconds; use locally, not CI.
XLARGE = SyntheticParams(
    n_frames=200,
    n_start_cells=150,
    division_prob=0.006,
    frame_shape=(64, 512, 512),
    radius=6,
    max_cells=600,
)

# Small preset for fast local iteration.
SMALL = SyntheticParams(
    n_frames=20,
    n_start_cells=15,
    division_prob=0.02,
    frame_shape=(32, 128, 128),
    radius=5,
    max_cells=60,
)

# 2D+time large preset (UI paths differ between 2D and 3D).
LARGE_2D = SyntheticParams(
    n_frames=100,
    n_start_cells=80,
    division_prob=0.01,
    frame_shape=(1024, 1024),
    radius=8,
    max_cells=250,
)

PRESETS = {"large": LARGE, "xlarge": XLARGE, "small": SMALL, "large_2d": LARGE_2D}


def _sphere_mask(radius: int, spatial_ndim: int) -> np.ndarray:
    """Boolean sphere mask of the given radius in an (2r+1)^ndim box."""
    size = 2 * radius + 1
    coords = np.ogrid[tuple(slice(0, size) for _ in range(spatial_ndim))]
    dist_sq = sum((c - radius) ** 2 for c in coords)
    return dist_sq <= radius**2


def _bbox_and_mask(
    center: np.ndarray, radius: int, frame_shape: tuple[int, ...]
) -> tuple[np.ndarray, Mask]:
    """Build a clamped bbox and cropped sphere Mask for a cell centered at ``center``.

    bbox layout matches tracksdata: [d0_0, d1_0, ..., d0_1, d1_1, ...] (starts then
    stops), e.g. 2D -> [y0, x0, y1, x1], 3D -> [z0, y0, x0, z1, y1, x1].
    """
    spatial_ndim = len(frame_shape)
    full = _sphere_mask(radius, spatial_ndim)
    starts, stops, crops = [], [], []
    for axis in range(spatial_ndim):
        lo = int(round(center[axis])) - radius
        hi = lo + 2 * radius + 1
        clo, chi = max(lo, 0), min(hi, frame_shape[axis])
        starts.append(clo)
        stops.append(chi)
        crops.append(slice(clo - lo, (2 * radius + 1) - (hi - chi)))
    mask_arr = np.ascontiguousarray(full[tuple(crops)])
    bbox = np.array(starts + stops, dtype=np.int64)
    return bbox, Mask(mask_arr, bbox=bbox)


def build_graph(params: SyntheticParams = LARGE) -> td.graph.GraphView:
    """Build the raw tracksdata GraphView of dividing spheres (no SolutionTracks wrap).

    Exposed separately so benchmarks can time ``SolutionTracks`` construction on a
    freshly-built graph.
    """
    rng = np.random.default_rng(params.seed)
    spatial_ndim = len(params.frame_shape)
    shape = np.array(params.frame_shape, dtype=float)

    graph = create_empty_graphview_graph(
        node_attributes=_NODE_ATTRS,
        edge_attributes=["iou"],
        ndim=params.ndim,
    )

    nodes: list[dict] = []
    indices: list[int] = []
    edges: list[dict] = []

    next_node_id = 1
    next_track_id = 1
    next_lineage_id = 1

    def add_node(t: int, pos: np.ndarray, track_id: int, lineage_id: int) -> int:
        nonlocal next_node_id
        bbox, mask = _bbox_and_mask(pos, params.radius, params.frame_shape)
        node_id = next_node_id
        next_node_id += 1
        nodes.append(
            {
                "t": t,
                "pos": [float(x) for x in pos],
                "area": float(mask.mask.sum()),
                "track_id": track_id,
                "lineage_id": lineage_id,
                "solution": True,
                td.DEFAULT_ATTR_KEYS.MASK: mask,
                td.DEFAULT_ATTR_KEYS.BBOX: bbox,
            }
        )
        indices.append(node_id)
        return node_id

    # Active cells: each is (last_node_id, pos, track_id, lineage_id).
    active: list[tuple[int, np.ndarray, int, int]] = []
    margin = params.radius + 1
    for _ in range(params.n_start_cells):
        pos = rng.uniform(margin, shape - margin)
        node_id = add_node(0, pos, next_track_id, next_lineage_id)
        active.append((node_id, pos, next_track_id, next_lineage_id))
        next_track_id += 1
        next_lineage_id += 1

    for t in range(1, params.n_frames):
        new_active: list[tuple[int, np.ndarray, int, int]] = []
        for parent_id, pos, track_id, lineage_id in active:
            step = rng.normal(0.0, params.step_std, size=spatial_ndim)
            new_pos = np.clip(pos + step, margin, shape - margin)

            can_divide = (
                rng.random() < params.division_prob
                and len(active) + len(new_active) < params.max_cells
            )
            if can_divide:
                for _ in range(2):
                    offset = rng.normal(0.0, params.radius, size=spatial_ndim)
                    child_pos = np.clip(new_pos + offset, margin, shape - margin)
                    child_id = add_node(t, child_pos, next_track_id, lineage_id)
                    edges.append(
                        {
                            "source_id": parent_id,
                            "target_id": child_id,
                            "iou": 0.0,
                            "solution": True,
                        }
                    )
                    new_active.append((child_id, child_pos, next_track_id, lineage_id))
                    next_track_id += 1
            else:
                child_id = add_node(t, new_pos, track_id, lineage_id)
                edges.append(
                    {
                        "source_id": parent_id,
                        "target_id": child_id,
                        "iou": 0.5,
                        "solution": True,
                    }
                )
                new_active.append((child_id, new_pos, track_id, lineage_id))
        active = new_active

    graph.bulk_add_nodes(nodes=nodes, indices=indices)
    graph.bulk_add_edges(edges)
    graph._update_metadata(shape=(params.n_frames, *params.frame_shape))
    return graph


def generate_synthetic_tracks(params: SyntheticParams = LARGE) -> SolutionTracks:
    """Generate a SolutionTracks of dividing spheres from ``params``.

    Returns a fully-constructed SolutionTracks whose ``.segmentation`` is a lazy
    GraphArrayView backed by the per-node masks.
    """
    graph = build_graph(params)
    return SolutionTracks(graph=graph, ndim=params.ndim, time_attr="t")


def pick_nodes(tracks: SolutionTracks) -> dict:
    """Pick deterministic, distinct nodes/edges to act on."""
    edges = tracks.graph.edge_attrs(
        attr_keys=[td.DEFAULT_ATTR_KEYS.EDGE_SOURCE, td.DEFAULT_ATTR_KEYS.EDGE_TARGET]
    )
    src = edges[td.DEFAULT_ATTR_KEYS.EDGE_SOURCE].to_list()
    tgt = edges[td.DEFAULT_ATTR_KEYS.EDGE_TARGET].to_list()
    return {
        "tree_node": int(src[0]),
        "canvas_node": int(src[len(src) // 3]),
        "del_node": int(src[len(src) // 2]),
        "del_edge": (int(src[-1]), int(tgt[-1])),
    }


def tracklet_nodes(tracks: SolutionTracks, node: int) -> list[int]:
    """All node ids sharing the tracklet (track_id) of ``node`` -- a connected path."""
    tid = tracks.get_track_id(node)
    return [int(n) for n in tracks.graph.node_ids() if tracks.get_track_id(n) == tid]


def _describe(tracks: SolutionTracks) -> dict:
    graph = tracks.graph
    src = graph.edge_attrs(attr_keys=[td.DEFAULT_ATTR_KEYS.EDGE_SOURCE])[
        td.DEFAULT_ATTR_KEYS.EDGE_SOURCE
    ].to_list()
    # A division = a source node appearing in more than one edge.
    counts: dict[int, int] = {}
    for s in src:
        counts[s] = counts.get(s, 0) + 1
    n_divisions = sum(1 for c in counts.values() if c > 1)
    return {
        "n_nodes": graph.num_nodes(),
        "n_edges": graph.num_edges(),
        "n_divisions": n_divisions,
    }


if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=PRESETS, default="large")
    args = parser.parse_args()

    params = PRESETS[args.preset]
    t0 = time.perf_counter()
    tracks = generate_synthetic_tracks(params)
    build_s = time.perf_counter() - t0
    stats = _describe(tracks)
    print(f"preset={args.preset} ndim={params.ndim} frame_shape={params.frame_shape}")  # noqa: T201
    print(  # noqa: T201
        f"nodes={stats['n_nodes']} edges={stats['n_edges']} "
        f"divisions={stats['n_divisions']} build={build_s:.2f}s"
    )
    print(f"segmentation (lazy) shape={tracks.segmentation.shape}")  # noqa: T201
