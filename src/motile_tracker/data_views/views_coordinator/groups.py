from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any
from warnings import warn

from fonticon_fa6 import FA6S
from funtracks.features._feature import Feature
from funtracks.user_actions import UserUpdateNodesAttrs
from napari._qt.qt_resources import QColoredSVGIcon
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon as qticon

if TYPE_CHECKING:
    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer

from motile_tracker.data_views.views.tree_view.tree_widget_utils import (
    extract_lineage_tree,
)
from motile_tracker.import_export.menus.export_dialog import ExportDialog


class CollectionButton(QWidget):
    """Widget holding a name and delete icon for listing in the QListWidget. Also contains
    an initially empty instance of a Collection to which nodes can be assigned"""

    def __init__(self, name: str):
        super().__init__()
        self.name = QLabel(name)
        self.name.setFixedHeight(20)
        self.collection = set()
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.node_count = QLabel(f"{len(self.collection)} node(s)")

        export_icon = qticon(FA6S.file_export, color="white")
        self.export = QPushButton(icon=export_icon)
        self.export.setFixedSize(20, 20)
        self.export.setToolTip("Export nodes in this group to CSV or geff")

        select_icon = qticon(FA6S.arrow_pointer, color="white")
        self.select_nodes_in_group_btn = QPushButton(icon=select_icon)
        self.select_nodes_in_group_btn.setFixedSize(20, 20)
        self.select_nodes_in_group_btn.setToolTip("Select nodes in group")

        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(20, 20)
        layout = QHBoxLayout()
        layout.setSpacing(1)
        layout.addWidget(self.name)
        layout.addWidget(self.node_count)
        layout.addWidget(self.select_nodes_in_group_btn)
        layout.addWidget(self.export)
        layout.addWidget(self.delete)
        layout.setSpacing(10)

        self.setLayout(layout)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint

    def update_node_count(self, n_nodes: int | None = None) -> None:
        if n_nodes is None:
            n_nodes = len(self.collection)
        self.node_count.setText(f"{n_nodes} node(s)")


class CollectionWidget(QWidget):
    """Widget for holding in-memory Collections (groups). Emits a signal whenever
    a collection is selected in the list, to update the viewing properties
    """

    group_changed = Signal()

    def __init__(self, tracks_viewer: TracksViewer):
        super().__init__()

        self.tracks_viewer = tracks_viewer
        self.tracks_viewer.node_selection_updated.connect(
            self._update_buttons_and_node_count
        )

        self.group_changed.connect(self._update_buttons_and_node_count)

        self.collection_list = QListWidget()
        self.collection_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.collection_list.itemSelectionChanged.connect(self._selection_changed)
        self.selected_collection = None

        self._is_deleted = False

        # edit layout
        edit_widget = QGroupBox("Edit group")
        edit_layout = QVBoxLayout()

        add_layout = QHBoxLayout()
        self.add_nodes_btn = QPushButton("Add node(s)")
        self.add_nodes_btn.clicked.connect(self._add_selection)
        self.add_track_btn = QPushButton("Add track(s)")
        self.add_track_btn.clicked.connect(lambda: self._add_track(add=True))
        self.add_lineage_btn = QPushButton("Add lineage(s)")
        self.add_lineage_btn.clicked.connect(lambda: self._add_lineage(add=True))
        add_layout.addWidget(self.add_nodes_btn)
        add_layout.addWidget(self.add_track_btn)
        add_layout.addWidget(self.add_lineage_btn)

        remove_layout = QHBoxLayout()
        self.remove_node_btn = QPushButton("Remove node(s)")
        self.remove_node_btn.clicked.connect(self._remove_selection)
        self.remove_track_btn = QPushButton("Remove track(s)")
        self.remove_track_btn.clicked.connect(lambda: self._add_track(add=False))
        self.remove_lineage_btn = QPushButton("Remove lineage(s)")
        self.remove_lineage_btn.clicked.connect(lambda: self._add_lineage(add=False))
        remove_layout.addWidget(self.remove_node_btn)
        remove_layout.addWidget(self.remove_track_btn)
        remove_layout.addWidget(self.remove_lineage_btn)

        edit_layout.addLayout(add_layout)
        edit_layout.addLayout(remove_layout)
        edit_widget.setLayout(edit_layout)

        # adding a new group
        new_group_box = QGroupBox("New Group")
        new_group_layout = QHBoxLayout()
        self.group_name = QLineEdit("new group")
        new_group_layout.addWidget(self.group_name)
        self.new_group_button = QPushButton("Create")
        self.new_group_button.clicked.connect(
            lambda: self._add_group(name=None, select=True)
        )
        new_group_layout.addWidget(self.new_group_button)
        new_group_box.setLayout(new_group_layout)

        # combine widgets
        layout = QVBoxLayout()
        layout.addWidget(self.collection_list)
        layout.addWidget(edit_widget)
        layout.addWidget(new_group_box)
        self.setLayout(layout)

        self._update_buttons_and_node_count()

    def _update_buttons_and_node_count(self, update_counts: bool = True) -> None:
        """Enable or disable selection and edit buttons depending on whether a group is
        selected, nodes are selected, and whether the group contains any nodes"""

        # Guard against widget deletion
        if self._is_deleted:
            self.tracks_viewer.node_selection_updated.disconnect(
                self._update_buttons_and_node_count
            )
            return

        try:
            selected = self.collection_list.selectedItems()
        except RuntimeError as e:
            if "has been deleted" in str(e):
                self._is_deleted = True
                return  # underlying Qt object already gone
            else:
                raise

        if selected and len(self.tracks_viewer.selected_nodes) > 0:
            self.add_nodes_btn.setEnabled(True)
            self.add_track_btn.setEnabled(True)
            self.add_lineage_btn.setEnabled(True)
            self.remove_node_btn.setEnabled(True)
            self.remove_track_btn.setEnabled(True)
            self.remove_lineage_btn.setEnabled(True)
        else:
            self.add_nodes_btn.setEnabled(False)
            self.add_track_btn.setEnabled(False)
            self.add_lineage_btn.setEnabled(False)
            self.remove_node_btn.setEnabled(False)
            self.remove_track_btn.setEnabled(False)
            self.remove_lineage_btn.setEnabled(False)

        if selected and update_counts:
            # only update the counts if the tracks data has been updated
            collection_item = self.collection_list.itemWidget(selected[0])
            nodes = (
                collection_item.collection
                - self.tracks_viewer.selected_nodes.deleted_items
            )
            collection_item.update_node_count(len(nodes))

        if self.tracks_viewer.tracks is not None:
            self.new_group_button.setEnabled(True)
        else:
            self.new_group_button.setEnabled(False)

    def _jump_to_node(self, forward: bool) -> None:
        """Jump to the next/previous selected node in the list"""

        node = self.tracks_viewer.selected_nodes.next_node(forward)
        if node:
            self.tracks_viewer.center_on_node(node)

    def _invert_selection(self) -> None:
        """Invert the current selection"""

        all_nodes = set(self.tracks_viewer.tracks.graph.node_ids())
        inverted = list(all_nodes - set(self.tracks_viewer.selected_nodes))
        self.tracks_viewer.selected_nodes.add_list(inverted, append=False)

    def _refresh(self) -> None:
        """Keep the node collection in sync with the node group attributes on the graph"""

        collection_items = [
            self.collection_list.itemWidget(self.collection_list.item(i))
            for i in range(self.collection_list.count())
        ]
        for collection_item in collection_items:
            nodes = (
                collection_item.collection
                - self.tracks_viewer.selected_nodes.deleted_items
            )
            collection_item.update_node_count(
                len(nodes)
            )  # update the count, but keep deleted nodes in the collection.

    def retrieve_existing_groups(self) -> None:
        """Create collections based on the node attributes"""

        # first clear the entire list
        self.collection_list.clear()
        self.selected_collection = None  # set back to None

        if self.tracks_viewer.tracks is None:
            # nothing is loaded, so the cleared list above is the whole answer
            return

        # find existing group features on Tracks
        group_features = [
            (group_name, group_dict)
            for group_name, group_dict in self.tracks_viewer.tracks.features.items()
            if group_dict["value_type"] == "bool" and group_name != "solution"
        ]
        group_dict = {}
        for group_name, _ in group_features:
            if group_name not in group_dict:
                nodes = [
                    node
                    for node in self.tracks_viewer.tracks.graph.node_ids()
                    if self.tracks_viewer.tracks.get_node_attr(node, group_name)
                ]
                group_dict[group_name] = nodes
                self._add_group(name=group_name, select=True)
                self.selected_collection.collection = set(group_dict[group_name])
                nodes = [
                    n
                    for n in self.selected_collection.collection
                    if n not in self.tracks_viewer.selected_nodes.deleted_items
                ]
                self.selected_collection.update_node_count(
                    len(nodes)
                )  # update node count

        self._update_buttons_and_node_count()

    def _selection_changed(self) -> None:
        """Update the currently selected collection and send update signal"""

        selected = self.collection_list.selectedItems()
        if selected:
            self.selected_collection = self.collection_list.itemWidget(selected[0])
            self.group_changed.emit()

        self._update_buttons_and_node_count()

    def _add_nodes(self, nodes: list[Any] | None = None) -> None:
        """Add individual nodes to the selected collection and send update signal

        Args:
            nodes (list, optional): A list of nodes to add to this group. If not provided,
            the nodes are taken from the current selection in tracks_viewer.selected_nodes
        """

        if self.selected_collection is not None:
            self.selected_collection.collection = (
                self.selected_collection.collection | set(nodes)
            )

            # Use UpdateNodesAttrs to set the feature value to True for all nodes at once
            feature_key = self.selected_collection.name.text()
            UserUpdateNodesAttrs(
                tracks=self.tracks_viewer.tracks,
                nodes=[int(n) for n in nodes],
                attrs={feature_key: [True] * len(nodes)},
            )

            self.group_changed.emit()

    def _add_selection(self) -> None:
        """Add the currently selected node(s) to the collection"""

        self._add_nodes(self.tracks_viewer.selected_nodes.as_list)

    def _add_track(self, add: bool = True) -> None:
        """Adds or removes the tracks belonging to selected nodes to the selected
        collection.

        Args:
            add (bool=True): when True, will add the nodes to the collection, when False,
            it will remove them.
        """

        selected = set(self.tracks_viewer.selected_nodes)
        nodes_to_process = []

        while selected:
            node_id = selected.pop()
            track_id = self.tracks_viewer.tracks.get_track_id(node_id)
            track = self.tracks_viewer.tracks.track_annotator.tracklet_id_to_nodes[
                track_id
            ]
            nodes_to_process.extend(track)
            selected.difference_update(track)

        self._add_nodes(nodes_to_process) if add else self._remove_nodes(
            nodes_to_process
        )

    def _add_lineage(self, add: bool = True) -> None:
        """Add or remove lineages to/from the selected collection
        Args:
            add (bool=True): when True, will add the nodes to the collection, when False,
            it will remove them.
        """

        selected = set(self.tracks_viewer.selected_nodes)
        nodes_to_process = []

        while selected:
            node_id = selected.pop()
            lineage_key = self.tracks_viewer.tracks.track_annotator.lineage_key
            if lineage_key in self.tracks_viewer.tracks.features:
                lineage_id = self.tracks_viewer.tracks.get_node_attr(
                    node_id, lineage_key
                )
                lineage = self.tracks_viewer.tracks.track_annotator.lineage_id_to_nodes[
                    lineage_id
                ]
            else:
                # fallback in case the lineage feature is not activated
                lineage = extract_lineage_tree(self.tracks_viewer.tracks.graph, node_id)

            nodes_to_process.extend(lineage)
            selected.difference_update(lineage)
        self._add_nodes(nodes_to_process) if add else self._remove_nodes(
            nodes_to_process
        )

    def _remove_nodes(self, nodes: list[Any]) -> None:
        """Remove selected nodes from the selected collection"""

        if self.selected_collection is not None:
            # remove from the collection
            self.selected_collection.collection = {
                item
                for item in self.selected_collection.collection
                if item not in nodes
            }

            feature_key = self.selected_collection.name.text()
            UserUpdateNodesAttrs(
                tracks=self.tracks_viewer.tracks,
                nodes=[int(n) for n in nodes],
                attrs={feature_key: [False] * len(nodes)},
            )

            self.group_changed.emit()

    def _remove_selection(self) -> None:
        """Remove individual nodes from the selected collection"""

        self._remove_nodes(self.tracks_viewer.selected_nodes)

    def _add_group(self, name: str | None = None, select: bool = True) -> None:
        """Create a new custom group

        Args:
            name (str, optional): the name to give to this group. If not provided, the
                name in the self.group_name QLineEdit widget is used.
            select (bool, optional): whether or not to make this group the selected item
                in the QListWidget. Defaults to True.
        """

        if name is None:
            name = self.group_name.text()

        names = [
            self.collection_list.itemWidget(self.collection_list.item(i)).name.text()
            for i in range(self.collection_list.count())
        ]
        while name in names:
            name = name + "_1"
        item = QListWidgetItem(self.collection_list)
        group_row = CollectionButton(name)
        self.collection_list.setItemWidget(item, group_row)
        item.setSizeHint(group_row.minimumSizeHint())
        self.collection_list.addItem(item)
        group_row.delete.clicked.connect(partial(self._remove_group, item))
        group_row.export.clicked.connect(partial(self._show_export_dialog, item))
        group_row.select_nodes_in_group_btn.clicked.connect(
            partial(self._select_nodes, item)
        )

        if select:
            self.collection_list.setCurrentRow(len(self.collection_list) - 1)

        # Register group as new feature on Tracks
        if name not in self.tracks_viewer.tracks.features:
            new_feature: Feature = {
                "feature_type": "node",  # This is a node feature
                "value_type": "bool",  # The feature is a boolean
                "num_values": 1,  # Each node has one value for this feature
                "display_name": name,
                "default_value": False,  # Default value for nodes without this feature
            }

            # Use add_feature to update both the FeatureDict and the graph schema
            self.tracks_viewer.tracks.add_feature(name, new_feature)

    def _remove_group(self, item: QListWidgetItem) -> None:
        """Remove a collection object from the list. You must pass the list item that
        represents the collection, not the collection object itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the CollectionButton that represents a set of node_ids.
        """

        row = self.collection_list.indexFromItem(item).row()
        group_name = self.collection_list.itemWidget(item).name.text()
        self.collection_list.takeItem(row)

        # remove from the features dict and graph schema
        if group_name in self.tracks_viewer.tracks.features:
            del self.tracks_viewer.tracks.features[group_name]
        if group_name in self.tracks_viewer.tracks.graph.node_attr_keys():
            self.tracks_viewer.tracks.graph.remove_node_attr_key(group_name)

        # If we removed the last group while in 'group' mode, fall back to 'all'
        # so the viewer doesn't stay stuck on an empty group view.
        if self.collection_list.count() == 0 and self.tracks_viewer.mode == "group":
            self.tracks_viewer.set_display_mode("all")
            self.tracks_viewer.mode_updated.emit()

    def _show_export_dialog(self, item: QListWidgetItem) -> None:
        """Prompt user to choose export format (csv or geff), then export the nodes
        belonging to this group. You must pass the list item that represents the group.

        Args:
            item (QListWidgetItem): The list item containing the CollectionButton that
                represents a group of nodes.
        """

        group_name = self.collection_list.itemWidget(item).name.text()
        nodes_to_keep = (
            self.collection_list.itemWidget(item).collection
            - self.tracks_viewer.selected_nodes.deleted_items
        )

        if len(nodes_to_keep) == 0:
            warn("No nodes in this group to export!", stacklevel=2)
            return

        # Keep nodes that belong to the selected group and export
        ExportDialog.show_export_dialog(
            self,
            tracks=self.tracks_viewer.tracks,
            name=group_name,
            nodes_to_keep=nodes_to_keep,
            colormap=self.tracks_viewer.colormap,
        )

    def _select_nodes(self, item: QListWidgetItem) -> None:
        """Select all nodes in the collection"""

        nodes = list(self.collection_list.itemWidget(item).collection)
        nodes = [
            n for n in nodes if n not in self.tracks_viewer.selected_nodes.deleted_items
        ]
        self.tracks_viewer.selected_nodes.add_list(nodes, append=False)
