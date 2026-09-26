from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import napari
import numpy as np
from funtracks.exceptions import InvalidActionError
from funtracks.user_actions import UserUpdateSegmentation
from napari.layers import Labels
from napari.utils.notifications import show_info
from tracksdata.nodes import Mask

from napari_track_edit.data_views.keybindings_config import (
    KEYMAP,
    bind_keymap,
)
from napari_track_edit.data_views.views.layers.click_utils import (
    detect_click,
    detect_side_button,
    get_click_value,
)
from napari_track_edit.data_views.views.layers.contour_labels import ContourLabels
from napari_track_edit.data_views.views_coordinator.user_dialogs import (
    confirm_force_operation,
)

if TYPE_CHECKING:
    from napari.utils.events import Event

    from napari_track_edit.data_views.views_coordinator.tracks_viewer import (
        TracksViewer,
    )


def updates_from_masked_atoms(atoms) -> list[tuple[Mask, int, int]]:
    """Turn napari >= 0.8 paint atoms into one segmentation update per label.

    Each atom is a ``_MaskedPaintAtom``: a bounding box, a mask of the pixels that
    changed inside it, their values before the change, and the value painted.

    Note: A stroke emits one atom per brush position, normally napari records a pixel
    only the first time it is painted: it drops pixels that already hold the value being
    painted. That check reads the layer's data, which we never write back (see
    ``ContourLabels._paint_region_with_mask``), so every brush position reports its whole
      box afresh, and a slow drag repeats the same box dozens of times. Atoms that share
      a box are therefore mergedfirst, so that a pixel is turned into mask pixels only
      once.

    Args:
        atoms: the atoms of one paint event, all in the mask form.

    Returns:
        list[tuple[Mask, int, int]]: one (mask, time, old value) per label painted
            over, per brush position and time point. Each mask carries the
            bounding box of the brush position it came from; funtracks tightens
            them around their own pixels and combines the ones of a label.
    """

    # Merge per bounding box rather than over the whole event: a label painted
    # over in several places stays several small masks, which is what lets
    # funtracks tighten cheaply before it unions them.
    merged: dict[tuple, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for slice_key, mask, old_values, _new_value in atoms:
        key = tuple((sl.start, sl.stop, sl.step) for sl in slice_key)
        seen = merged.get(key)
        if seen is not None and seen[1].all():
            # nothing left in this box for another atom to contribute
            continue

        old_region = np.asarray(old_values)
        if mask is None:
            # every pixel in the bounding box changed, so napari dropped the mask
            # and stored a snapshot of the whole box instead
            mask = np.ones(old_region.shape, dtype=bool)
        else:
            old_region = np.zeros(mask.shape, dtype=old_region.dtype)
            old_region[mask] = old_values

        if seen is None:
            start = np.array([0 if sl.start is None else sl.start for sl in slice_key])
            # copy: the arrays of an atom belong to napari's undo history, and the
            # accumulator is written into below
            merged[key] = (start, mask.copy(), old_region.copy())
            continue

        _start, seen_mask, seen_old = seen
        # The first atom to reach a pixel holds its pre-paint value: a later atom
        # of the same stroke either reports the same value (read-only data, which
        # is never written back, so every atom sees the pre-stroke array) or does
        # not report the pixel at all (writable data, where napari drops pixels
        # that already hold the value being painted).
        np.copyto(seen_old, old_region, where=mask & ~seen_mask)
        seen_mask |= mask

    updates = []
    for start, mask, old_region in merged.values():
        # tracksdata bounding boxes are spatial only, so peel the time axis off
        # the box and report it separately
        spatial = start[1:]
        bbox = np.concatenate([spatial, spatial + np.array(mask.shape[1:])])
        for step, (mask_t, old_t) in enumerate(zip(mask, old_region, strict=True)):
            for old_value in np.unique(old_t[mask_t]):
                changed = mask_t & (old_t == old_value)
                updates.append(
                    (Mask(changed, bbox=bbox), int(start[0] + step), int(old_value))
                )
    return updates


def updates_from_index_atoms(atoms) -> list[tuple[tuple[np.ndarray, ...], int]]:
    """Turn napari ≤ 0.7 paint atoms into one segmentation update per label.

    Each atom is a ``data_setitem`` 3-tuple: a multi-index of the elements that
    changed, their values before the change, and the value after it. There is no
    bounding box to work from, so the coordinates are handed to funtracks, which
    builds the masks.

    Args:
        atoms: the atoms of one paint event, all in the multi-index form.

    Returns:
        list[tuple[tuple[np.ndarray, ...], int]]: one (multi-index, old value) per
            label painted over, per time point. A coordinate may appear twice in
            an index, which funtracks is free to ignore: painting a pixel into a
            mask is idempotent.
    """

    ndim = len(atoms[0][0])
    indices = tuple(
        np.concatenate([np.asarray(atom[0][axis]) for atom in atoms])
        for axis in range(ndim)
    )
    old_values = np.concatenate(
        [
            np.broadcast_to(np.asarray(old), np.shape(atom_indices[0])).ravel()
            for atom_indices, old, _new_value in atoms
        ]
    )

    updates = []
    for old_value in np.unique(old_values):
        of_value = old_values == old_value
        for time in np.unique(indices[0][of_value]):
            in_slice = of_value & (indices[0] == time)
            updates.append((tuple(axis[in_slice] for axis in indices), int(old_value)))
    return updates


def new_label(layer: TrackLabels):
    """A function to override the default napari labels new_label function.
    Must be registered (see end of this file)"""

    layer.events.selected_label.disconnect(layer._ensure_valid_label)
    _new_label(layer, new_track_id=True)
    layer.events.selected_label.connect(layer._ensure_valid_label)


def _new_label(layer: TrackLabels, new_track_id=True):
    """A function to get a new label for a given TrackLabels layer. This helper is
    abstracted out because we want to do the same thing both with and without making a
    new track id for the layer.

    Args:
        layer (TrackLabels): A TrackLabels layer from which get a new label for drawing a
            new segmentation. Updates the selected_label attribute.
        new_track_id (bool, optional): If you should also generate a new track id and set
            it to the selected_track attribute. Defaults to True.
    """

    new_selected_label = layer.tracks_viewer.tracks.get_next_node_id()
    if new_track_id or layer.tracks_viewer.selected_track is None:
        layer.tracks_viewer.set_new_track_id()
    layer.selected_label = new_selected_label
    layer.track_colormap.add_node(
        new_selected_label, layer.tracks_viewer.selected_track
    )
    # to refresh, otherwise you paint with a transparent label until you
    # release the mouse
    with layer.events.selected_label.blocker():
        layer.colormap = layer.track_colormap.to_direct_colormap()


class TrackLabels(ContourLabels):
    """Extended labels layer that holds the track information and emits
    and responds to dynamics visualization signals"""

    @property
    def _type_string(self) -> str:
        return "labels"  # to make sure that the layer is treated as labels layer for saving

    def __init__(
        self,
        viewer: napari.Viewer,
        data: np.array,
        name: str,
        opacity: float,
        scale: tuple,
        tracks_viewer: TracksViewer,
    ):
        self.tracks_viewer = tracks_viewer
        # tracks_viewer.colormap is shared: tracks_viewer already called
        # set_tracks() with the current Tracks object before constructing this
        # layer (see TracksViewer.update_tracks), so no need to do it again here.
        self.track_colormap = self.tracks_viewer.colormap

        super().__init__(
            data=data,
            name=name,
            opacity=opacity,
            colormap=self.track_colormap.to_direct_colormap(),
            scale=scale,
        )

        self.viewer = viewer
        self.highlight_opacity = 1
        self.foreground_opacity = 0.6
        self.background_opacity = 0.3
        self.highlight_contour = False
        self.foreground_contour = False

        # Key bindings (should be specified both on the viewer (in tracks_viewer)
        bind_keymap(self, KEYMAP, self.tracks_viewer)

        # Listen to paint events and changing the selected label
        self.mouse_drag_callbacks.append(self.click)
        self.events.paint.connect(self._on_paint)
        self.tracks_viewer.node_selection_updated.connect(self.update_selected_label)
        self.events.mode.connect(self._check_mode)
        self.events.selected_label.connect(self._ensure_valid_label)

        # listen to changing the contours
        self.events.contour.connect(self.tracks_viewer.mode_updated.emit)

    # Connect click events to node selection
    def click(self, _, event):
        side_button = detect_side_button(event)
        if side_button is not None:
            self.process_click(event, side_button=side_button)
        elif self.mode == "pan_zoom" and event.type == "mouse_press":
            # disable selecting in lineage mode in 3D
            # differentiate between click and drag
            was_click = yield from detect_click(event)
            if was_click:
                value = get_click_value(self, event)
                self.process_click(event, value=value)

    def new_label(self) -> None:
        """Select a valid new label to paint a new track with.

        Called by TracksViewer.request_new_track, which owns the "start a new track"
        action for all views. The label is new by construction, guard can be skipped.
        """

        self.events.selected_label.disconnect(self._ensure_valid_label)
        _new_label(self, new_track_id=True)
        self.events.selected_label.connect(self._ensure_valid_label)

    def process_click(
        self,
        event: Event,
        value: int | None = None,
        side_button: int | None = None,
        layer: ContourLabels | None = None,
    ):
        """Process the click event to update the selected nodes.

        Args:
            event (Event): The click event.
            value (int): The label value (node) at the clicked position.
            side_button (int | None): the integer for the mouse side buttons (4: back, 5: forward)
            layer (ContourLabels | None): The (ortho view) layer from which the click originated.
                If provided, it is used to check label visibility in that layer's colormap.
        """

        # Communicate that the click comes from the napari canvas
        with self.tracks_viewer.viewer_interaction():
            # Intercept mouse side button navigation (back/forward)
            if side_button is not None:
                self.tracks_viewer.select_node_set_from_history(
                    previous=side_button == 4
                )
                return

            if value is not None and value != 0:
                # check visibility in the respective colormap. If a label is not visible, it
                # is not allowed to be selected from this view
                if layer is not None:
                    is_visible = layer.colormap.color_dict.get(value)[3] > 0
                else:
                    is_visible = self.colormap.color_dict.get(value)[3] > 0
                if is_visible:
                    append = "Shift" in event.modifiers
                    jump = "Control" in event.modifiers
                    pick_track = "Alt" in event.modifiers
                    if pick_track:
                        self.tracks_viewer.select_track_id_from_node(int(value))
                    elif jump:
                        self.tracks_viewer.center_on_node(value)
                    else:
                        self.tracks_viewer.selected_nodes.add(int(value), append)
                else:
                    warnings.warn(
                        f"Node {value} is not visible in this view and cannot be selected.",
                        stacklevel=2,
                    )

    def _check_mode(self):
        """Check if the mode is valid and call the ensure_valid_label function"""
        # here disconnecting the event listener is still necessary because
        # self.mode = paint triggers the event internally and it is not blocked with
        # event.blocker()
        self.events.mode.disconnect(self._check_mode)
        if self.mode == "polygon":
            show_info("Please use the paint tool to update the label")
            self.mode = "paint"

        self.events.mode.connect(self._check_mode)

    def redo(self):
        """Overwrite the redo functionality of the labels layer and invoke redo action on
        the tracks_viewer.tracks first
        """

        self.tracks_viewer.redo()

    def undo(self):
        """Overwrite undo function and invoke undo action on the
        tracks_viewer.tracks first
        """

        self.tracks_viewer.undo()

    @staticmethod
    def _parse_paint_event(event_val):
        """Turn a paint event into the segmentation updates funtracks expects.

        napari reports the atoms of an event in one of two forms, never mixed
        within an event: the mask form of napari >= 0.8, and the multi-index form
        that ``data_setitem`` still uses.

        Args:
            event_val (list[tuple]): the paint "atoms" the labels layer recorded
                for this event.

        Returns:
            list[tuple]: the updates for every label painted over, in whichever of
                the two forms ``UserUpdateSegmentation`` was handed. Empty when the
                event changed nothing.
        """

        if not event_val:
            return []

        if len(event_val[0]) == 3:  # multi-index atoms
            return updates_from_index_atoms(event_val)
        return updates_from_masked_atoms(event_val)

    def _revert_paint(self, _, source_layer: Labels | None = None):
        """Revert a paint event after it fails validation (no actions have
        been created). This keeps the view synced with the backend data.
        been created). If a source_layer is provided, the paint event will be reverted on
        this layer (this is necessary for orthoviews). This keeps the view synced with
        the backend data.
        """
        if source_layer is not None:
            source_layer.undo()  # revert on the orthoview
        else:
            super().undo()

    def _on_paint(self, event):
        """Listen to the paint event and check which track_ids have changed"""

        updated_pixels = self._parse_paint_event(event.value)
        if not updated_pixels:
            return

        # Every entry covers exactly one time point, so more than one distinct time
        # means the brush spanned frames, which is not allowed.
        if len({u[1] if len(u) == 3 else int(u[0][0][0]) for u in updated_pixels}) > 1:
            show_info("Painting in the time dimension is not supported")
            self._revert_paint(event)
            self._refresh()  # also re-syncs the orthoviews, if present
            return

        # painting happens on the canvas, so specify with tracks_viewer.viewer_interaction
        with self.tracks_viewer.viewer_interaction():
            # make sure that 0 (in the case or erasing) or a valid label (in the case of
            # painting) is selected.
            if (
                self.mode == "erase"
                or (self.mode == "fill" and self.selected_label == 0)
                or (self.mode == "paint" and self.selected_label == 0)
            ):
                target_value = 0
            else:
                self._ensure_valid_label()
                # TODO: drop this conversion once tracksdata coerces numpy scalars
                # at the SQL query boundary; see the note in _ensure_valid_label.
                # Passing napari's numpy selected_label straight through makes
                # UserUpdateSegmentation read an existing node as missing on a
                # database-backed graph, and it then tries to add a node that is
                # already there.
                target_value = int(self.selected_label)

            with self.events.selected_label.blocker():
                try:
                    UserUpdateSegmentation(
                        tracks=self.tracks_viewer.tracks,
                        new_value=target_value,
                        updated_pixels=updated_pixels,
                        current_track_id=self.tracks_viewer.selected_track,
                        force=self.tracks_viewer.force,
                    )  # paint with the updated self.selected_label, not with the value from the
                    # event, to ensure it is a valid label.
                except InvalidActionError as e:
                    if e.forceable:
                        # If the action is invalid, ask the user if they want to force it anyway
                        force, always_force = confirm_force_operation(message=str(e))
                        self.tracks_viewer.force = always_force
                        super().undo()
                        if not force:
                            self._refresh()  # to trigger refresh on orthoviews, if present
                        else:
                            # try again with force enabled
                            UserUpdateSegmentation(
                                tracks=self.tracks_viewer.tracks,
                                new_value=target_value,
                                updated_pixels=updated_pixels,
                                current_track_id=self.tracks_viewer.selected_track,
                                force=True,
                            )
                    else:
                        warnings.warn(str(e), stacklevel=2)
                        super().undo()
                        self._refresh()

    def _refresh(self):
        """Refresh the data in the labels layer"""
        self.data = self.tracks_viewer.tracks.segmentation
        # No set_tracks() here: TracksViewer._refresh already synced track_colormap
        # before calling this, and the other caller (_on_paint's revert path) never
        # changes the node/track-id set - it just undoes a rejected paint - so the
        # cached colors are already correct. Just rebuild the napari-facing colormap
        # from that cached state.
        self.colormap = self.track_colormap.to_direct_colormap()
        self.refresh()

    def update_label_colormap(self, visible: list[int] | str) -> None:
        """Updates the opacity for the highlighted, foreground, and background labels,
        and adds labels to the filled_labels if necessary.
        """

        highlighted = set(self.tracks_viewer.selected_nodes)
        foreground = self.track_colormap.nodes if visible == "all" else visible
        self.background = (
            []
            if visible == "all"
            else self.track_colormap.nodes - visible - highlighted
        )

        self.filled_labels = []
        if self.contour > 0 and visible != "all":
            if not self.highlight_contour:
                self.filled_labels.extend(highlighted)
            if not self.foreground_contour:
                self.filled_labels.extend(foreground)

        # special case: 3D rendering + partially filled contours -> set background opacity
        # to 0
        if self._slice.slice_input.ndisplay == 3 and self.contour > 0:
            self.track_colormap.set_alpha(self.background, 0)
        else:
            # set normal background opacity
            self.track_colormap.set_alpha(self.background, self.background_opacity)
        self.track_colormap.set_alpha(foreground, self.foreground_opacity)
        self.track_colormap.set_alpha(highlighted, self.highlight_opacity)

        # Setting colormap also emits `selected_label`, which triggers
        # `_ensure_valid_label` and would rebuild the colormap a second time; that
        # validation is only needed when the painting label changes, not on a
        # highlight/opacity refresh, so block it here.
        with self.events.selected_label.blocker():
            self.colormap = self.track_colormap.to_direct_colormap()

    def new_colormap(self):
        """Override existing function to generate new colormap on tracks_viewer and
        emit refresh signal to update colors in all layers/widgets"""

        self.tracks_viewer.colormap.color_source.shuffle()
        self.tracks_viewer._refresh()

    def update_selected_label(self):
        """Update the selected label in the labels layer"""

        if len(self.tracks_viewer.selected_nodes) > 0:
            node = int(self.tracks_viewer.selected_nodes[0])
            self.selected_label = node
            self.tracks_viewer.selected_track = int(
                self.tracks_viewer.tracks.get_track_id(node)
            )

    def _ensure_valid_label(self, event: Event | None = None):
        """Make sure a valid label is selected, because it is not allowed to paint with
        a label that already exists at a different timepoint.

        Scenarios:

        1. If a node with the selected label value (node id) exists at a different time
           point, check if there is any node with the same track_id at the current time
           point.

           a. If there is a node with the same track id, select that one, so that it
              can be used to update an existing node.
           b. If there is no node with the same track id, create a new node id and
              paint with the track_id of the selected label. This can be used to add a
              new node with the same track id at a time point where it does not (yet)
              exist (anymore).

        2. If there is no existing node with this value in the graph, it is assumed that
           you want to add a node with the current track id. Retrieve the track_id from
           self.current_track_id and use it to find if there are any nodes of this track
           id at current time point.

        3. If no node with this label exists yet, it is valid and can be used to start a
           new track id. Therefore, create a new node id and map a new color. Add it to
           the dictionary.

        4. If a node with the label exists at the current time point, it is valid and
           can be used to update the existing node in a paint event. No action is needed.
        """

        # The background label is never a valid label to paint a node with (painting
        # with it erases), so it should never get a track id or a color. napari binds
        # "X" on Labels layers to swap_selected_and_background_labels, which sets
        # selected_label to the background value: without this guard, that would give
        # the background an opaque color and make the whole segmentation background
        # render in the track color (see issue #493).
        if self.selected_label == self.colormap.background_value:
            return

        update_colormap = False
        if self.tracks_viewer.tracks is not None:
            # The viewer may carry extra leading axes the tracks do not have, so time is
            # not necessarily axis 0.
            current_timepoint = self.viewer.dims.current_step[
                self.tracks_viewer.tracks_dims.time_axis
            ]

            # TODO: drop this conversion once tracksdata coerces numpy scalars at
            # the SQL query boundary. napari stores selected_label as a numpy
            # integer, and SQLGraph.has_node(np.int64(n)) answers False where
            # has_node(n) answers True, so an existing node reads as missing and
            # the caller goes on to add a node that is already there. The
            # in-memory backend matches either type, so this only bites on a
            # database. Same conversion in _on_paint.
            selected_label = int(self.selected_label)

            # A label that names a node outside the solution but still present in
            # graph_full is soft-deleted: the node was removed, or added and then
            # undone. Select a new label if this is the case.
            if not self.tracks_viewer.tracks.graph_solution.has_node(
                selected_label
            ) and self.tracks_viewer.tracks.graph_full.has_node(selected_label):
                _new_label(self, new_track_id=False)
                # _new_label picks a different label, so re-read it.
                selected_label = int(self.selected_label)

            # if a node with the given label is already in the graph
            if self.tracks_viewer.tracks.graph_solution.has_node(selected_label):
                # Update the track id
                self.tracks_viewer.selected_track = (
                    self.tracks_viewer.tracks.get_track_id(selected_label)
                )
                existing_time = self.tracks_viewer.tracks.get_time(selected_label)
                if existing_time == current_timepoint:
                    # we are changing the existing node. This is fine
                    pass
                else:
                    # if there is already a node in that track in this frame, edit that
                    # instead
                    edit = False
                    if (
                        self.tracks_viewer.selected_track
                        in self.tracks_viewer.tracks.track_id_to_node
                    ):
                        for node in self.tracks_viewer.tracks.track_id_to_node[
                            self.tracks_viewer.selected_track
                        ]:
                            if (
                                self.tracks_viewer.tracks.get_time(node)
                                == current_timepoint
                            ):
                                self.selected_label = int(node)
                                edit = True
                                break

                    if not edit:
                        # use a new label, but the same track id
                        _new_label(self, new_track_id=False)

            # the current node does not exist in the graph.
            # Use the current selected_track as the track id (will be a new track if a
            # new label was found with "m")
            # Check that the track id is not already in this frame.
            else:
                # if there is already a node in that track in this frame, edit that
                # instead
                if (
                    self.tracks_viewer.selected_track
                    in self.tracks_viewer.tracks.track_id_to_node
                ):
                    for node in self.tracks_viewer.tracks.track_id_to_node[
                        self.tracks_viewer.selected_track
                    ]:
                        if (
                            self.tracks_viewer.tracks.get_time(node)
                            == current_timepoint
                        ):
                            self.selected_label = int(node)
                            break

                elif self.tracks_viewer.selected_track is None:
                    self.tracks_viewer.selected_track = (
                        self.tracks_viewer.tracks.get_next_track_id()
                    )
                    update_colormap = True

        # update color and emit signal
        self.tracks_viewer.set_track_id_color(self.tracks_viewer.selected_track)
        if update_colormap:
            self.track_colormap.add_node(
                self.selected_label, self.tracks_viewer.selected_track
            )
            with self.events.selected_label.blocker():
                self.colormap = self.track_colormap.to_direct_colormap()  # refresh
        self.tracks_viewer.update_track_id.emit()

    @napari.layers.Labels.n_edit_dimensions.setter
    def n_edit_dimensions(self, n_edit_dimensions):
        # Overriding the setter to disable editing in time dimension
        if n_edit_dimensions > self.tracks_viewer.tracks.ndim - 1:
            n_edit_dimensions = self.tracks_viewer.tracks.ndim - 1
        self._n_edit_dimensions = n_edit_dimensions
        self.events.n_edit_dimensions()
