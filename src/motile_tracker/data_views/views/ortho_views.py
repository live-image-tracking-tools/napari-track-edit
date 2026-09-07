import inspect
from collections.abc import Callable
from typing import Any

import numpy as np
from napari import Viewer
from napari.layers import Labels, Layer, Points, Shapes
from napari.utils.colormaps import DirectLabelColormap
from napari.utils.events import Event
from napari.utils.notifications import show_info
from napari_orthogonal_views.layer_sync_hooks import sync_labels_paint
from napari_orthogonal_views.ortho_view_manager import (  # noqa
    OrthoViewManager,
    _get_manager,
)

from motile_tracker.data_views.keybindings_config import KEYMAP, bind_keymap
from motile_tracker.data_views.views.layers.click_utils import (
    detect_click,
    detect_side_button,
    get_click_value,
)
from motile_tracker.data_views.views.layers.contour_labels import ContourLabels
from motile_tracker.data_views.views.layers.out_of_slice_points import ZOnlyPoints
from motile_tracker.data_views.views.layers.track_graph import TrackGraph
from motile_tracker.data_views.views.layers.track_labels import TrackLabels
from motile_tracker.data_views.views.layers.track_points import TrackPoints


# How the tracking layers are copied into the orthogonal views. Installed with
# OrthoViewManager.set_copy_layer.
def copy_layer(layer: Layer, name: str = ""):
    if isinstance(
        layer, TrackGraph
    ):  # instead of showing the tracks (not very useful on 3D data because they are
        # collapsed to a single frame), use an empty shapes layer as substitute to ensure
        # that the layer indices in the orthogonal viewer models match with those in the
        # main viewer
        res_layer = Shapes(
            name=layer.name,
            data=[],
        )

    elif isinstance(layer, TrackLabels):
        res_layer = ContourLabels(
            data=layer.data,
            name=layer.name,
            colormap=layer.colormap,
            opacity=layer.opacity,
            scale=layer.scale,
        )
        res_layer._undo_history = layer._undo_history
        res_layer._redo_history = layer._redo_history

    elif isinstance(layer, TrackPoints):
        res_layer = ZOnlyPoints(
            data=layer.data,
            name=layer.name,
            size=layer.size,  # these are not synced, so copy these properties here to set
            shown=layer.shown,  # the initial size and shown properties correctly.
        )
        # points added in an orthogonal view are created at current_size, which is not
        # synced either, so start it at the size the tracks are drawn with
        res_layer.current_size = layer.default_size
    else:
        res_layer = Layer.create(*layer.as_layer_data_tuple())

    res_layer.metadata["viewer_name"] = name
    return res_layer


# Define custom sync_filters. By default, all properties are synced forwards and backwards
# between the original layer and its derived copy. However, for Tracks Layers we need
# finer control over some syncing events, because they may have additional attached events
# that shouldn't be triggered due to reverse syncing, or because we need to capture the
# event and process it separately before it gets synced. A dictionary can be defined here
# to disable specific Layer properties for forward or reverse syncing.


def get_property_names_from_class(layer_cls):
    """Return all property names for a Layer class."""
    res = []
    for name, obj in inspect.getmembers(layer_cls):
        # must be a property with a setter
        if isinstance(obj, property) and obj.fset is not None:
            # skip special or non-sync properties
            if name in ("thumbnail", "name"):
                continue
            res.append(name)
    return res


sync_filters = {
    TrackGraph: {
        "forward_exclude": "*",  # disable all forward sync (layer is not shown)
        "reverse_exclude": "*",  # disable all reverse sync
    },
    TrackPoints: {
        "forward_exclude": {
            "data",
            "size",
            "current_size",
            "properties",  # we sync features but no need to sync properties as well
        },  # we will sync data separately on TrackPoints as we
        # need finer control
        "reverse_exclude": set(get_property_names_from_class(Points))
        - {
            "mode",
            "visible",
        },  # Block 'size' and 'current_size' syncing of the enlarged size of a selected
        # point to the original layer
    },
    TrackLabels: {
        "forward_exclude": {"colormap"},
        "reverse_exclude": set(get_property_names_from_class(Labels))
        - {
            "mode",
            "selected_label",
            "n_edit_dimensions",
            "brush_size",
            "visible",
        },  # Let TrackLabels handle these properties on its own because it is listening to
        # them and we do not want to overwrite through reverse syncing.
    },
}


# Define special functions to allow specific behavior on special layer types (TrackLabels,
# and TrackPoints). They follow the hook contract of napari-orthogonal-views: called once
# per layer per orthogonal view as hook(orig_layer, copied_layer), returning whatever has
# to be undone when the layer or the views go away.
def point_data_hook(
    orig_layer: TrackPoints,
    copied_layer: ZOnlyPoints,
) -> list[tuple[Any, Callable]]:
    """Hook to connect to sync points data and visualization between original and copied
    Points layers.

    Args:
        orig_layer (TrackPoints): TracksLabels layer from which the copied layer is
            derived.
        copied_layer (ZOnlyPoints): ZOnlyPoints equivalent of the TracksPoints layer.

    Returns:
        list[tuple[Any, Callable]]: the (signal, handler) pairs connected here, so the
            orthoviews can disconnect them again when the layer or the views go away.
    """

    # Sync the shown points and their size, as it is not synced by default. We bind to the
    # border_color event as this this is emitted when we modify shown points and point
    # size on the TrackPoints layer.
    def sync_shown_points(orig_layer: TrackPoints, copied_layer: ZOnlyPoints) -> None:
        """Sync the visible points between original TrackPoints layer and Points layers
        in ViewerModel instances (this is not a synced property).

        Both setters re-slice the copied layer on their own, so their refreshes are
        blocked and a single one is done afterwards instead.
        """

        if len(copied_layer.data) != len(orig_layer.data):
            return  # data update still on its way; it syncs these as well

        with copied_layer.events.blocker_all(), copied_layer._block_refresh():
            copied_layer.size = orig_layer.size
            copied_layer.shown = orig_layer.shown

        copied_layer.refresh()

    def shown_points_wrapper(event):
        return sync_shown_points(orig_layer, copied_layer)

    orig_layer.events.border_color.connect(shown_points_wrapper)
    connections = [(orig_layer.events.border_color, shown_points_wrapper)]

    # Receive data updates from the original layer
    def receive_data(orig_layer: TrackPoints, copied_layer: ZOnlyPoints) -> None:
        """Respond to signal from the original layer, to update the data"""

        copied_layer.events.data.disconnect(copied_layer._sync_data_wrapper)
        copied_layer.data = orig_layer.data
        copied_layer.events.data.connect(copied_layer._sync_data_wrapper)

    def receive_data_wrapper():
        return receive_data(orig_layer, copied_layer)

    orig_layer.data_updated.connect(receive_data_wrapper)
    connections.append((orig_layer.data_updated, receive_data_wrapper))

    # Sync the event that is emitted when a point is moved or deleted. We need to capture
    # it on the original layer to process it there, and potentially undo it if it was an
    # invalid action (we have no way to judge that on a normal ZOnlyPoints layer).
    def sync_data_event(
        orig_layer: TrackPoints, copied_layer: ZOnlyPoints, event: Event
    ) -> None:
        """Send the event that is emitted when a point is moved or deleted to the original
        layer"""

        if hasattr(event, "action") and event.action in ("added", "changed", "removed"):
            if orig_layer.tracks_viewer.tracks.ndim == 3 and event.action in (
                "added",
                "changed",
            ):
                show_info("Adding/moving nodes in the time dimension is not supported")
                orig_layer._refresh()
                return

            orig_layer._update_data(event)
            with orig_layer.events.blocker_all():  # try to suppress updating visibility
                orig_layer.selected_data = (
                    copied_layer.selected_data
                )  # make sure the same data is selected

    def sync_data_wrapper(event):
        return sync_data_event(orig_layer, copied_layer, event)

    copied_layer._sync_data_wrapper = sync_data_wrapper
    copied_layer.events.data.connect(sync_data_wrapper)
    connections.append((copied_layer.events.data, sync_data_wrapper))

    return connections


def paint_event_hook(
    orig_layer: TrackLabels,
    copied_layer: Labels,
) -> list[tuple[Any, Callable]]:
    """Hook to connect to paint events and process them on the original TracksLabels
    layer.

    Args:
        orig_layer (TrackLabels): TracksLabels layer from which the copied layer is
            derived.
        copied_layer (Labels): Labels equivalent of the TracksLabels layer. Instead of
            processing paint actions on this copy, we want to send them to the original
            layer and process them there.

    Returns:
        list[tuple[Any, Callable]]: the (signal, handler) pairs connected here.
    """

    def sync_paint(orig_layer: TrackLabels, copied_layer: Labels, event: Event):
        """Process paint event on original TrackLabels instance."""

        if copied_layer.data.ndim > 3:
            orig_layer._on_paint(event)
        else:
            show_info("Painting in the time dimension is not supported")
            orig_layer._revert_paint(event, copied_layer)
            orig_layer.refresh()

    def paint_wrapper(event: Event):
        """Wrap paint event and send to original layer."""

        return sync_paint(orig_layer, copied_layer, event)

    copied_layer.events.paint.connect(paint_wrapper)

    return [(copied_layer.events.paint, paint_wrapper)]


def needs_own_colormap(orig_layer: TrackLabels, copied_layer: Labels) -> bool:
    """Check whether the copied layer needs a colormap separate from the original's.

    It only does when the two disagree about the background opacity, which happens when
    contours are on and exactly one of the two views renders in 3D: contours are not
    rendered in 3D, so there the labels are shown filled and the background is hidden
    instead (see colormap_hook). In every other case the colors are identical and the
    colormap object can simply be shared.

    Args:
        orig_layer (TrackLabels): TrackLabels layer from which the copy is derived.
        copied_layer (ContourLabels): ContourLabels equivalent of the TrackLabels layer.

    Returns:
        bool: True if the copied layer needs a color dict of its own.
    """

    if orig_layer.contour == 0:
        return False
    return (orig_layer._slice.slice_input.ndisplay == 3) != (
        copied_layer._slice.slice_input.ndisplay == 3
    )


def make_own_colormap(orig_layer: TrackLabels, copied_layer: Labels) -> None:
    """Give the copied layer a color dict of its own, holding the original's colors.

    The colors are copied into the existing dict when the copy already has one for the
    same labels, because building a new DirectLabelColormap validates every color again.
    A new one is only constructed when the labels changed, or when the copy is still
    sharing the original's colormap.

    Args:
        orig_layer (TrackLabels): TrackLabels layer from which the copy is derived.
        copied_layer (ContourLabels): ContourLabels equivalent of the TrackLabels layer.
    """

    source_colors = orig_layer.colormap.color_dict
    target_colors = copied_layer.colormap.color_dict

    if (
        copied_layer.colormap is orig_layer.colormap
        or target_colors.keys() != source_colors.keys()
    ):
        copied_layer.colormap = DirectLabelColormap(
            color_dict={
                label: np.array(color, copy=True)
                for label, color in source_colors.items()
            }
        )
        return

    for label, color in source_colors.items():
        target_colors[label][:] = color


def colormap_hook(
    orig_layer: TrackLabels,
    copied_layer: Labels,
) -> list[tuple[Any, Callable]]:
    """Hook to sync colormap changes from the original TrackLabels layer to the copied
    layers. We need a hook for the special case in which one of the views is showing a 3D
    rendering in combination with partially filled contour labels. Since contours are not
    rendered in 3D, we want to display the non-filled labels with full opacity instead.

    That special case is the only one in which the copy needs a colormap of its own; the
    rest of the time both views show identical colors and share a single colormap object.

    Args:
        orig_layer (TrackLabels): TracksLabels layer from which the copied layer is
            derived.
        copied_layer (ContourLabels): ContourLabels equivalent of the TracksLabels layer.

    Returns:
        list[tuple[Any, Callable]]: the (signal, handler) pairs connected here, so they
        can be cleaned up when the layer or the views go away.
    """

    def sync_colormap(orig_layer: TrackLabels, copied_layer: Labels, event: Event):
        """Sync the colormap from the original TrackLabels instance to the copied
        ContourLabels instance. Check the slice ndisplay and contour settings to adjust
        background opacity accordingly."""

        if not needs_own_colormap(orig_layer, copied_layer):
            # Both views want exactly the same colors, so they can share the same
            # colormap object instead of giving the copy one of its own. Opacity changes
            # the original makes in place are visible here immediately, and only the
            # texture is rebuilt.
            if copied_layer.colormap is orig_layer.colormap:
                copied_layer.refresh_colormap()
            else:
                copied_layer.colormap = orig_layer.colormap
            return

        # The copy needs its own color dict, because its background opacity differs.
        make_own_colormap(orig_layer, copied_layer)
        if copied_layer._slice.slice_input.ndisplay == 3:
            copied_layer.set_opacity(orig_layer.background, 0)
        else:
            copied_layer.set_opacity(
                orig_layer.background, orig_layer.background_opacity
            )
        copied_layer.refresh_colormap()

    def update_colormap_wrapper(event: Event):
        """Wrap paint event and send to original layer."""

        return sync_colormap(orig_layer, copied_layer, event)

    orig_layer.events.colormap.connect(update_colormap_wrapper)

    return [(orig_layer.events.colormap, update_colormap_wrapper)]


def labels_paint_hook(
    orig_layer: Labels,
    copied_layer: Labels,
) -> list[tuple[Any, Callable]] | None:
    """Replacement for the built-in paint syncing, for TrackLabels layers only. This is to
    ensure that normal Labels layers keep the default behavior, but TrackLabels layers
    skip this because they are handled via our custom paint_event_hook.

    Args:
        orig_layer (Labels): the layer on the main viewer.
        copied_layer (Labels): its counterpart in the orthogonal view.

    Returns:
        list[tuple[Any, Callable]] | None: connections made for a non-TrackLabels layer,
            or None for a TrackLabels layer (handled separately).
    """

    if isinstance(orig_layer, TrackLabels):
        return None

    return sync_labels_paint(orig_layer, copied_layer)


def track_layers_hook(
    orig_layer: TrackLabels | TrackPoints,
    copied_layer: Labels | ZOnlyPoints,
) -> None:
    """Hook to capture click events on TrackLabels and TrackPoints derived Labels and
    ZOnlyPoints layers, and forward them to their original layer. Also, register key binds
    for view mode, undo & redo to copied layer, that call functions on the original layer.

    Args:
        orig_layer (TrackLabels | TrackPoints): TracksLabels or TrackPoints layer from
            which the copied layer is derived.
        copied_layer (Labels | ZOnlyPoints): Labels or ZOnlyPoints equivalent of the TracksLabels
            or TrackPoints layer.

    Nothing is returned because everything connected here lives on the copied layer,
    which is discarded together with the orthogonal view.
    """

    # define the click behavior the layer should respond to
    def click(
        orig_layer: TrackLabels | TrackPoints, layer: Labels | ZOnlyPoints, event: Event
    ):
        side_button = detect_side_button(event)
        if side_button is not None:
            orig_layer.process_click(event, side_button=side_button)
        # only the left button selects: the right button is used to copy a detection
        # from a connected source layer
        elif layer.mode == "pan_zoom" and event.button == 1:
            was_click = yield from detect_click(event)
            if was_click:
                value = get_click_value(layer, event)
                orig_layer.process_click(event, value=value, layer=layer)

    # Wrap and attach click callback
    def click_wrapper(layer, event):
        return click(orig_layer, layer, event)

    copied_layer.mouse_drag_callbacks.append(click_wrapper)

    # Bind keys to original layer TracksViewer
    bind_keymap(copied_layer, KEYMAP, orig_layer.tracks_viewer)
    if isinstance(orig_layer, TrackLabels):
        copied_layer.bind_key("m")(orig_layer.assign_new_label)


def copy_detection_hook(
    orig_layer: TrackLabels | TrackPoints, copied_layer: Labels | ZOnlyPoints
) -> None:
    """Hook to forward right-clicks on an orthogonal-view copy of a track layer to the
    main-view copy logic, so copying a detection from a connected source layer works
    identically from the ortho views.

    The forwarding is only active while a source layer is connected: the
    CopyFromSourceWidget stores a ``_manual_copy_detection`` callback on the target track
    layer while connected and removes it afterwards. It is looked up dynamically, so this
    hook is a no-op for track layers without a connected source (and their copies).

    Args:
        orig_layer (TrackLabels | TrackPoints): the original track layer in the main
            viewer.
        copied_layer (Labels | ZOnlyPoints): the ortho-view copy of that layer.
    """

    def click(layer: Labels | ZOnlyPoints, event: Event):
        copy_detection = getattr(orig_layer, "_manual_copy_detection", None)
        if (
            copy_detection is not None
            and event.type == "mouse_press"
            and event.button == 2
        ):
            copy_detection(event)

    copied_layer.mouse_drag_callbacks.append(click)


def initialize_ortho_views(viewer: Viewer) -> OrthoViewManager:
    """Initialize orthoviews on the current napari Viewer and register hooks and filters.

    Args:
        viewer (napari.Viewer): viewer to set the orthogonal views for.

    Returns:
        OrthoViewManager: reference to the OrthoViewManager instance
    """

    orth_view_manager = _get_manager(viewer)

    # set our custom copy layer function
    orth_view_manager.set_copy_layer(copy_layer)

    # additional ortho view functionalities as layer hooks
    orth_view_manager.register_layer_hook(
        (TrackLabels, TrackPoints), track_layers_hook, name="TrackLayer_clicks_and_keys"
    )
    orth_view_manager.register_layer_hook(
        TrackLabels, paint_event_hook, name="TrackLabels_paint"
    )
    orth_view_manager.register_layer_hook(
        TrackPoints, point_data_hook, name="TrackPoints_point_data"
    )
    orth_view_manager.register_layer_hook(
        TrackLabels, colormap_hook, name="TrackLabels_colormap"
    )

    orth_view_manager.register_layer_hook(
        (TrackLabels, TrackPoints), copy_detection_hook, name="Copy_detections"
    )

    # Narrow the built-in paint syncing to normal Labels layers (so that TrackLabels do
    # not run this on top of their own paint_event_hook)
    orth_view_manager.set_layer_hook("labels_paint", labels_paint_hook)

    orth_view_manager.set_sync_filters(sync_filters)
    orth_view_manager.activate_checkboxes = True

    return orth_view_manager
