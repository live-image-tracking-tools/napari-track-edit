from dataclasses import dataclass, fields

import numpy as np
import numpy.typing as npt
from napari.layers import Points
from napari.layers.points._slice import _PointSliceRequest
from napari.layers.points.points import _PointsSlicingState


@dataclass(frozen=True)
class _ZOnlyPointSliceRequest(_PointSliceRequest):
    def _get_slice_data(self, not_disp: list[int]) -> tuple[npt.NDArray, int]:
        """Modified _get_slice_data function from napari's _PointSliceRequest to apply the out-of-slice display logic only along the last non displayed axis, assumed to be z.

        Args: not_disp (list[int]): List of non-displayed dimensions (e.g. [0, 1] for t, z)

        Returns: tuple[npt.NDArray, int]: A tuple containing the indices of the points that are inside the slice and the scale factor for out-of-slice points.
        """

        data = self.data[:, not_disp]
        ndim = len(not_disp)

        # Last axis = spill axis
        spill_dim = ndim - 1
        filter_dims = list(range(spill_dim))

        scale = 1

        point, m_left, m_right = self.data_slice[not_disp].as_array()

        # Filter points that are outside the slice along any non-spill axis
        inside_mask = np.ones(len(data), dtype=bool)

        for ax in filter_dims:
            low = point[ax] - m_left[ax]
            high = point[ax] + m_right[ax]

            if np.isclose(low, high):
                low -= 0.5
                high += 0.5

            inside_mask &= (data[:, ax] >= low) & (data[:, ax] <= high)

        if not np.any(inside_mask):
            return np.empty(0, dtype=int), 1

        # Normal slice behavior within masked region, but only along spill axis
        if self.projection_mode == "none":
            low = point.copy()
            high = point.copy()
        else:
            low = point - m_left
            high = point + m_right

        too_thin = np.isclose(high, low)
        low[too_thin] -= 0.5
        high[too_thin] += 0.5

        inside_full = np.all((data >= low) & (data <= high), axis=1)

        # Must satisfy strict filtering dims
        inside_slice = inside_mask & inside_full
        slice_indices = np.where(inside_slice)[0].astype(int)

        # Out of slice display along spill axis only
        if self.out_of_slice_display and self.slice_input.ndim > 2:
            # Only candidates that pass strict filtering dims
            candidate_mask = inside_mask
            if not np.any(candidate_mask):
                return np.empty(0, dtype=int), 1

            sizes = self.size[candidate_mask] / 2
            spill_values = data[candidate_mask, spill_dim]

            low_spill = low[spill_dim]
            high_spill = high[spill_dim]

            dist_from_low = np.abs(spill_values - low_spill)
            dist_from_high = np.abs(spill_values - high_spill)
            distances = np.minimum(dist_from_low, dist_from_high)

            # points fully inside slice along spill axis
            inside_spill = (spill_values >= low_spill) & (spill_values <= high_spill)
            distances[inside_spill] = 0

            matches = distances <= sizes
            if not np.any(matches):
                return np.empty(0, dtype=int), 1

            size_match = sizes[matches]
            scale = (size_match - distances[matches]) / size_match

            candidate_indices = np.where(candidate_mask)[0]
            slice_indices = candidate_indices[matches]

        return slice_indices.astype(int), scale


class _ZOnlyPointsSlicingState(_PointsSlicingState):
    """Slicing state that builds a z-only out-of-slice request."""

    def make_slice_request_internal(self, slice_input, data_slice):
        return _ZOnlyPointSliceRequest(
            slice_input=slice_input,
            data=self.layer.data,
            data_slice=data_slice,
            projection_mode=self.layer.projection_mode,
            out_of_slice_display=self.layer.out_of_slice_display,
            size=self.layer.size,
        )


class _ZOnlyPoints(Points):
    """Points subclass that overrides the slice request to apply the out-of-slice display logic only along the last non displayed axis.

    Since napari 0.7 the slice request is built by a separate
    ``_PointsSlicingState`` object, reached via ``_get_layer_slicing_state``, so
    hook in there.
    """

    def _get_layer_slicing_state(self, data, cache):
        return _ZOnlyPointsSlicingState(layer=self, data=data, cache=cache)


# napari 0.9 removed size-based out-of-slice display (deprecating
# out_of_slice_display in favour of projection_mode) and slice margins are per
# axis, so a thick slice along z alone already gives the z-only behaviour.
_HAS_SIZE_BASED_OUT_OF_SLICE = "out_of_slice_display" in {
    f.name for f in fields(_PointSliceRequest)
}
ZOnlyPoints = _ZOnlyPoints if _HAS_SIZE_BASED_OUT_OF_SLICE else Points
