"""Estimate how the cloud of detections moves between time points, so the view can
move along with it when stepping through time.

Per time point, the center of all nodes (the median position) and their spread (the
median distance to that center) are measured. A position p at time t maps to
``c_t' + (r_t' / r_t) * (p - c_t)`` at time t'. This follows the data when it shifts,
and when it collapses or inflates while the objects themselves keep their size. Links
are not needed, so plain detections suffice, and medians keep a few spurious
detections from pulling the estimate along.
"""

from __future__ import annotations

import numpy as np
from funtracks.data_model import Tracks


class DetectionMotion:
    """The global shift and scaling of all nodes between time points.

    A snapshot of the tracks at the moment it was built: later edits do not change it
    until it is rebuilt.

    Args:
        tracks (Tracks): The tracks to read the node positions from.
    """

    def __init__(self, tracks: Tracks):
        position_key = tracks.features.position_key
        pos_keys = (
            list(position_key) if isinstance(position_key, list) else [position_key]
        )
        time_key = tracks.features.time_key
        df = tracks.graph_solution.node_attrs(attr_keys=[time_key, *pos_keys])

        if len(pos_keys) == 1:
            positions = np.asarray(df[pos_keys[0]].to_numpy(), dtype=float)
            if positions.ndim == 1:
                positions = positions[:, np.newaxis]
        else:
            positions = np.stack(
                [df[key].to_numpy().astype(float) for key in pos_keys], axis=1
            )
        times = df[time_key].to_numpy().astype(int)

        self._centers: dict[int, np.ndarray] = {}
        self._spreads: dict[int, float] = {}
        for time in np.unique(times):
            frame_positions = positions[times == time]
            center = np.median(frame_positions, axis=0)
            self._centers[int(time)] = center
            self._spreads[int(time)] = float(
                np.median(np.linalg.norm(frame_positions - center, axis=1))
            )

    def map_position(
        self, position: np.ndarray, from_time: int, to_time: int
    ) -> np.ndarray | None:
        """Carry a position at from_time along with the detections to to_time.

        Returns:
            np.ndarray | None: The new position, or None if there are no detections at
                one of the two time points.
        """

        if from_time not in self._centers or to_time not in self._centers:
            return None
        start, end = self._centers[from_time], self._centers[to_time]
        start_spread, end_spread = self._spreads[from_time], self._spreads[to_time]
        # a single detection (or detections all in one place) has no spread to scale by
        scale = (
            end_spread / start_spread if start_spread > 0 and end_spread > 0 else 1.0
        )
        return end + scale * (np.asarray(position, dtype=float) - start)
