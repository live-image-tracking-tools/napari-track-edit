"""Relating the axes of a Tracks object to the axes of the napari viewer.

The viewer can have more dimensions than the tracks do, e.g. because of multi-channel
images being present in the same viewer as the tracks layers. Napari aligns every layer
on its trailing dimensions, so the tracks occupy the last ``ndim_tracks`` world axes of
the viewer. All additional leading dimensions are for visualization only.

``dims.order`` only permutes how axes are *displayed*. ``dims.point``,
``dims.current_step`` and ``dims.range`` stay indexed by world axis, and ``roll()`` and
``transpose()`` touch nothing but ``order``. So rolling or transposing with the napari
buttons never moves an axis from one world index to another, and the map between tracks
axes and world axes does not have to be remembered across a roll. A roll can put an extra
axis on screen, so any code reading a displayed axis has to ask whether it is a tracks
axis at all before using it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


def world_to_layer_axis(
    world_axis: int, ndim_world: int, ndim_layer: int
) -> int | None:
    """Map a viewer (world) axis onto a layer's own axis, or None if it has none.

    A layer with fewer dimensions than the viewer has no axis at all corresponding to the
    leading world axes, and subtracting the offset there gives a negative index that
    numpy would silently wrap to the wrong end of the array instead of raising.

    Args:
        world_axis (int): Axis index in the viewer's world coordinate system.
        ndim_world (int): Number of dimensions of the viewer.
        ndim_layer (int): Number of dimensions of the layer.

    Returns:
        int | None: The corresponding layer axis, or None if the layer does not
            span this world axis.
    """

    layer_axis = world_axis - (ndim_world - ndim_layer)
    if layer_axis < 0 or layer_axis >= ndim_layer:
        return None
    return layer_axis


@dataclass(frozen=True)
class TracksDims:
    """Where a Tracks object's axes sit among the viewer's world axes.

    The tracks take the last ``ndim_tracks`` world axes; ``ndim_offset`` counts the
    extra ones in front, which are for visualization only. Meant to be built at the
    point of use rather than stored, because ``ndim_world`` changes when layers are
    added or removed.

    To know where a layer sits with respect to the viewer, use layer.ndim as ndim_world.

    Attributes:
        ndim_world (int): Number of dimensions of the viewer (or of the layer the
            tracks are being related to).
        ndim_tracks (int): Number of dimensions of the tracks, time included.
    """

    ndim_world: int
    ndim_tracks: int

    def __post_init__(self) -> None:
        if self.ndim_tracks < 2:
            raise ValueError(
                f"Tracks must have at least a time and one spatial axis, got "
                f"{self.ndim_tracks}"
            )
        if self.ndim_world < self.ndim_tracks:
            raise ValueError(
                f"The viewer has fewer dimensions ({self.ndim_world}) than the "
                f"tracks ({self.ndim_tracks}); the tracks cannot be shown in it"
            )

    @property
    def ndim_offset(self) -> int:
        """Number of extra world axes in front of the tracks' own axes.

        Also the index of the first tracks axis, so ``values[dims.ndim_offset:]`` is
        the tracks' part of anything indexed by world axis (``dims.point``,
        ``dims.current_step``, ``dims.range``, the axis labels).
        """

        return self.ndim_world - self.ndim_tracks

    @property
    def time_axis(self) -> int:
        """World axis carrying time, which is the tracks' first axis."""

        return self.ndim_offset

    def embed_point(
        self, location: Sequence[float], point: Sequence[float]
    ) -> list[float]:
        """Write a tracks-space location into a full-length viewer point.

        The extra leading axes keep whatever the viewer is currently showing, only the
        trailing tracks axes are replaced.

        Args:
            location (Sequence[float]): Position in tracks space, time included.
            point (Sequence[float]): The viewer's current ``dims.point``.

        Returns:
            list[float]: A point of length ``ndim_world``, ready to assign to
                ``viewer.dims.point``.

        Raises:
            ValueError: If either sequence has the wrong length, which would
                otherwise silently produce a point napari cannot use.
        """

        if len(location) != self.ndim_tracks:
            raise ValueError(
                f"Location {tuple(location)} has {len(location)} dimensions, "
                f"expected {self.ndim_tracks}"
            )
        if len(point) != self.ndim_world:
            raise ValueError(
                f"Point has {len(point)} dimensions, expected {self.ndim_world}"
            )

        embedded = list(point)
        embedded[self.ndim_offset :] = list(location)
        return embedded
