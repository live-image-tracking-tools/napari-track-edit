import contextlib
from pathlib import Path

import napari
import numpy as np
from fonticon_fa6 import FA6S
from funtracks.actions import ActionGroup
from funtracks.exceptions import InvalidActionError
from funtracks.user_actions import (
    UserAddNode,
    UserDeleteNodes,
    UserUpdateSegmentation,
)
from napari.layers import Labels, Points
from napari.utils.notifications import show_info
from qtpy.QtCore import QSize, Qt
from qtpy.QtSvgWidgets import QSvgWidget
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon as qticon

from motile_tracker.application_menus.layer_dropdown import LayerDropdown
from motile_tracker.data_views.views.layers.track_labels import TrackLabels
from motile_tracker.data_views.views.layers.track_points import TrackPoints
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.data_views.views_coordinator.user_dialogs import (
    confirm_force_operation,
)

COPY_ILLUSTRATION = str(
    Path(__file__).resolve().parent.parent / "assets" / "copy_labels.svg"
)


class ScaledSvgWidget(QSvgWidget):
    """QSvgWidget that fills the available width and keeps the aspect ratio of the
    drawing, so the illustration adapts to the width of the menu panel."""

    def __init__(self, path: str):
        super().__init__(path)

        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        default_size = self.renderer().defaultSize()
        self._ratio = (
            default_size.height() / default_size.width()
            if default_size.width() > 0
            else 0
        )
        self.setMaximumWidth(default_size.width())

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return int(width * self._ratio)

    def sizeHint(self) -> QSize:
        width = min(self.maximumWidth(), max(self.width(), 200))
        return QSize(width, self.heightForWidth(width))


class CopyFromSourceWidget(QWidget):
    """Widget to copy detections from a source layer into the current tracks.

    A Points or Labels layer holding detections can be connected as a copy source (the
    chain button). While connected, right-clicking a detection on the *target* track
    layer copies the detection under the cursor from the source layer into the tracks:
    onto the background it is added with the current tracklet id, on top of an existing
    label it replaces that label unless preserve labels is active.
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.viewer = viewer
        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        # the source layer that is currently connected as a copy source, the target
        # track layer, the right-click callback attached to the target, and the copy
        # mode ("points" or "labels", derived from the current tracks object)
        self._source_layer = None
        self._target_layer = None
        self._target_callback = None
        self._mode = None
        # the tracks object we last derived the mode/source-type from
        self._synced_tracks = None

        exp = QLabel()
        exp.setWordWrap(True)
        exp.setTextFormat(Qt.MarkdownText)
        exp.setText(
            "*Connect a source Point or Labels layer to copy detections from. While "
            "connected, right-click a detection with the tracks layer active to copy it "
            "into the tracks with the current tracklet ID. Right-clicking a detection "
            "that already holds a label replaces that label. To protect existing labels, "
            "turn on 'preserve labels' in the target Segmentation layer.*"
        )

        source_box = QGroupBox("Copy from source layer")
        source_layout = QVBoxLayout(source_box)
        source_layout.addWidget(exp)
        source_layout.addWidget(QLabel("Select a source layer"))

        dropdown_button_layout = QHBoxLayout()
        # follow_active=False: the dropdown should only change when the user explicitly
        # picks a layer from it, not when the active layer in the viewer changes.
        self.source_layer_dropdown = LayerDropdown(
            self.viewer,
            (Labels, Points),
            exclude_types=(TrackLabels, TrackPoints),
            follow_active=False,
        )
        self.source_layer_dropdown.layer_changed.connect(
            self._on_source_dropdown_changed
        )
        dropdown_button_layout.addWidget(self.source_layer_dropdown)

        self.chain_btn = QPushButton()
        self.chain_btn.setCheckable(True)
        self.chain_btn.setEnabled(False)
        self.chain_btn.setToolTip(
            "Connect or disconnect a source layer (Labels or Points) to copy detections to the tracking tree."
        )
        self.chain_btn.toggled.connect(self._on_chain_toggled)
        self._set_chain_icon(connected=False)
        dropdown_button_layout.addWidget(self.chain_btn)

        source_layout.addLayout(dropdown_button_layout)

        # Controls that only apply while a source layer is connected.
        self.copy_controls_box = QGroupBox("Copy detections")
        copy_controls_layout = QVBoxLayout(self.copy_controls_box)
        hint = QLabel(
            "Right-click a detection with the tracks layer active to copy it."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-style: italic;")
        copy_controls_layout.addWidget(hint)
        # When checked, a copy never continues an existing label: it always ends up in a
        # node of its own, with a new tracklet id.
        self.new_track_on_copy_checkbox = QCheckBox(
            "Copy as new track\n(don't grow existing tracklet)"
        )
        self.new_track_on_copy_checkbox.setToolTip(
            "When checked, a copy always becomes a new track: replacing an existing label "
            "deletes its node and adds a new one, and copying to a frame that already has "
            "an object with the current tracklet id starts a new track. When unchecked, "
            "the existing node is kept and its label is grown or replaced."
        )
        copy_controls_layout.addWidget(self.new_track_on_copy_checkbox)

        # Shown while the connected source carries extra axes in front of the ones the
        # tracks use, holding alternative segmentations of the same objects.
        self.channel_hint = QLabel()
        self.channel_hint.setWordWrap(True)
        self.channel_hint.setStyleSheet("font-style: italic;")
        self.channel_hint.setVisible(False)
        copy_controls_layout.addWidget(self.channel_hint)

        # schematic of copy action
        self.illustration = ScaledSvgWidget(COPY_ILLUSTRATION)
        copy_controls_layout.addWidget(self.illustration)

        self.copy_controls_box.setVisible(False)
        source_layout.addWidget(self.copy_controls_box)

        # keep the chain button and source-layer type in sync with the current tracks
        self.tracks_viewer.tracks_updated.connect(self._sync_to_tracks)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(source_box)
        layout.addStretch(0)

        self._sync_to_tracks()

    def _set_chain_icon(self, connected: bool) -> None:
        """Show a closed chain icon when connected, an open (broken) chain when not."""

        if connected:
            self.chain_btn.setIcon(qticon(FA6S.link_slash, color="white"))
        else:
            self.chain_btn.setIcon(qticon(FA6S.link, color="white"))

    def _reset_chain(self) -> None:
        """Set the chain button back to the disconnected (unchecked) state without
        triggering a toggle."""

        self.chain_btn.blockSignals(True)
        self.chain_btn.setChecked(False)
        self.chain_btn.blockSignals(False)
        self._set_chain_icon(connected=False)

    def _update_source_controls(self) -> None:
        """Enable the chain button whenever there are tracks to copy detections into."""

        self.chain_btn.setEnabled(self.tracks_viewer.tracks is not None)

    def _sync_to_tracks(self, *args) -> None:
        """Keep the chain button and the allowed source layer type in sync with the
        current tracks object. Whenever the tracks object changes (a different tracking
        result is selected), derive the mode from it - 'labels' if it has a segmentation,
        else 'points' - and drop any stale source connection."""

        tracks = self.tracks_viewer.tracks
        self._update_source_controls()

        if tracks is self._synced_tracks:
            return
        self._synced_tracks = tracks

        # a different tracks object: any previously connected source no longer applies
        self._reset_chain()
        self._teardown_source_connection()

        if tracks is None:
            self._mode = None
            return

        self._mode = "labels" if tracks.segmentation is not None else "points"
        if self._mode == "labels":
            self.source_layer_dropdown.set_layer_types(
                (Labels,), exclude_types=(TrackLabels,)
            )
        else:
            self.source_layer_dropdown.set_layer_types(
                (Points,), exclude_types=(TrackPoints,)
            )

    def _on_source_dropdown_changed(self, name=None) -> None:
        """React to the user picking a different source layer. Selecting a layer other
        than the currently connected one disconnects the old source and resets the chain
        button to its unchecked state, so the user can connect the newly selected layer
        with a fresh click."""

        self._update_source_controls()

        source = self.source_layer_dropdown.selected_layer
        if source is self._source_layer:
            return

        # a different layer was picked: drop the stale connection and make the chain
        # button available to connect the new selection again
        if self._source_layer is not None:
            self._teardown_source_connection()
        self._reset_chain()

    def _on_chain_toggled(self, checked: bool) -> None:
        """Connect (closed chain) or disconnect (open chain) the selected source layer."""

        if checked:
            source = self.source_layer_dropdown.selected_layer
            if source is None or self._mode is None:
                if self._mode is not None:
                    show_info(
                        f"Select a {self._mode[:-1].capitalize()} source layer to "
                        "connect."
                    )
                self._reset_chain()
                return
            self._teardown_source_connection()
            self._setup_source_connection(source)
            self._set_chain_icon(connected=True)
        else:
            self._teardown_source_connection()
            self._set_chain_icon(connected=False)

    def _setup_source_connection(self, source_layer: Labels | Points) -> None:
        """Keep the detections layer visible and attach a right-click callback to the
        target track layer that copies the detection under the cursor into the tracks."""

        target_layer = self._get_target_layer()
        if target_layer is None:
            show_info("No tracks layer to copy detections into.")
            self._reset_chain()
            return

        self._source_layer = source_layer
        self._target_layer = target_layer
        # update_tracks hides all input Labels/Points layers, so re-show the source
        source_layer.visible = True
        if isinstance(source_layer, Labels):
            source_layer.contour = 1

        self._target_callback = self._make_target_callback()
        target_layer.mouse_drag_callbacks.append(self._target_callback)
        # expose the copy function so orthogonal-view copies of the target layer can
        # forward their right-clicks to it (see copy_detection_hook in ortho_views.py)
        target_layer._manual_copy_detection = self._copy_detection

        # keep the tracks layer active, so the editing keybindings (undo, redo, start a
        # new track) apply while copying
        self.viewer.layers.selection.active = target_layer
        self._update_copy_controls_visibility()

    def _teardown_source_connection(self) -> None:
        """Disconnect the right-click callback from the previously connected target
        layer."""

        if self._target_layer is not None:
            if self._target_callback is not None:
                with contextlib.suppress(ValueError):
                    self._target_layer.mouse_drag_callbacks.remove(
                        self._target_callback
                    )
            with contextlib.suppress(AttributeError):
                del self._target_layer._manual_copy_detection

        self._source_layer = None
        self._target_layer = None
        self._target_callback = None
        self._update_copy_controls_visibility()

    def _make_target_callback(self) -> callable:
        """Create the mouse callback that copies a detection on right-click."""

        def callback(layer, event):
            if event.type == "mouse_press" and event.button == 2:
                self._copy_detection(event)

        return callback

    def _copy_detection(self, event) -> None:
        """Copy the label or point that is under the cursor in the source layer into the
        tracks as a new node with the current tracklet id.

        The event may come from the target layer in the main viewer or from one of its
        orthogonal-view copies; the source layer is always looked up by the event's world
        position, which the orthogonal views share with the main viewer.
        """

        if self.tracks_viewer.tracks is None or self._source_layer is None:
            return

        if isinstance(self._source_layer, Labels):
            self._copy_label(self._source_layer, event)
        else:
            self._copy_point(self._source_layer, event)

    def _leading_axes(self, layer: Labels | Points) -> int:
        """Return how many leading axes the source layer has that the tracks do not.

        A source layer may hold several 'channels': alternative segmentations of the
        same objects, stacked on extra axes in front of the ones the tracks use. Napari
        aligns layers on their trailing dimensions, so those axes come first in the
        viewer, and their sliders pick which of the alternatives a copy reads from.
        """

        tracks = self.tracks_viewer.tracks
        if tracks is None or layer is None:
            return 0
        return max(layer.ndim - tracks.ndim, 0)

    def _copy_label(self, layer: Labels, event) -> None:
        """Copy the label under the cursor (in the clicked time point) into the target
        segmentation via an UserUpdateSegmentation action.The label is read from the
        source data at the clicked coordinates.

        If the source carries extra leading axes, the click reads from the one the
        sliders are on, so which segmentation option gets copied follows the channel
        the user has selected.
        """

        coords = np.round(layer.world_to_data(event.position)).astype(int)
        shape = np.asarray(layer.data.shape)
        # ignore clicks outside the data
        if np.any(coords < 0) or np.any(coords >= shape):
            return

        # materialise the clicked value: a lazily loaded (dask/zarr) source returns an
        # unevaluated scalar here, and comparing the frame against that makes the whole
        # comparison lazy, so np.where comes back with arrays of unknown length
        value = int(np.asarray(layer.data[tuple(coords)]))
        # ignore clicks on the background
        if not value:
            return

        lead = self._leading_axes(layer)
        channel = tuple(int(coord) for coord in coords[:lead])
        t = int(coords[lead])
        # index the selected channel and time point, so the copied pixels come from the
        # segmentation option the user is looking at
        frame = np.asarray(layer.data[(*channel, t)])
        spatial_coords = np.where(frame == value)
        if spatial_coords[0].size == 0:
            return

        self._add_segmentation_node(
            t, spatial_coords, clicked_value=self._clicked_track_label(event)
        )

    def _clicked_track_label(self, event) -> int:
        """Return the node id at the clicked location in the target segmentation, or 0
        if the click was on the background (or outside the data)."""

        tracks = self.tracks_viewer.tracks
        target_layer = self._get_target_layer()
        if tracks.segmentation is None or target_layer is None:
            return 0

        coords = np.round(target_layer.world_to_data(event.position)).astype(int)
        shape = np.asarray(tracks.segmentation.shape)
        if np.any(coords < 0) or np.any(coords >= shape):
            return 0
        return int(np.asarray(tracks.segmentation[int(coords[0])])[tuple(coords[1:])])

    def _copy_point(self, layer: Points, event) -> None:
        """Copy the point under the cursor into the tracks as a point node via an
        UserAddNode action.

        The point is looked up by the clicked coordinates (the closest point of the
        clicked time point, within its own radius).
        """

        data = np.asarray(layer.data)
        if len(data) == 0:
            return

        coords = np.asarray(layer.world_to_data(event.position))
        # extra leading axes select between alternatives, see _leading_axes: only the
        # points of the axes the sliders are on are candidates
        lead = self._leading_axes(layer)
        in_frame = np.round(data[:, lead]).astype(int) == int(round(coords[lead]))
        for axis in range(lead):
            in_frame &= np.round(data[:, axis]).astype(int) == int(round(coords[axis]))
        if not in_frame.any():
            return

        distances = np.linalg.norm(
            data[in_frame, lead + 1 :] - coords[lead + 1 :], axis=1
        )
        closest = int(np.argmin(distances))
        sizes = np.broadcast_to(
            np.atleast_1d(np.asarray(layer.size, dtype=float)), (len(data),)
        )
        # accept the click when it lands within the point itself (at least one pixel)
        if distances[closest] > max(sizes[in_frame][closest] / 2, 1):
            return

        point = data[np.flatnonzero(in_frame)[closest]]
        t = int(round(point[lead]))
        # tracks store positions in world coordinates (see nodes_from_points_list)
        position = point[lead + 1 :] * np.asarray(layer.scale[lead + 1 :])
        self._add_node(t, position=position)

    def _add_node(self, t: int, position: np.ndarray) -> None:
        """Add a point node to the tracks with the current tracklet id, at the given
        position (used for Points sources)."""

        tracks = self.tracks_viewer.tracks

        if self.tracks_viewer.selected_track is None:
            self.tracks_viewer.set_new_track_id()
        track_id = self.tracks_viewer.selected_track

        features = tracks.features
        attributes = {
            features.time_key: t,
            features.tracklet_key: track_id,
            features.position_key: position,
        }

        node_id = tracks._get_new_node_ids(1)[0]
        # Suppress view-centering during the add (see _add_segmentation_node).
        with self.tracks_viewer.center_node.blocked():
            try:
                UserAddNode(
                    tracks,
                    node=node_id,
                    attributes=attributes,
                    force=self.tracks_viewer.force,
                )
            except InvalidActionError as e:
                if e.forceable:
                    force, always_force = confirm_force_operation(message=str(e))
                    self.tracks_viewer.force = always_force
                    if force:
                        node_id = tracks._get_new_node_ids(1)[0]
                        UserAddNode(
                            tracks,
                            node=node_id,
                            attributes=attributes,
                            force=True,
                        )
                else:
                    show_info(str(e))

            # make the created node the new selection
            if tracks.graph.has_node(node_id):
                self.tracks_viewer.selected_nodes.add(node_id)

    def _add_segmentation_node(
        self,
        t: int,
        spatial_coords: tuple[np.ndarray, ...],
        clicked_value: int = 0,
    ) -> None:
        """Copy a label into the target segmentation at time ``t``.

        What a copy does depends on what was under the cursor in the target segmentation
        and on the 'preserve labels' setting of the target TrackLabels layer:

        - Clicked on an existing label (``clicked_value != 0``): that label is *replaced*
          by the copied one, even where the copied pixels do not fully cover it, and the
          result belongs to the currently active tracklet (see ``_replace_label``). With
          'preserve labels' on, replacing is not allowed and nothing is copied.
        - Clicked on the background (``clicked_value == 0``): the copied label is added
          with the current tracklet id, either in full ('preserve labels' off, existing
          labels are overwritten) or only where the target is still empty ('preserve
          labels' on).

        Args:
            t (int): The time point of the copied label.
            spatial_coords (tuple[np.ndarray, ...]): The spatial (non-time) coordinates of
                the label pixels, as returned by ``np.where`` on a single time frame.
            clicked_value (int): The node id at the clicked location in the target
                segmentation, or 0 if the click was on the background.
        """

        tracks = self.tracks_viewer.tracks
        if tracks.segmentation is None or spatial_coords[0].size == 0:
            return

        target_layer = self._get_target_layer()
        preserve = bool(getattr(target_layer, "preserve_labels", False))

        if clicked_value != 0 and tracks.graph.has_node(clicked_value):
            self._replace_label(t, spatial_coords, int(clicked_value), preserve)
        else:
            self._add_label(t, spatial_coords, preserve)

    def _replace_label(
        self,
        t: int,
        spatial_coords: tuple[np.ndarray, ...],
        node: int,
        preserve: bool,
    ) -> None:
        """Replace the label that was clicked on with the copied one.

        The copy always belongs to the currently active tracklet. Which node ends up
        holding the copied pixels depends on the active tracklet:

        - 'copy as new track' on: the clicked node is deleted and the copied pixels
          become a new node with a new tracklet id.
        - the clicked node is the active tracklet's node in this frame: it keeps its id
          (and with it its edges) and its pixels become exactly the copied ones.
        - the active tracklet has no node in this frame: the clicked node is deleted and
          the copied pixels become a new node of the active tracklet.
        - the active tracklet has a different node in this frame: the clicked node is
          deleted and the copied pixels grow that node, since a tracklet can only have one
          node per frame.

        With 'preserve labels' on, only a label of the active tracklet may be replaced -
        the labels of other tracklets are protected.

        A segmentation update can only paint with a single value, so replacing takes more
        than one action: the copied pixels are painted first, so the node is never
        momentarily empty, and whatever the copy does not cover is deleted or erased
        afterwards. The actions are committed together, so one undo reverts the copy.
        """

        tracks = self.tracks_viewer.tracks

        if self.tracks_viewer.selected_track is None:
            self.tracks_viewer.set_new_track_id()
        track_id = self.tracks_viewer.selected_track

        if preserve:
            if int(tracks.get_track_id(node)) != track_id:
                show_info(
                    "'preserve labels' is on: only a label of the current tracklet can "
                    "be replaced. Turn it off to overwrite this label."
                )
                return
            # the copy may still reach into other labels: keep those pixels as they are
            values = np.asarray(tracks.segmentation[t])[spatial_coords]
            free = (values == 0) | (values == node)
            spatial_coords = tuple(coord[free] for coord in spatial_coords)
            if spatial_coords[0].size == 0:
                show_info(
                    "Nothing to copy: all pixels belong to other labels and "
                    "'preserve labels' is on."
                )
                return

        target_node = (
            None
            if self.new_track_on_copy_checkbox.isChecked()
            else self._current_track_node(t, track_id)
        )

        actions = []
        if target_node == node:
            # the clicked label is the active tracklet's own: replace its pixels
            actions += self._paint(t, spatial_coords, node, track_id)
            actions += self._erase_outside(t, spatial_coords, node, track_id)
        else:
            if target_node is None:
                # Reserve the new node id before deleting
                target_node = tracks._get_new_node_ids(1)[0]
                actions.append(UserDeleteNodes(tracks, nodes=[node], _top_level=False))
                if self.new_track_on_copy_checkbox.isChecked():
                    self.tracks_viewer.set_new_track_id()
                    track_id = self.tracks_viewer.selected_track
            else:
                # the copy joins the node the active tracklet already has in this frame
                actions.append(UserDeleteNodes(tracks, nodes=[node], _top_level=False))
            actions += self._paint(t, spatial_coords, target_node, track_id)

        self._commit(actions, node_to_select=target_node)

    def _add_label(
        self, t: int, spatial_coords: tuple[np.ndarray, ...], preserve: bool
    ) -> None:
        """Copy a label onto the background with the current tracklet id.

        With 'preserve labels' on, only the pixels that are not part of an existing label
        are copied. The copy grows the current tracklet's node in this frame if it has
        one, unless 'copy as new track' is checked.
        """

        tracks = self.tracks_viewer.tracks

        if preserve:
            free = np.asarray(tracks.segmentation[t])[spatial_coords] == 0
            spatial_coords = tuple(coord[free] for coord in spatial_coords)
            if spatial_coords[0].size == 0:
                show_info(
                    "Nothing to copy: all pixels belong to existing labels and "
                    "'preserve labels' is on."
                )
                return

        if self.tracks_viewer.selected_track is None:
            self.tracks_viewer.set_new_track_id()
        track_id = self.tracks_viewer.selected_track

        # grow the current tracklet's node in this frame if it exists, otherwise create a
        # new node with the current tracklet id
        existing_node = self._current_track_node(t, track_id)
        if existing_node is not None and self.new_track_on_copy_checkbox.isChecked():
            # start a fresh track instead of growing the existing label in this frame
            self.tracks_viewer.set_new_track_id()
            track_id = self.tracks_viewer.selected_track
            existing_node = None

        new_value = (
            existing_node
            if existing_node is not None
            else tracks._get_new_node_ids(1)[0]
        )

        actions = self._paint(t, spatial_coords, new_value, track_id)
        self._commit(actions, node_to_select=new_value)

    def _commit(self, actions: list, node_to_select: int | None) -> None:
        """Record the actions of one copy as a single undoable step, refresh the views
        and select the node the copy landed in.

        The actions are created with ``_top_level=False`` so that a copy that takes more
        than one segmentation update (replacing a label needs a paint and an erase) is
        still undone in one go.
        """

        tracks = self.tracks_viewer.tracks
        actions = [action for action in actions if action is not None]

        # Suppress view-centering: the refresh (and the selection below) would otherwise
        # re-center the camera on the node.
        with self.tracks_viewer.center_node.blocked():
            if actions:
                tracks.action_history.add_new_action(
                    actions[0] if len(actions) == 1 else ActionGroup(tracks, actions)
                )
                tracks.refresh.emit()

            if node_to_select is not None and tracks.graph.has_node(node_to_select):
                self.tracks_viewer.selected_nodes.add(node_to_select)

    def _paint(
        self,
        t: int,
        spatial_coords: tuple[np.ndarray, ...],
        new_value: int,
        track_id: int,
    ) -> list:
        """Paint the given pixels of frame ``t`` with ``new_value``, creating the node if
        it does not exist yet and shrinking (or deleting) the nodes that are overwritten.

        Returns the actions that were performed, for the caller to commit (see
        ``_commit``); the list is empty if there was nothing to paint.
        """

        tracks = self.tracks_viewer.tracks
        old_values = np.asarray(tracks.segmentation[t])[spatial_coords]

        # Nothing to do if every pixel already belongs to the target node: skip the paint
        # so we don't push an empty (un-undoable) action onto the history.
        if np.all(old_values == new_value):
            return []

        t_array = np.full(spatial_coords[0].size, t, dtype=int)
        pixels = (t_array, *spatial_coords)
        # group the pixels by the node they currently belong to, so
        # UserUpdateSegmentation can shrink/delete the overwritten nodes.
        updated_pixels = [
            (tuple(dim[old_values == old_value] for dim in pixels), int(old_value))
            for old_value in np.unique(old_values)
        ]

        def apply(force: bool):
            return UserUpdateSegmentation(
                tracks,
                new_value=new_value,
                updated_pixels=updated_pixels,
                current_track_id=track_id,
                force=force,
                _top_level=False,
            )

        try:
            return [apply(self.tracks_viewer.force)]
        except InvalidActionError as e:
            if e.forceable:
                force, always_force = confirm_force_operation(message=str(e))
                self.tracks_viewer.force = always_force
                if force:
                    return [apply(True)]
            else:
                show_info(str(e))
        return []

    def _erase_outside(
        self,
        t: int,
        spatial_coords: tuple[np.ndarray, ...],
        node: int,
        track_id: int,
    ) -> list:
        """Erase the pixels of ``node`` in frame ``t`` that are not among the copied
        ones, so that the node is left with exactly the copied pixels.

        Returns the actions that were performed, for the caller to commit (see
        ``_commit``); the list is empty if the copy covered the whole label already.
        """

        tracks = self.tracks_viewer.tracks
        frame = np.asarray(tracks.segmentation[t])
        copied = np.zeros(frame.shape, dtype=bool)
        copied[spatial_coords] = True
        leftover = np.where((frame == node) & ~copied)
        if leftover[0].size == 0:
            return []

        t_array = np.full(leftover[0].size, t, dtype=int)
        return [
            UserUpdateSegmentation(
                tracks,
                new_value=0,
                updated_pixels=[((t_array, *leftover), node)],
                current_track_id=track_id,
                force=self.tracks_viewer.force,
                _top_level=False,
            )
        ]

    def _current_track_node(self, t: int, track_id: int) -> int | None:
        """Return the node of ``track_id`` present in frame ``t``, or None if there is
        none."""

        tracks = self.tracks_viewer.tracks
        for node in tracks.track_id_to_node.get(track_id, []):
            if tracks.get_time(node) == t:
                return int(node)
        return None

    def _get_target_layer(self) -> Labels | Points | None:
        """Return the track layer that copies go into, based on the active mode: the
        TrackLabels layer for 'labels', the TrackPoints layer for 'points'."""

        if self._mode == "labels":
            return self.tracks_viewer.tracking_layers.seg_layer
        if self._mode == "points":
            return self.tracks_viewer.tracking_layers.points_layer
        return None

    def _update_copy_controls_visibility(self, event=None) -> None:
        """Show the copy controls while a source layer is connected, and tell the user
        about the extra axes of a multi-channel source."""

        self.copy_controls_box.setVisible(self._source_layer is not None)

        lead = self._leading_axes(self._source_layer)
        if lead:
            labels = list(self.viewer.dims.axis_labels)[:lead]
            named = ", ".join(f"'{label}'" for label in labels)
            self.channel_hint.setText(
                f"This source has {lead} extra axis/axes ({named}) in front of the ones "
                "the tracks use. Move the corresponding slider(s) to choose which "
                "segmentation option a right-click copies."
            )
        self.channel_hint.setVisible(bool(lead))
