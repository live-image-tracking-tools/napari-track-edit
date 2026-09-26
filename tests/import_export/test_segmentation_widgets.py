"""Tests for segmentation_widgets - widgets for selecting segmentation data."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import zarr
from geff_spec import GeffMetadata

from napari_track_edit.import_export.menus.segmentation_widgets import (
    CSVSegmentationWidget,
    ExternalSegmentationWidget,
    FileFolderDialog,
    GeffSegmentationWidget,
)


def _minimal_geff_attrs(**overrides) -> dict:
    """Build a minimal but schema-valid 'geff' zarr attrs dict for test fixtures.

    GeffMetadata.read validates the full geff_spec schema, so fixtures need more
    than just the fields under test (e.g. related_objects) to be readable.
    """
    metadata = GeffMetadata(
        directed=True, node_props_metadata={}, edge_props_metadata={}, **overrides
    )
    return metadata.model_dump(mode="json", exclude_none=True)


class TestExternalSegmentationWidget:
    """Test ExternalSegmentationWidget initialization and methods."""

    def test_initialization(self, qtbot):
        """Test widget creates all components."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        assert widget.image_path_line is not None
        assert widget.image_browse_button is not None
        assert widget.seg_label is not None
        assert widget.valid is False

    def test_browse_segmentation_opens_dialog(self, qtbot):
        """Test browse button opens FileFolderDialog."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        with patch(
            "napari_track_edit.import_export.menus.segmentation_widgets.FileFolderDialog"
        ) as mock_dialog:
            mock_instance = MagicMock()
            mock_dialog.return_value = mock_instance

            widget.image_browse_button.click()

            # Verify dialog was created and opened
            mock_dialog.assert_called_once()
            mock_instance.open.assert_called_once()

    def test_verify_path_with_tiff_file(self, qtbot, tmp_path):
        """Test _verify_path validates tiff files correctly."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        # Create a temporary tiff file
        tiff_file = tmp_path / "test.tif"
        tiff_file.touch()

        widget.image_path_line.setText(str(tiff_file))
        widget._verify_path()

        assert widget.valid is True
        assert widget.seg_label.styleSheet() == ""

    def test_verify_path_with_zarr_folder(self, qtbot, tmp_path):
        """Test _verify_path validates zarr folders correctly."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        # Create a zarr folder
        zarr_path = tmp_path / "test.zarr"
        zarr_path.mkdir()

        widget.image_path_line.setText(str(zarr_path))
        widget._verify_path()

        assert widget.valid is True
        assert widget.seg_label.styleSheet() == ""

    def test_verify_path_with_folder_containing_tiffs(self, qtbot, tmp_path):
        """Test _verify_path validates folders with tiff images."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        # Create folder with tiff files
        folder = tmp_path / "images"
        folder.mkdir()
        (folder / "img1.tif").touch()
        (folder / "img2.tiff").touch()

        widget.image_path_line.setText(str(folder))
        widget._verify_path()

        assert widget.valid is True
        assert widget.seg_label.styleSheet() == ""

    def test_verify_path_with_invalid_path(self, qtbot):
        """Test _verify_path marks invalid paths."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        widget.image_path_line.setText("/nonexistent/path.tif")
        widget._verify_path()

        assert widget.valid is False
        assert "red" in widget.seg_label.styleSheet()

    def test_verify_path_with_invalid_file_type(self, qtbot, tmp_path):
        """Test _verify_path rejects invalid file types."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        # Create a non-tiff file
        invalid_file = tmp_path / "test.txt"
        invalid_file.touch()

        widget.image_path_line.setText(str(invalid_file))
        widget._verify_path()

        assert widget.valid is False
        assert "red" in widget.seg_label.styleSheet()

    def test_verify_path_emits_signal(self, qtbot):
        """Test _verify_path emits seg_path_updated signal."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        with qtbot.waitSignal(widget.seg_path_updated, timeout=1000):
            widget._verify_path()

    def test_get_segmentation_path_with_valid_path(self, qtbot, tmp_path):
        """Test get_segmentation_path returns valid path."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        tiff_file = tmp_path / "test.tif"
        tiff_file.touch()

        widget.image_path_line.setText(str(tiff_file))

        result = widget.get_segmentation_path()
        assert result == Path(tiff_file)

    def test_get_segmentation_path_with_invalid_path(self, qtbot):
        """Test get_segmentation_path returns None for invalid path."""
        widget = ExternalSegmentationWidget()
        qtbot.addWidget(widget)

        widget.image_path_line.setText("/nonexistent/path.tif")

        result = widget.get_segmentation_path()
        assert result is None


class TestFileFolderDialog:
    """Test FileFolderDialog for selecting files or folders."""

    def test_initialization(self, qtbot):
        """Test dialog creates all components."""
        dialog = FileFolderDialog()
        qtbot.addWidget(dialog)

        assert dialog.path_line_edit is not None
        assert dialog.file_button is not None
        assert dialog.folder_button is not None
        assert dialog.ok_button is not None

    def test_select_file_sets_path(self, qtbot, tmp_path):
        """Test _select_file sets path when file selected."""
        dialog = FileFolderDialog()
        qtbot.addWidget(dialog)

        test_file = tmp_path / "test.tif"
        test_file.touch()

        # Mock QFileDialog.getOpenFileName to return our test file
        with patch(
            "napari_track_edit.import_export.menus.segmentation_widgets.QFileDialog.getOpenFileName",
            return_value=(str(test_file), ""),
        ):
            dialog.file_button.click()
            assert dialog.path_line_edit.text() == str(test_file)

    def test_select_folder_sets_path(self, qtbot, tmp_path):
        """Test _select_folder sets path when folder selected."""
        dialog = FileFolderDialog()
        qtbot.addWidget(dialog)

        test_folder = tmp_path / "images"
        test_folder.mkdir()

        # Mock QFileDialog.getExistingDirectory to return our test folder
        with patch(
            "napari_track_edit.import_export.menus.segmentation_widgets.QFileDialog.getExistingDirectory",
            return_value=str(test_folder),
        ):
            dialog.folder_button.click()
            assert dialog.path_line_edit.text() == str(test_folder)

    def test_get_selected_path_with_valid_path(self, qtbot, tmp_path):
        """Test get_selected_path returns path when valid."""
        dialog = FileFolderDialog()
        qtbot.addWidget(dialog)

        test_file = tmp_path / "test.tif"
        test_file.touch()
        dialog.path_line_edit.setText(str(test_file))

        result = dialog.get_selected_path()
        assert result == str(test_file)

    def test_get_selected_path_with_invalid_path(self, qtbot):
        """Test get_selected_path returns None for invalid path."""
        dialog = FileFolderDialog()
        qtbot.addWidget(dialog)

        dialog.path_line_edit.setText("/nonexistent/path.tif")

        result = dialog.get_selected_path()
        assert result is None

    def test_get_selected_path_with_empty_path(self, qtbot):
        """Test get_selected_path returns None for empty path."""
        dialog = FileFolderDialog()
        qtbot.addWidget(dialog)

        dialog.path_line_edit.setText("")

        result = dialog.get_selected_path()
        assert result is None


class TestCSVSegmentationWidget:
    """Test CSVSegmentationWidget for CSV import."""

    def test_initialization(self, qtbot):
        """Test widget creates all components."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        assert widget.button_group is not None
        assert widget.none_radio is not None
        assert widget.external_segmentation_radio is not None
        assert widget.segmentation_widget is not None
        assert widget.none_radio.isChecked()
        assert not widget.segmentation_widget.isVisible()

    def test_toggle_segmentation_shows_widget(self, qtbot):
        """Test clicking radio shows segmentation widget."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)
        widget.show()

        # Check external segmentation radio
        widget.external_segmentation_radio.setChecked(True)
        qtbot.wait(100)  # Wait for visibility update

        assert widget.segmentation_widget.isVisible()

    def test_toggle_segmentation_hides_widget(self, qtbot):
        """Test unchecking radio hides segmentation widget."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        # Check then uncheck
        widget.external_segmentation_radio.setChecked(True)
        widget.none_radio.setChecked(True)

        assert not widget.segmentation_widget.isVisible()

    def test_include_seg_returns_false_when_none_selected(self, qtbot):
        """Test include_seg returns False when None is selected."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        assert widget.include_seg() is False

    def test_include_seg_returns_true_when_external_selected(self, qtbot):
        """Test include_seg returns True when external seg is selected."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        widget.external_segmentation_radio.setChecked(True)

        assert widget.include_seg() is True

    def test_get_segmentation_path_returns_none_when_none_selected(self, qtbot):
        """Test get_segmentation_path returns None when None is selected."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        result = widget.get_segmentation_path()
        assert result is None

    def test_get_segmentation_path_returns_path_when_external_selected(
        self, qtbot, tmp_path
    ):
        """Test get_segmentation_path returns path when external seg is selected."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        # Set up valid path
        test_file = tmp_path / "test.tif"
        test_file.touch()
        widget.segmentation_widget.image_path_line.setText(str(test_file))

        # Select external segmentation
        widget.external_segmentation_radio.setChecked(True)

        result = widget.get_segmentation_path()
        assert result == Path(test_file)

    def test_load_segmentation_with_valid_path(self, qtbot, tmp_path):
        """Test load_segmentation loads image array."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        # Create test tiff file
        test_file = tmp_path / "test.tif"
        test_file.touch()  # Create the file
        test_array = np.zeros((2, 10, 10), dtype=np.uint8)

        with patch(
            "napari_track_edit.import_export.menus.segmentation_widgets.magic_imread"
        ) as mock_imread:
            mock_imread.return_value = test_array

            # Set up widget
            widget.segmentation_widget.image_path_line.setText(str(test_file))
            widget.segmentation_widget.valid = True
            widget.external_segmentation_radio.setChecked(True)

            result = widget.load_segmentation()

            mock_imread.assert_called_once_with(test_file, use_dask=False)
            assert np.array_equal(result, test_array)

    def test_load_segmentation_with_invalid_path(self, qtbot):
        """Test load_segmentation shows error for invalid path."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        widget.external_segmentation_radio.setChecked(True)
        widget.segmentation_widget.valid = False

        with patch(
            "napari_track_edit.import_export.menus.segmentation_widgets.QMessageBox.critical"
        ) as mock_msgbox:
            result = widget.load_segmentation()

            mock_msgbox.assert_called_once()
            assert result is None

    def test_seg_updated_signal_emitted(self, qtbot):
        """Test seg_updated signal is emitted on toggle."""
        widget = CSVSegmentationWidget()
        qtbot.addWidget(widget)

        with qtbot.waitSignal(widget.seg_updated, timeout=1000):
            widget.external_segmentation_radio.setChecked(True)


class TestGeffSegmentationWidget:
    """Test GeffSegmentationWidget for GEFF import."""

    def test_initialization_without_root(self, qtbot):
        """Test widget creates all components without root."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        assert widget.button_group is not None
        assert widget.none_radio is not None
        assert widget.external_segmentation_radio is not None
        assert widget.segmentation_widget is not None
        assert widget.root is None
        assert not widget.isVisible()

    def test_initialization_with_root(self, qtbot, tmp_path):
        """Test widget creates all components with root."""
        # Create zarr group
        zarr_path = tmp_path / "test.zarr"
        root = zarr.open_group(str(zarr_path), mode="w")

        widget = GeffSegmentationWidget(root=root)
        qtbot.addWidget(widget)

        assert widget.root is root

    def test_update_root_with_none_hides_widget(self, qtbot):
        """Test update_root with None hides widget."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        widget.update_root(None)

        assert not widget.isVisible()

    def test_update_root_with_root_shows_widget(self, qtbot, tmp_path):
        """Test update_root with root shows widget."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        # Create zarr group
        zarr_path = tmp_path / "test.zarr"
        root = zarr.open_group(str(zarr_path), mode="w")
        root.attrs["geff"] = _minimal_geff_attrs()

        widget.update_root(root)

        assert widget.isVisible()

    def test_update_root_with_related_objects_creates_radios(self, qtbot, tmp_path):
        """Test update_root creates radio buttons for related objects."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        # Create zarr group with related objects metadata
        zarr_path = tmp_path / "test.zarr"
        root = zarr.open_group(str(zarr_path), mode="w")
        root.attrs["geff"] = _minimal_geff_attrs(
            related_objects=[
                {"type": "labels", "path": "segmentation"},
                {"type": "labels", "path": "masks"},
            ]
        )

        widget.update_root(root)

        # Verify radio buttons were created
        assert len(widget.related_object_radio_buttons) == 2
        assert "segmentation" in widget.related_object_radio_buttons
        assert "masks" in widget.related_object_radio_buttons

    def test_update_root_clears_previous_radios(self, qtbot, tmp_path):
        """Test update_root clears previous radio buttons."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        # First update with related objects
        zarr_path1 = tmp_path / "test1.zarr"
        root1 = zarr.open_group(str(zarr_path1), mode="w")
        root1.attrs["geff"] = _minimal_geff_attrs(
            related_objects=[{"type": "labels", "path": "seg1"}]
        )
        widget.update_root(root1)
        assert len(widget.related_object_radio_buttons) == 1

        # Second update with different related objects
        zarr_path2 = tmp_path / "test2.zarr"
        root2 = zarr.open_group(str(zarr_path2), mode="w")
        root2.attrs["geff"] = _minimal_geff_attrs(
            related_objects=[{"type": "labels", "path": "seg2"}]
        )
        widget.update_root(root2)

        # Should have new radio, not old one
        assert len(widget.related_object_radio_buttons) == 1
        assert "seg2" in widget.related_object_radio_buttons
        assert "seg1" not in widget.related_object_radio_buttons

    def test_toggle_segmentation_shows_widget(self, qtbot):
        """Test external segmentation radio shows widget."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)
        widget.show()

        widget.external_segmentation_radio.setChecked(True)
        qtbot.wait(100)  # Wait for visibility update

        assert widget.segmentation_widget.isVisible()

    def test_toggle_segmentation_hides_widget(self, qtbot):
        """Test unchecking external radio hides widget."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        widget.external_segmentation_radio.setChecked(True)
        widget.none_radio.setChecked(True)

        assert not widget.segmentation_widget.isVisible()

    def test_include_seg_returns_false_when_none_selected(self, qtbot):
        """Test include_seg returns False when None is selected."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        assert widget.include_seg() is False

    def test_include_seg_returns_true_when_external_selected(self, qtbot):
        """Test include_seg returns True when external seg is selected."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        widget.external_segmentation_radio.setChecked(True)

        assert widget.include_seg() is True

    def test_include_seg_returns_true_when_related_object_selected(
        self, qtbot, tmp_path
    ):
        """Test include_seg returns True when related object is selected."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        # Create zarr group with related object
        zarr_path = tmp_path / "test.zarr"
        root = zarr.open_group(str(zarr_path), mode="w")
        root.attrs["geff"] = _minimal_geff_attrs(
            related_objects=[{"type": "labels", "path": "segmentation"}]
        )
        widget.update_root(root)

        # Select the related object radio
        widget.related_object_radio_buttons["segmentation"].setChecked(True)

        assert widget.include_seg() is True

    def test_get_segmentation_path_returns_none_when_none_selected(self, qtbot):
        """Test get_segmentation_path returns None when None is selected."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        result = widget.get_segmentation_path()
        assert result is None

    def test_get_segmentation_path_returns_path_for_external(self, qtbot, tmp_path):
        """Test get_segmentation_path returns path for external seg."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        test_file = tmp_path / "test.tif"
        test_file.touch()
        widget.segmentation_widget.image_path_line.setText(str(test_file))
        widget.external_segmentation_radio.setChecked(True)

        result = widget.get_segmentation_path()
        assert result == Path(test_file)

    def test_get_segmentation_path_returns_path_for_related_object(
        self, qtbot, tmp_path
    ):
        """Test get_segmentation_path returns path for related object."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        # Create zarr group with related object
        zarr_path = tmp_path / "test.zarr"
        # First create root group
        root = zarr.open_group(str(zarr_path / "tracks"), mode="w")
        root.attrs["geff"] = _minimal_geff_attrs(
            related_objects=[{"type": "labels", "path": "segmentation"}]
        )

        # Create the expected segmentation path
        seg_path = zarr_path / "tracks" / "segmentation"
        seg_path.mkdir(parents=True, exist_ok=True)

        widget.update_root(root)
        widget.related_object_radio_buttons["segmentation"].setChecked(True)

        result = widget.get_segmentation_path()
        assert result.exists()
        assert result.name == "segmentation"

    def test_seg_updated_signal_emitted(self, qtbot):
        """Test seg_updated signal is emitted on toggle."""
        widget = GeffSegmentationWidget()
        qtbot.addWidget(widget)

        with qtbot.waitSignal(widget.seg_updated, timeout=1000):
            widget.external_segmentation_radio.setChecked(True)
