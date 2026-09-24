import logging
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
from urllib.request import urlretrieve

import gdown
import numpy as np
import tifffile
import zarr
from appdirs import AppDirs
from funtracks.utils import setup_zarr_array, setup_zarr_group
from napari.types import LayerData
from skimage.measure import regionprops

logger = logging.getLogger(__name__)

# Region of Fluo-N2DL-HeLa used for the crop: (y, x) slices
HELA_CROP = (slice(90, 300), slice(700, 1040))


def Mouse_Embryo_Membrane() -> list[LayerData]:
    """Loads the Mouse Embryo Membrane raw data and segmentation data from
    the appdir "user data dir". Will download it from the Zenodo DOI if not present.

    Returns:
        list[LayerData]: An image layer of raw data and a segmentation labels
            layer
    """
    ds_name = "Mouse_Embryo_Membrane"
    appdir = AppDirs("motile-tracker")
    data_dir = Path(appdir.user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_name = "imaging.tif"
    label_name = "segmentation.tif"
    return read_zenodo_dataset(ds_name, raw_name, label_name, data_dir)


def Fluo_N2DL_HeLa() -> list[LayerData]:
    """Loads the Fluo-N2DL-HeLa 01 training raw data and silver truth from
    the appdir "user data dir". Will download it from the CTC and convert it to
    zarr if it is not present already.

    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    ds_name = "Fluo-N2DL-HeLa"
    appdir = AppDirs("motile-tracker")
    data_dir = Path(appdir.user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return read_ctc_dataset(ds_name, data_dir)


def Fluo_N2DL_HeLa_crop() -> list[LayerData]:
    """Loads the Fluo-N2DL-HeLa 01 training raw data and silver truth from
    the appdir "user data dir". Will download it from the CTC and convert it to
    zarr if it is not present already.

    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    ds_name = "Fluo-N2DL-HeLa"
    appdir = AppDirs("motile-tracker")
    data_dir = Path(appdir.user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return read_ctc_dataset(ds_name, data_dir, crop_region=True)


def read_zenodo_dataset(
    ds_name: str, raw_name: str, label_name: str, data_dir: Path
) -> list[LayerData]:
    """Read a zenodo dataset (assumes pre-downloaded)
    and returns a list of layer data for making napari layers

    Args:
        ds_name (str): name to give to the dataset
        raw_name (str): name of the file that points to the intensity data
        label_name (str): name of the file that points to the segmentation data
        data_dir (Path): Path to the directory containing the images

    Returns:
        list[LayerData]: An image layer of raw data and a segmentation labels
            layer
    """
    ds_zarr = data_dir / (ds_name + ".zarr")
    if not ds_zarr.exists():
        logger.info("Downloading %s", ds_name)
        download_zenodo_dataset(ds_name, raw_name, label_name, data_dir)

    raw_data = zarr.open(store=ds_zarr, path="01_membrane", dimension_separator="/")[:]
    raw_layer_data = (raw_data, {"name": "01_membrane"}, "image")
    seg_data = zarr.open(ds_zarr, path="01_labels", dimension_separator="/")[:]
    seg_layer_data = (seg_data, {"name": "01_labels"}, "labels")
    return [raw_layer_data, seg_layer_data]


def read_ctc_dataset(
    ds_name: str, data_dir: Path, crop_region=False
) -> list[LayerData]:
    """Read a CTC dataset from a zarr (assumes pre-downloaded and converted)
    and returns a list of layer data for making napari layers

    Args:
        ds_name (str): Dataset name
        data_dir (Path): Path to the directory containing the zarr

    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    ds_zarr = data_dir / (ds_name + ".zarr")
    if not ds_zarr.exists():
        logger.info("Downloading %s", ds_name)
        download_ctc_dataset(ds_name, data_dir)
    zarr_store = zarr.open(store=ds_zarr, mode="a")  # Open in append mode ('a')
    raw_data = zarr_store["01"]
    seg_data = zarr_store["01_ST"]
    if crop_region:
        raw_data = raw_data[(slice(None), *HELA_CROP)]
        seg_data = seg_data[(slice(None), *HELA_CROP)]
    else:
        raw_data = raw_data[:]
        seg_data = seg_data[:]
    raw_layer_data = (raw_data, {"name": "01_raw"}, "image")
    seg_layer_data = (seg_data, {"name": "01_ST"}, "labels")

    # Check if 'points' dataset exists in the zarr file
    points_name = "points_crop" if crop_region else "points"
    if points_name not in zarr_store:
        logger.info("extracting centroids...")
        centroids_list = []
        for t in range(seg_data.shape[0]):  # Iterate over time frames
            frame_seg = seg_data[t]
            props = regionprops(frame_seg)
            centroids = np.array([prop.centroid for prop in props])
            time_stamped_centroids = np.column_stack(
                [np.full(centroids.shape[0], t), centroids]
            )
            centroids_list.append(time_stamped_centroids)
        all_centroids = np.vstack(centroids_list)

        # Save the centroids inside the zarr file under the 'points' key
        points_array = setup_zarr_array(
            ds_zarr / points_name,
            shape=all_centroids.shape,
            dtype=all_centroids.dtype,
        )
        points_array[:] = all_centroids
        logger.info("Centroids extracted and saved")
    else:
        # If 'points' dataset exists, load it
        logger.info("points dataset found, loading...")
        all_centroids = zarr_store[points_name][:]

    # Prepare points layer data for napari
    points_layer_data = (all_centroids, {"name": "centroids"}, "points")

    return [raw_layer_data, seg_layer_data, points_layer_data]


def download_zenodo_dataset(
    ds_name: str, raw_name: str, label_name: str, data_dir: Path
) -> None:
    """Download a sample dataset from zenodo doi and unzip it, then delete the zip. Then convert the tiffs to
    zarrs for the first training set consisting of 3D membrane intensity images and segmentation.

    Args:
        ds_name (str): Name to give to the dataset
        raw_name (str): Name of the file that contains the intensity data
        label_name (str): Name of the file that contains the label data
        data_dir (Path): The directory in which to store the data.
    """
    ds_file_raw = data_dir / raw_name
    ds_file_labels = data_dir / label_name
    ds_zarr = data_dir / (ds_name + ".zarr")
    url_raw = "https://zenodo.org/records/13903500/files/imaging.zip"
    url_labels = "https://zenodo.org/records/13903500/files/segmentation.zip"
    zip_filename_raw = data_dir / "imaging.zip"
    zip_filename_labels = data_dir / "segmentation.zip"

    if not zip_filename_raw.is_file():
        urlretrieve(url_raw, filename=zip_filename_raw)
    if not zip_filename_labels.is_file():
        urlretrieve(url_labels, filename=zip_filename_labels)

    with zipfile.ZipFile(zip_filename_raw, "r") as zip_ref:
        zip_ref.extractall(data_dir)
    with zipfile.ZipFile(zip_filename_labels, "r") as zip_ref:
        zip_ref.extractall(data_dir)

    zip_filename_raw.unlink()
    zip_filename_labels.unlink()

    convert_4d_arr_to_zarr(ds_file_raw, ds_zarr, "01_membrane")
    convert_4d_arr_to_zarr(ds_file_labels, ds_zarr, "01_labels")


def download_ctc_dataset(ds_name: str, data_dir: Path) -> None:
    """Download a dataset from the Cell Tracking Challenge
    and unzip it, then delete the zip. Then convert the tiffs to
    zarrs for the first training set images and silver truth.

    Args:
        ds_name (str): Dataset name, according to the CTC
        data_dir (Path): The directory in which to store the data.
    """
    ds_dir = data_dir / ds_name
    ds_zarr = data_dir / (ds_name + ".zarr")
    ctc_url = f"http://data.celltrackingchallenge.net/training-datasets/{ds_name}.zip"
    zip_filename = data_dir / f"{ds_name}.zip"
    if not zip_filename.is_file():
        urlretrieve(ctc_url, filename=zip_filename)
    with zipfile.ZipFile(zip_filename, "r") as zip_ref:
        zip_ref.extractall(data_dir)
    zip_filename.unlink()

    convert_to_zarr(ds_dir / "01", ds_zarr, "01")
    convert_to_zarr(ds_dir / "01_ST" / "SEG", ds_zarr, "01_ST", relabel=True)
    shutil.rmtree(ds_dir)


def convert_4d_arr_to_zarr(
    tiff_file: Path, zarr_path: Path, zarr_group: str, relabel: bool = False
) -> None:
    """Convert 4D tiff file to zarr array. Deletes the tiff after conversion.

    Args:
        tiff_file: Path to the 4D tiff file
        zarr_path: Path to the zarr store to write to
        zarr_group: Name of the array within the zarr store
        relabel: If True, relabel segmentations to be unique across time
    """
    img = tifffile.imread(tiff_file)
    data_shape = img.shape
    data_dtype = img.dtype

    setup_zarr_group(zarr_path, zarr_format=2, mode="a")
    zarr_array = setup_zarr_array(
        zarr_path,
        zarr_format=2,
        mode="a",
        path=zarr_group,
        shape=data_shape,
        dtype=data_dtype,
    )

    max_label = 0
    for t in range(img.shape[0]):
        frame = img[t]
        if relabel:
            frame = frame.copy()
            frame[frame != 0] += max_label
            max_label = int(np.max(frame))
        zarr_array[t] = frame

    tiff_file.unlink()


def convert_to_zarr(
    tiff_path: Path, zarr_path: Path, zarr_group: str, relabel: bool = False
) -> None:
    """Convert a directory of tiff files to a zarr array. Deletes tiffs after conversion.

    Args:
        tiff_path: Path to directory containing tiff files (one per time point)
        zarr_path: Path to the zarr store to write to
        zarr_group: Name of the array within the zarr store
        relabel: If True, relabel segmentations to be unique across time
    """
    files = sorted(tiff_path.glob("*.tif"))
    logger.info("%s time points found.", len(files))

    # Read first frame to get shape and dtype
    first_frame = tifffile.imread(files[0])
    shape = (len(files), *first_frame.shape)

    setup_zarr_group(zarr_path, zarr_format=2, mode="a")
    zarr_array = setup_zarr_array(
        zarr_path,
        zarr_format=2,
        mode="a",
        path=zarr_group,
        shape=shape,
        dtype=first_frame.dtype,
    )

    # Write frames one at a time
    max_label = 0
    for t, file in enumerate(files):
        frame = tifffile.imread(file) if t > 0 else first_frame
        if relabel:
            frame = frame.copy()
            frame[frame != 0] += max_label
            max_label = int(np.max(frame))
        zarr_array[t] = frame
        file.unlink()

    tiff_path.rmdir()


def Fluo_N2DL_HeLa_crop_raw() -> LayerData:
    """Loads only the cropped raw data of Fluo-N2DL-HeLa (see Fluo_N2DL_HeLa_crop),
    downloading the dataset first if it is not present.

    Returns:
        LayerData: An image layer of the cropped 01 training raw data
    """
    ds_name = "Fluo-N2DL-HeLa"
    data_dir = Path(AppDirs("motile-tracker").user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    ds_zarr = data_dir / (ds_name + ".zarr")
    if not ds_zarr.exists():
        logger.info("Downloading %s", ds_name)
        download_ctc_dataset(ds_name, data_dir)
    raw_data = zarr.open(store=ds_zarr, mode="r")["01"][(slice(None), *HELA_CROP)]
    return (raw_data, {"name": "01_raw"}, "image")


def Mouse_Embryo_Membrane_raw() -> LayerData:
    """Loads only the raw data of Mouse_Embryo_Membrane, downloading the dataset
    first if it is not present.

    Returns:
        LayerData: An image layer of the membrane raw data
    """
    ds_name = "Mouse_Embryo_Membrane"
    data_dir = Path(AppDirs("motile-tracker").user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    ds_zarr = data_dir / (ds_name + ".zarr")
    if not ds_zarr.exists():
        logger.info("Downloading %s", ds_name)
        download_zenodo_dataset(ds_name, "imaging.tif", "segmentation.tif", data_dir)
    raw_data = zarr.open(store=ds_zarr, path="01_membrane", dimension_separator="/")[:]
    return (raw_data, {"name": "01_membrane"}, "image")


class SampleTracks(NamedTuple):
    """Example tracks shown in the welcome widget, with their raw data."""

    url: str  # Google Drive folder with the geff
    store_name: str  # name of the geff store in the user data dir
    raw_name: str  # name of the raw data layer
    load_raw: Callable[[], LayerData]


# Example tracks, by display name.
# TODO: the drive folders are missing their zarr metadata files. Until they are
# re-uploaded, the store names point at local test geffs, so the download is
# skipped when those are present.
SAMPLE_TRACKS: dict[str, SampleTracks] = {
    "Hela cells (2D)": SampleTracks(
        "https://drive.google.com/drive/folders/1zRRS4TmfRgFCr11MMWmzNnKSNTDVitJl",
        "test_data_2D.geff",
        "01_raw",
        Fluo_N2DL_HeLa_crop_raw,
    ),
    "Mouse embryo (3D)": SampleTracks(
        "https://drive.google.com/drive/folders/1FyZ6KGjCdE3o0R9LpKFpOGtJHMZWLDEQ",
        "test_data_3D.geff",
        "01_membrane",
        Mouse_Embryo_Membrane_raw,
    ),
}


def sample_tracks_path(name: str) -> Path:
    """Return the local path to the example tracks geff with the given name,
    downloading it from Google Drive into the appdir "user data dir" first if it
    is not present yet.

    Args:
        name (str): A key of SAMPLE_TRACKS

    Returns:
        Path: Path to the geff store
    """
    url, store_name, _, _ = SAMPLE_TRACKS[name]
    data_dir = Path(AppDirs("motile-tracker").user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    store_path = data_dir / store_name
    if not store_path.exists():
        logger.info("Downloading %s", name)
        download_drive_folder(url, store_path)
    return store_path


def download_drive_folder(url: str, output: Path) -> None:
    """Download a public Google Drive folder to the given path. The folder is
    first downloaded next to the output and only moved into place once complete,
    so an interrupted download is not mistaken for existing data.

    Args:
        url (str): Url of the Google Drive folder
        output (Path): Path to store the folder contents at
    """
    tmp_output = output.with_name(output.name + ".download")
    if tmp_output.exists():
        shutil.rmtree(tmp_output)
    files = gdown.download_folder(
        url=url, output=str(tmp_output), quiet=True, use_cookies=False
    )
    if not files:
        shutil.rmtree(tmp_output, ignore_errors=True)
        raise RuntimeError(f"Failed to download {url}")
    tmp_output.rename(output)
