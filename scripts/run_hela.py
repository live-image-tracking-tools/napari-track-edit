import logging

import napari
import zarr
from napari.utils.theme import _themes

from napari_track_edit.application_menus import StartupWidget
from napari_track_edit.example_data import user_data_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s %(message)s",
)
logging.getLogger("napari_track_edit").setLevel(logging.DEBUG)

_themes["dark"].font_size = "18pt"


# Load Zarr datasets

ds_name = "Fluo-N2DL-HeLa"
zarr_directory = user_data_dir() / f"{ds_name}.zarr"
zarr_group = zarr.open_group(zarr_directory, mode="r")

# Initialize Napari viewer
viewer = napari.Viewer()

# Add image and label layers to the viewer
viewer.add_image(zarr_group["01"][:], name="01 Raw")
viewer.add_labels(zarr_group["01_ST"][:], name="01 ST")

# Add your custom widget
StartupWidget(viewer)

# Start the Napari GUI event loop
napari.run()
