import difflib

import pandas as pd
import zarr
from funtracks.annotators._regionprops_annotator import DEFAULT_POS_KEY
from funtracks.annotators._track_annotator import (
    DEFAULT_LINEAGE_KEY,
    DEFAULT_TRACKLET_KEY,
)
from funtracks.import_export import has_embedded_segmentation
from funtracks.import_export._utils import get_default_key_to_feature_mapping
from psygnal import Signal
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.import_export.menus.geff_import_utils import (
    clear_layout,
    geff_group_path,
)


def get_attr_dtype_zarr(root: zarr.Group, attr: str) -> str:
    """
    Determine the data type for a property stored under
    root['nodes']['props'][attr].

    Returns:
        One of: 'bool', 'int', 'float', 'str', or 'object'
    """
    node = root["nodes"]["props"][attr]

    # Try to find a child array and inspect its dtype
    for name in getattr(node, "keys", list)():
        child = node[name]
        if hasattr(child, "dtype"):
            kind = child.dtype.kind
            # Convert numpy kind to readable type
            if kind == "b":
                return "bool"
            elif kind in ("i", "u"):
                return "int"
            elif kind == "f":
                return "float"
            elif kind in ("S", "U"):
                return "str"
            else:
                return "object"


def get_attr_dtype_pandas(series: pd.Series) -> str:
    """Extract the data type of a pandas series as one of 'bool', 'int', 'float', 'str',
    or 'object'
    """

    if pd.api.types.is_integer_dtype(series):
        return "int"
    elif pd.api.types.is_float_dtype(series):
        return "float"
    elif pd.api.types.is_bool_dtype(series):
        return "bool"
    else:
        return str(series.dtype)


class StandardFieldMapWidget(QWidget):
    """QWidget to map motile run attributes to node properties in csv or geff."""

    props_updated = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.seg = False
        self.seg_for_features = False
        self.incl_z = True
        self.has_duplicates = False
        self.node_attrs: list[str] = []
        self.metadata = None
        self.mapping_labels = {}
        self.mapping_widgets = {}

        # Group box for property field mapping
        box = QGroupBox("Map properties")
        box_layout = QHBoxLayout()
        box.setLayout(box_layout)
        main_layout = QVBoxLayout()

        main_layout.addWidget(box)
        self.setLayout(main_layout)

        # Graph data mapping Layout
        mapping_box = QGroupBox("Graph data")
        mapping_box.setToolTip(
            "<html><body><p style='white-space:pre-wrap; width: 300px;'>"
            "Map spatiotemporal attributes and optional track and lineage attributes to "
            "node properties."
        )
        self.mapping_layout = QFormLayout()
        mapping_box.setLayout(self.mapping_layout)
        box_layout.addWidget(mapping_box, alignment=Qt.AlignTop)

        # Optional features
        optional_box = QGroupBox("Optional features")
        optional_box.setToolTip(
            "<html><body><p style='white-space:pre-wrap; width: 300px;'>"
            "Optionally select additional features to be imported. If the 'Recompute' "
            "checkbox is checked, the feature will be recomputed, otherwise it will "
            "directly be imported from the data."
        )

        self.optional_mapping_layout = QGridLayout()
        optional_box.setLayout(self.optional_mapping_layout)
        box_layout.addWidget(optional_box, alignment=Qt.AlignTop)
        self.optional_features = {}

        self.setVisible(False)

    def extract_csv_property_fields(
        self, df: pd.DataFrame, seg: bool, incl_z: bool
    ) -> None:
        """Update the mapping widget with the provided root group and segmentation flag."""

        self.seg = seg
        self.seg_for_features = seg
        self.incl_z = incl_z

        self.df = df
        self.setVisible(True)
        self.node_attrs = list(self.df.columns)

        # Retrieve attribute types
        self.attr_types = {
            attr: get_attr_dtype_pandas(self.df[attr]) for attr in self.node_attrs
        }
        self.props_left = []
        self.standard_fields = [
            "id",
            "parent_id",
            "time",
            "y",
            "x",
            DEFAULT_TRACKLET_KEY,
            DEFAULT_LINEAGE_KEY,
            "seg_id",
        ]

        if self.incl_z:
            self.standard_fields.insert(3, "z")

        self.update_mapping(seg)

    def extract_geff_property_fields(
        self,
        root: zarr.Group,
        seg: bool,
        incl_z: bool,
        seg_for_features: bool | None = None,
    ) -> None:
        """Update the mapping widget with the provided root group and segmentation flag."""

        self.seg = seg
        self.seg_for_features = seg if seg_for_features is None else seg_for_features
        self.incl_z = incl_z

        self.setVisible(False)
        self.node_attrs = list(root["nodes"]["props"].group_keys())
        self.metadata = dict(root.attrs.get("geff", {}))

        # Exclude mask/bbox from optional features when they are embedded segmentation
        # attributes that will be imported automatically (shape metadata present).
        if has_embedded_segmentation(geff_group_path(root)):
            self.node_attrs = [a for a in self.node_attrs if a not in ("mask", "bbox")]

        # Retrieve attribute types from the zarr group
        self.attr_types = {
            attr: get_attr_dtype_zarr(root, attr) for attr in self.node_attrs
        }
        self.props_left = []
        self.standard_fields = [
            "time",
            "y",
            "x",
            "seg_id",
            DEFAULT_TRACKLET_KEY,
            DEFAULT_LINEAGE_KEY,
        ]

        axes = self.metadata.get("axes", None)
        if axes is not None:
            axes_types = [ax.get("type") for ax in axes if ax.get("type") == "space"]
            if len(axes_types) == 3:
                self.standard_fields.insert(1, "z")
        else:
            # no axes provided, use incl_z
            if self.incl_z:
                self.standard_fields.insert(1, "z")

        self.update_mapping(seg)
        self.setVisible(True)

    def _update_props_left(self) -> None:
        """Update the list of columns that have not been mapped yet

        Remove attributes from optional features if they are mapped in the mandatory
        mapping.
        """

        # Get all mapped values from the mandatory mapping
        mapped_mandatory = {
            combo.currentText()
            for combo in self.mapping_widgets.values()
            if combo.currentText() != "None"
        }

        # Remove from optional features if mapped in mandatory mapping
        self.props_left = [
            attr for attr in self.node_attrs if attr not in mapped_mandatory
        ]

        optional_features = list(self.optional_features.keys())
        for attribute in optional_features:
            if attribute not in self.props_left and attribute in mapped_mandatory:
                self._remove_optional_prop(attribute)

        for attribute in self.props_left:
            if attribute not in self.optional_features:
                self._add_optional_prop(attribute)

        # update duplicate check
        self._check_for_duplicates()

    def _get_initial_mapping(self) -> dict[str, str]:
        """Make an initial guess for mapping of geff columns to fields"""

        mapping: dict[str, str] = {}
        self.props_left = self.node_attrs.copy()

        # check if the axes information is in the metadata, if so, use it for initial
        # mapping
        if hasattr(self.metadata, "axes"):
            axes_names = [ax.name for ax in self.metadata.axes]
            for attribute in self.standard_fields:
                if attribute in axes_names:
                    mapping[attribute] = attribute
                    self.props_left.remove(attribute)

        # if fields could not be assigned via the metadata, try find exact matches for
        # standard fields
        for attribute in self.standard_fields:
            if attribute in mapping:
                continue
            if attribute in self.props_left:
                mapping[attribute] = attribute
                self.props_left.remove(attribute)

        # assign closest remaining column as best guess for remaining standard fields
        for attribute in self.standard_fields:
            if attribute in mapping:
                continue
            # seg_id is semantically specific: only match exactly to avoid stealing
            # track_id or other columns via fuzzy matching (e.g. 'seg_id' ~ 'track_id'
            # scores above the 0.4 cutoff and can prevent tracklet_id from being mapped).
            if attribute == "seg_id":
                mapping[attribute] = "None"
                continue
            if len(self.props_left) > 0:
                lower_map = {p.lower(): p for p in self.props_left}
                closest = difflib.get_close_matches(
                    attribute.lower(), lower_map.keys(), n=1, cutoff=0.4
                )
                if closest:
                    # map back to the original case
                    best_match = lower_map[closest[0]]
                    mapping[attribute] = best_match
                    self.props_left.remove(best_match)
                else:
                    mapping[attribute] = "None"
            else:
                mapping[attribute] = "None"

        return mapping

    def _add_optional_prop(self, attribute: str) -> None:
        """Add an attribute to the dictionary of optional features and create the
        associated widgets in the grid layout:
        - Checkbox to include/exclude the attribute
        - Combobox to select the feature option (regionprops feature, 'Group', or 'Custom')
        - Checkbox to indicate whether to recompute the feature (only for regionprops
        features)

        Args:
            attribute (str): The attribute name to add as an optional feature
        """

        # Use the QGridLayout row count to assign a new row. Indices will keep counting up
        # as widgets are removed and added back, but this does not leave holes, and
        # ensures that two widgets will never collide together on the same row
        row_idx = self.optional_mapping_layout.rowCount()

        # Prop checkbox
        attr_checkbox = QCheckBox(attribute)
        attr_checkbox.toggled.connect(self._check_for_duplicates)
        # Feature option combobox
        feature_option = QComboBox()
        # Numerical types & segmentation provided => list regionprops features
        if (
            self.attr_types.get(attribute)
            in {
                "int",
                "float",
            }
            and self.seg_for_features
        ):
            feature_option.addItems(self.feature_options)
        elif self.attr_types.get(attribute) in {"bool", "object", "0"}:
            # Boolean or unknown/object types => grouping option
            feature_option.addItem("Group")
        # Always have "Custom" as last option
        feature_option.addItem("Custom")
        feature_option.currentIndexChanged.connect(self._check_for_duplicates)

        # Recompute checkbox - initially disabled
        recompute_checkbox = QCheckBox()
        recompute_checkbox.setEnabled(False)

        # When the combobox selection changes, update recompute checkbox enable
        def make_on_change(checkbox, combo):
            def on_change(index):
                selected_feature = combo.currentText()
                # Recompute requires an external segmentation path (self.seg=True).
                # Embedded segmentation (seg_for_features=True, seg=False) does not
                # register a RegionPropsAnnotator, so recompute is not supported.
                if selected_feature in self.feature_options and self.seg:
                    checkbox.setEnabled(True)
                else:
                    checkbox.setEnabled(False)
                    checkbox.setChecked(False)

            return on_change

        feature_option.currentIndexChanged.connect(
            make_on_change(recompute_checkbox, feature_option)
        )

        # initialize recompute enabled state based on current selection
        make_on_change(recompute_checkbox, feature_option)(
            feature_option.currentIndex()
        )

        # Place widgets into the grid
        self.optional_mapping_layout.addWidget(attr_checkbox, row_idx, 0)
        self.optional_mapping_layout.addWidget(feature_option, row_idx, 1)
        self.optional_mapping_layout.addWidget(recompute_checkbox, row_idx, 2)

        # Save references for later retrieval
        self.optional_features[attribute] = {
            "attr_checkbox": attr_checkbox,
            "feature_option": feature_option,
            "recompute": recompute_checkbox,
        }

    def _remove_optional_prop(self, attribute: str) -> None:
        """Remove an attribute from the dictionary of optional features and remove the
        associated widgets from the 'extra features' layout."""

        self.optional_features[attribute]["attr_checkbox"].setParent(None)
        self.optional_features[attribute]["attr_checkbox"].deleteLater()
        self.optional_features[attribute]["feature_option"].setParent(None)
        self.optional_features[attribute]["feature_option"].deleteLater()
        self.optional_features[attribute]["recompute"].setParent(None)
        self.optional_features[attribute]["recompute"].deleteLater()

        del self.optional_features[attribute]

    def _check_for_duplicates(self) -> None:
        """Check if any regionprops property is assigned twice in optional_features
        (ignoring 'Group' and 'Custom').
        """

        selected_props = [
            widgets["feature_option"].currentText()
            for widgets in self.optional_features.values()
            if widgets["attr_checkbox"].isChecked()
        ]

        effective_props = [p for p in selected_props if p not in ("Group", "Custom")]
        seen = set()
        duplicates = {p for p in effective_props if p in seen or seen.add(p)}
        self.has_duplicates = bool(duplicates)
        for widgets in self.optional_features.values():
            checkbox = widgets["attr_checkbox"]
            selected = widgets["feature_option"].currentText()

            if checkbox.isChecked() and selected in duplicates:
                checkbox.setStyleSheet("background-color: red;")
            else:
                checkbox.setStyleSheet("")

        self.props_updated.emit()

    def _wrap_tooltip(self, text: str) -> str:
        """Wrap tooltip with fixed width."""

        if not text:
            return ""
        return (
            f"<html><body>"
            f"<p style='white-space:pre-wrap; width: 300px;'>"
            f"{text}"
            f"</p></body></html>"
        )

    def _get_tooltip(self, attribute: str) -> str:
        """Return the tooltip for the given attribute"""

        tooltips = {
            "id": "Unique identifier for the node.",
            "time": "The time point of the node. Must be an integer.",
            "z": "The world z-coordinate of the node.",
            "y": "The world y-coordinate of the node.",
            "x": "The world x-coordinate of the node.",
            "seg_id": (
                "The integer label value in the segmentation file. Choose None "
                "if the label values are identical to the node IDs. "
                "If the segmentation was exported with 'relabel to track_id', "
                "set this to the track_id column."
            ),
            DEFAULT_TRACKLET_KEY: (
                "(Optional) The tracklet id this node belongs to, defined as a "
                "single chain with at most one incoming and one outgoing edge."
            ),
            DEFAULT_LINEAGE_KEY: (
                "(Optional) Lineage id this node belongs to, defined as a weakly "
                "connected component in the graph."
            ),
        }

        return self._wrap_tooltip(tooltips.get(attribute, ""))

    def update_mapping(self, seg: bool = False) -> None:
        """Map graph spatiotemporal data and optionally the track and lineage attributes.

        Args:
            seg (bool): whether a segmentation is associated with this data
        """

        self.setVisible(False)
        self.mapping_labels = {}
        self.mapping_widgets = {}
        clear_layout(self.mapping_layout)  # clear layout first
        initial_mapping = self._get_initial_mapping()
        for attribute in self.standard_fields:
            combo = QComboBox()
            combo.addItems(self.node_attrs + ["None"])  # also add None
            combo.setCurrentText(initial_mapping.get(attribute, "None"))
            combo.currentIndexChanged.connect(self._update_props_left)
            label = QLabel(attribute)
            label.setToolTip(self._get_tooltip(attribute))
            self.mapping_widgets[attribute] = combo
            self.mapping_labels[attribute] = label
            self.mapping_layout.addRow(label, combo)
            if attribute == "seg_id" and not seg:
                combo.setVisible(False)
                label.setVisible(False)

        # Optional extra features: build display_name -> default_key mapping
        ndim = 4 if "z" in self.standard_fields else 3
        available = get_default_key_to_feature_mapping(ndim=ndim, display_name=False)
        standard_keys = set(self.standard_fields) | {DEFAULT_POS_KEY}
        # Lowercase for case-insensitive collision detection, since downstream
        # code (e.g. tracks_from_df) lowercases feature keys before use.
        self.reserved_keys = {k.lower() for k in available.keys() | standard_keys}
        self.feature_options = []
        self.display_name_to_default_key: dict[str, str] = {}
        for default_key, feature in available.items():
            if feature["feature_type"] != "node" or default_key in standard_keys:
                continue
            display_name = feature.get("display_name", default_key)
            self.feature_options.append(display_name)
            self.display_name_to_default_key[display_name] = default_key

        # Clear existing optional layout and widgets
        clear_layout(self.optional_mapping_layout)
        self.optional_features = {}

        # Add header
        header_prop = QLabel("Name")
        header_assign = QLabel("Assign as Feature")
        header_recompute = QLabel("Recompute")
        header_prop.setAlignment(Qt.AlignLeft)
        header_assign.setAlignment(Qt.AlignLeft)
        header_recompute.setAlignment(Qt.AlignLeft)
        self.optional_mapping_layout.addWidget(header_prop, 0, 0)
        self.optional_mapping_layout.addWidget(header_assign, 0, 1)
        self.optional_mapping_layout.addWidget(header_recompute, 0, 2)
        self._update_props_left()

        self.setVisible(True)
        self.setMinimumHeight(350)

    def get_name_map(self) -> dict[str, str]:
        """Return a mapping from standard field name to source property name.

        Includes standard fields (time, x, y, etc.), Custom/Group features,
        and non-recompute regionprops features selected in optional features.
        """
        name_map = {
            attribute: combo.currentText()
            for attribute, combo in self.mapping_widgets.items()
        }

        for attr, widgets in self.optional_features.items():
            if not widgets["attr_checkbox"].isChecked():
                continue
            selected = widgets["feature_option"].currentText()
            if selected in ("Custom", "Group"):
                key = f"custom_{attr}" if attr.lower() in self.reserved_keys else attr
                name_map[key] = attr
            elif not widgets["recompute"].isChecked():
                # Regionprops feature loaded from data (not recomputed)
                default_key = self.display_name_to_default_key[selected]
                name_map[default_key] = attr

        return name_map

    def get_recompute_keys(self) -> list[str]:
        """Get feature keys that should be recomputed from segmentation.

        Returns a list of default feature keys for which the user checked
        the 'Recompute' checkbox.
        """
        recompute_keys = []
        for _attr, widgets in self.optional_features.items():
            if widgets["attr_checkbox"].isChecked():
                selected = widgets["feature_option"].currentText()
                if selected in ("Custom", "Group"):
                    continue
                if widgets["recompute"].isChecked():
                    default_key = self.display_name_to_default_key[selected]
                    recompute_keys.append(default_key)
        return recompute_keys
