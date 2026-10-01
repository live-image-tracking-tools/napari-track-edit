from __future__ import annotations

from typing import Any

from napari.layers import Layer
from napari.layers.utils.plane import ClippingPlane, ClippingPlaneList
from napari.utils.events import Event

ClippingPlanesState = tuple[tuple[tuple[float, ...], tuple[float, ...], bool], ...]


class EventedClippingPlanes:
    """Mixin that makes ``experimental_clipping_planes`` a linkable layer attribute.

    napari's ``link_layers`` only accepts attributes that emit an event on every layer
    of the group, and the base layer emits nothing when its clipping planes change.
    Without this mixin the tracking layers can only be linked on the attributes they
    happen to have in common (``visible``, ``opacity``, ``mouse_pan``, ``blending``,
    ...), which is far more than we want to share: hiding the points should not hide
    the segmentation, and a points layer in select mode should not lock the camera on
    the labels.

    With the emitter in place, ``link_layers(layers, ("experimental_clipping_planes",))``
    keeps the clipping planes of the tracking layers in sync -- including a move of a
    single plane, which the napari setter never sees, because it mutates the plane in
    the list rather than replacing the list -- and leaves every other attribute alone.

    A layer that is showing a plane of its own (``depiction == "plane"``) ignores
    incoming updates. The plane sliders clip the layers *without* a plane (points,
    tracks) to a thin slab around that plane, so that they mimic plane mode; letting
    that slab travel back over the link would clip the layer that defines the plane.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # set first: the base layer assigns its clipping planes during __init__
        self._applying_clipping_planes = False
        super().__init__(*args, **kwargs)
        self.events.add(experimental_clipping_planes=Event)
        # the list is created once and only ever cleared and refilled, so connecting
        # to it here also catches changes made to the individual planes it holds
        self._experimental_clipping_planes.events.connect(self._emit_clipping_planes)

    @property
    def experimental_clipping_planes(self) -> ClippingPlaneList:
        return self._experimental_clipping_planes

    @experimental_clipping_planes.setter
    def experimental_clipping_planes(
        self,
        value: dict | ClippingPlane | list[ClippingPlane | dict] | ClippingPlaneList,
    ) -> None:
        if getattr(self, "depiction", None) == "plane":
            return  # this layer is clipped by its own plane, see the class docstring

        before = self._clipping_planes_state()
        self._applying_clipping_planes = True
        try:
            Layer.experimental_clipping_planes.fset(self, value)
        finally:
            self._applying_clipping_planes = False

        # only pass on an actual change, so that two linked layers setting the planes
        # on each other come to a stop instead of handing the same value back and forth
        if self._clipping_planes_state() != before:
            self._emit_clipping_planes()

    def _clipping_planes_state(self) -> ClippingPlanesState:
        """The values of the clipping planes, to tell one update from the next"""

        return tuple(
            (plane.normal, plane.position, plane.enabled)
            for plane in self._experimental_clipping_planes
        )

    def _emit_clipping_planes(self, event: Event | None = None) -> None:
        """Announce the clipping planes of this layer to the layers linked to it"""

        emitter = getattr(
            getattr(self, "events", None), "experimental_clipping_planes", None
        )
        if emitter is None or self._applying_clipping_planes:
            # either we are still inside Layer.__init__, or we are in the middle of
            # applying an update that came in over the link and should not echo it
            return
        emitter(value=self._experimental_clipping_planes)
