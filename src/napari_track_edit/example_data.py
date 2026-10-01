import logging
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
from urllib.request import urlretrieve

import numpy as np
import tifffile
import zarr
from funtracks.utils import setup_zarr_array, setup_zarr_group
from napari.types import LayerData
from platformdirs import PlatformDirs
from skimage.measure import regionprops

logger = logging.getLogger(__name__)

# Download sources for the napari sample data
ZENODO_RAW_URL = "https://zenodo.org/records/13903500/files/imaging.zip"
ZENODO_LABELS_URL = "https://zenodo.org/records/13903500/files/segmentation.zip"
CTC_URL_TEMPLATE = (
    "http://data.celltrackingchallenge.net/training-datasets/{ds_name}.zip"
)

# Region of Fluo-N2DL-HeLa used for the crop: (y, x) slices
HELA_CROP = (slice(90, 300), slice(700, 1040))

# Signature of the `urlretrieve` report hook: (block number, block size, total size)
ReportHook = Callable[[int, int, int], None]


def user_data_dir() -> Path:
    """The platformdirs "user data dir", where all example data is cached. Created if
    it does not exist yet.
    """
    data_dir = Path(PlatformDirs("napari-track-edit").user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _ensure_dataset(ds_name: str, data_dir: Path, download: Callable[[], None]) -> Path:
    """Return the path to a dataset's zarr, downloading the dataset first if it
    is not there yet.

    Args:
        ds_name (str): Dataset name, the zarr is named after it
        data_dir (Path): The directory the dataset is cached in
        download (Callable[[], None]): Fetches and converts the dataset

    Returns:
        Path: Path to the zarr holding the dataset
    """
    ds_zarr = data_dir / (ds_name + ".zarr")
    if not ds_zarr.exists():
        logger.info("Downloading %s", ds_name)
        download()
    return ds_zarr


def _zenodo_raw_layer(ds_zarr: Path) -> LayerData:
    """The membrane intensity layer of a zenodo dataset zarr."""
    raw_data = zarr.open(store=ds_zarr, path="01_membrane", dimension_separator="/")[:]
    return (raw_data, {"name": "01_membrane"}, "image")


def _ctc_raw_layer(ds_zarr: Path, crop_region: bool) -> LayerData:
    """The 01 training intensity layer of a CTC dataset zarr."""
    raw_data = zarr.open(store=ds_zarr, mode="r")["01"]
    raw_data = raw_data[(slice(None), *HELA_CROP)] if crop_region else raw_data[:]
    return (raw_data, {"name": "01_raw"}, "image")


def Mouse_Embryo_Membrane() -> list[LayerData]:
    """Loads the Mouse Embryo Membrane raw data and segmentation data from
    the appdir "user data dir". Will download it from the Zenodo DOI if not present.

    Returns:
        list[LayerData]: An image layer of raw data and a segmentation labels
            layer
    """
    ds_name = "Mouse_Embryo_Membrane"
    data_dir = user_data_dir()
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
    return read_ctc_dataset("Fluo-N2DL-HeLa", user_data_dir())


def Fluo_N2DL_HeLa_crop() -> list[LayerData]:
    """Loads the Fluo-N2DL-HeLa 01 training raw data and silver truth from
    the appdir "user data dir". Will download it from the CTC and convert it to
    zarr if it is not present already.

    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    return read_ctc_dataset("Fluo-N2DL-HeLa", user_data_dir(), crop_region=True)


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
    ds_zarr = _ensure_dataset(
        ds_name,
        data_dir,
        lambda: download_zenodo_dataset(ds_name, raw_name, label_name, data_dir),
    )
    raw_layer_data = _zenodo_raw_layer(ds_zarr)
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
    ds_zarr = _ensure_dataset(
        ds_name, data_dir, lambda: download_ctc_dataset(ds_name, data_dir)
    )
    zarr_store = zarr.open(store=ds_zarr, mode="a")  # Open in append mode ('a')
    raw_layer_data = _ctc_raw_layer(ds_zarr, crop_region)
    seg_data = zarr_store["01_ST"]
    seg_data = seg_data[(slice(None), *HELA_CROP)] if crop_region else seg_data[:]
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
    ds_name: str,
    raw_name: str,
    label_name: str,
    data_dir: Path,
    reporthook: ReportHook | None = None,
) -> None:
    """Download a sample dataset from zenodo doi and unzip it, then delete the zip. Then convert the tiffs to
    zarrs for the first training set consisting of 3D membrane intensity images and segmentation.

    Args:
        ds_name (str): Name to give to the dataset
        raw_name (str): Name of the file that contains the intensity data
        label_name (str): Name of the file that contains the label data
        data_dir (Path): The directory in which to store the data.
        reporthook (ReportHook | None): Called with the download progress.
    """
    ds_file_raw = data_dir / raw_name
    ds_file_labels = data_dir / label_name
    ds_zarr = data_dir / (ds_name + ".zarr")
    url_raw = ZENODO_RAW_URL
    url_labels = ZENODO_LABELS_URL
    zip_filename_raw = data_dir / "imaging.zip"
    zip_filename_labels = data_dir / "segmentation.zip"

    if not zip_filename_raw.is_file():
        urlretrieve(url_raw, filename=zip_filename_raw, reporthook=reporthook)
    if not zip_filename_labels.is_file():
        urlretrieve(url_labels, filename=zip_filename_labels, reporthook=reporthook)

    with zipfile.ZipFile(zip_filename_raw, "r") as zip_ref:
        zip_ref.extractall(data_dir)
    with zipfile.ZipFile(zip_filename_labels, "r") as zip_ref:
        zip_ref.extractall(data_dir)

    zip_filename_raw.unlink()
    zip_filename_labels.unlink()

    convert_4d_arr_to_zarr(ds_file_raw, ds_zarr, "01_membrane")
    convert_4d_arr_to_zarr(ds_file_labels, ds_zarr, "01_labels")


def download_ctc_dataset(
    ds_name: str, data_dir: Path, reporthook: ReportHook | None = None
) -> None:
    """Download a dataset from the Cell Tracking Challenge
    and unzip it, then delete the zip. Then convert the tiffs to
    zarrs for the first training set images and silver truth.

    Args:
        ds_name (str): Dataset name, according to the CTC
        data_dir (Path): The directory in which to store the data.
        reporthook (ReportHook | None): Called with the download progress.
    """
    ds_dir = data_dir / ds_name
    ds_zarr = data_dir / (ds_name + ".zarr")
    ctc_url = CTC_URL_TEMPLATE.format(ds_name=ds_name)
    zip_filename = data_dir / f"{ds_name}.zip"
    if not zip_filename.is_file():
        urlretrieve(ctc_url, filename=zip_filename, reporthook=reporthook)
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


def Fluo_N2DL_HeLa_crop_raw(reporthook: ReportHook | None = None) -> LayerData:
    """Loads only the cropped raw data of Fluo-N2DL-HeLa (see Fluo_N2DL_HeLa_crop),
    downloading the dataset first if it is not present.

    Args:
        reporthook (ReportHook | None): Called with the download progress.

    Returns:
        LayerData: An image layer of the cropped 01 training raw data
    """
    ds_name = "Fluo-N2DL-HeLa"
    data_dir = user_data_dir()
    ds_zarr = _ensure_dataset(
        ds_name,
        data_dir,
        lambda: download_ctc_dataset(ds_name, data_dir, reporthook),
    )
    return _ctc_raw_layer(ds_zarr, crop_region=True)


def Mouse_Embryo_Membrane_raw(reporthook: ReportHook | None = None) -> LayerData:
    """Loads only the raw data of Mouse_Embryo_Membrane, downloading the dataset
    first if it is not present.

    Args:
        reporthook (ReportHook | None): Called with the download progress.

    Returns:
        LayerData: An image layer of the membrane raw data
    """
    ds_name = "Mouse_Embryo_Membrane"
    data_dir = user_data_dir()
    ds_zarr = _ensure_dataset(
        ds_name,
        data_dir,
        lambda: download_zenodo_dataset(
            ds_name, "imaging.tif", "segmentation.tif", data_dir, reporthook
        ),
    )
    return _zenodo_raw_layer(ds_zarr)


class SampleTracks(NamedTuple):
    """Example tracks shown in the welcome widget, with their raw data."""

    url: str  # download url of a zip holding the geff store
    store_name: str  # name of the geff store in the zip and in the user data dir
    raw_name: str  # name of the raw data layer
    raw_zarr: str  # name of the zarr the raw data is cached in
    raw_size: str  # download size of the raw data, shown before downloading it
    load_raw: Callable[..., LayerData]  # takes an optional report hook


def _drive_download_url(file_id: str) -> str:
    """Direct-download URL for a Google Drive file (skips the preview page)."""
    return (
        f"https://drive.usercontent.google.com/download?id={file_id}"
        "&export=download&confirm=t"
    )


# Example tracks, by display name. They are zipped, because Google Drive drops the
# hidden zarr metadata files (.zattrs, ...) of uploaded folders.
SAMPLE_TRACKS: dict[str, SampleTracks] = {
    "Hela cells (2D)": SampleTracks(
        _drive_download_url("1wI1IHtxvbXB6Tg75zozxnFbeTITBefSW"),
        "hela2D_crop_tracks.geff",
        "01_raw",
        "Fluo-N2DL-HeLa.zarr",
        "190 MB",
        Fluo_N2DL_HeLa_crop_raw,
    ),
    "Mouse embryo (3D)": SampleTracks(
        _drive_download_url("1zTiI4FRiSyOomaN-eV_HBTqQoawUCPWi"),
        "mouse3D_tracks.geff",
        "01_membrane",
        "Mouse_Embryo_Membrane.zarr",
        "250 MB",
        Mouse_Embryo_Membrane_raw,
    ),
}


def sample_tracks_path(name: str, reporthook: ReportHook | None = None) -> Path:
    """Return the local path to the example tracks geff with the given name,
    downloading it from Google Drive into the appdir "user data dir" first if it
    is not present yet.

    Args:
        name (str): A key of SAMPLE_TRACKS
        reporthook (ReportHook | None): Called with the download progress.

    Returns:
        Path: Path to the geff store
    """
    store_name = SAMPLE_TRACKS[name].store_name
    store_path = user_data_dir() / store_name
    if not store_path.exists():
        logger.info("Downloading %s", name)
        download_zipped_store(SAMPLE_TRACKS[name].url, store_path, reporthook)
    return store_path


def raw_data_is_downloaded(name: str) -> bool:
    """Whether the raw data belonging to a sample is already on disk, so that
    clicking the sample does not trigger a large download unannounced.

    Args:
        name (str): A key of SAMPLE_TRACKS

    Returns:
        bool: True if the zarr holding the raw data exists
    """
    return (user_data_dir() / SAMPLE_TRACKS[name].raw_zarr).exists()


def download_zipped_store(
    url: str, output: Path, reporthook: ReportHook | None = None
) -> None:
    """Download a zip holding a store named like the output, and unpack it there.

    The zip is downloaded and unpacked next to the output, and only moved into
    place once complete, so an interrupted download is not mistaken for existing
    data.

    Args:
        url (str): Download url of the zip
        output (Path): Path to put the store at. The zip must contain a directory
            with the same name.
        reporthook (ReportHook | None): Called with the download progress.
    """
    tmp_dir = output.with_name(output.name + ".download")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir()
    try:
        zip_path = tmp_dir / "download.zip"
        urlretrieve(url, filename=zip_path, reporthook=reporthook)  # noqa: S310
        if not zipfile.is_zipfile(zip_path):
            # Google Drive serves an html page instead of the file when the
            # download is blocked (quota exceeded, permissions changed, ...).
            raise RuntimeError(f"Google Drive refused the download of {url}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)
        store = tmp_dir / output.name
        if not store.is_dir():
            raise RuntimeError(f"{url} does not contain {output.name}")
        store.rename(output)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
