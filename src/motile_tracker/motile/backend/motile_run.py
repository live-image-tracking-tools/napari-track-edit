from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import tracksdata as td
from funtracks.data_model import SolutionTracks
from funtracks.import_export import import_from_geff, load_v1_tracks

from motile_tracker.import_export.geff_io import is_geff, write_geff_over

from .solver_params import SolverParams

if TYPE_CHECKING:
    pass

STAMP_FORMAT = "%m%d%Y_%H%M%S"
PARAMS_FILENAME = "solver_params.json"
IN_POINTS_FILENAME = "input_points.npy"
GAPS_FILENAME = "gaps.txt"
ATTRS_FILENAME = "attrs.json"

# Internal edge attr keys managed by tracksdata — not user-facing features
_TRACKSDATA_INTERNAL_EDGE_KEYS = frozenset({"edge_id", "source_id", "target_id"})


class MotileRun(SolutionTracks):
    """An object representing a motile tracking run. Contains a name,
    parameters, time of creation, information about the solving process
    (status and list of solver gaps), and optionally the input and output
    segmentations and tracks. Mostly used for passing around the set of
    attributes needed to specify a run, as well as saving and loading.
    """

    def __init__(
        self,
        graph: td.graph.GraphView,
        run_name: str,
        time_attr: str = "t",
        pos_attr: str | tuple[str] | list[str] = "pos",
        scale: list[float] | None = None,
        ndim: int | None = None,
        solver_params: SolverParams | None = None,
        input_segmentation: np.ndarray | None = None,
        input_points: np.ndarray | None = None,
        time: datetime | None = None,
        gaps: list[float] | None = None,
        status: str = "done",
        _features=None,
        _segmentation=None,
    ):
        if ndim is None and input_segmentation is not None:
            ndim = input_segmentation.ndim

        super().__init__(
            graph,
            time_attr=time_attr,
            pos_attr=pos_attr,
            scale=scale,
            ndim=ndim,
            features=_features,
            _segmentation=_segmentation,
        )
        self.run_name = run_name
        self.solver_params = solver_params
        self.input_segmentation = input_segmentation
        self.input_points = input_points
        self.gaps = gaps
        self.status = status
        self.time = datetime.now() if time is None else time

    def _make_id(self) -> str:
        """Combine the time and run name into a unique id for the run

        Returns:
            str: A unique id combining the timestamp and run name
        """
        stamp = self.time.strftime(STAMP_FORMAT)
        return f"{stamp}_{self.run_name}"

    @staticmethod
    def _unpack_id(_id: str) -> tuple[datetime, str]:
        """Unpack a string id created with _make_id into the time and run name

        Args:
            _id (str): The id to unpack into time and run name

        Raises:
            ValueError: If the provided id is not in the expected format

        Returns:
            tuple[datetime, str]: A tuple of time and run name
        """
        stamp_len = len(datetime.now().strftime(STAMP_FORMAT))
        stamp = _id[0:stamp_len]
        run_name = _id[stamp_len + 1 :]
        try:
            time = datetime.strptime(stamp, STAMP_FORMAT)
        except ValueError as e:
            raise ValueError(
                f"Cannot unpack id {_id} into timestamp and run name."
            ) from e
        return time, run_name

    @classmethod
    def _resolve_name_and_time(
        cls, run_dir: Path, attrs: dict | None
    ) -> tuple[datetime | None, str]:
        """Determine the run name and run time for a run being loaded.

        Runs used to be saved in a directory named by _make_id, so the name and
        time could be recovered by unpacking the directory name. Newer runs
        store both in the attrs file instead, which lets them be saved to a
        directory the user named. Falls back through both, and finally to the
        directory name with no time, so that a run directory is loadable
        however it was named. A None time is replaced with the current time by
        __init__, so the run still displays.

        Args:
            run_dir (Path): The directory the run is being loaded from.
            attrs (dict | None): The loaded attrs, or None if there is no
                attrs file.

        Returns:
            tuple[datetime | None, str]: The run time and run name.
        """
        if attrs is not None and attrs.get("run_name") is not None:
            stamp = attrs.get("time")
            time = datetime.fromisoformat(stamp) if stamp is not None else None
            return time, attrs["run_name"]
        try:
            return cls._unpack_id(run_dir.stem)
        except ValueError:
            return None, run_dir.stem

    def save(self, path: str | Path, save_segmentation: bool = False) -> Path:
        """Save the run as a geff store at the provided path.

        The geff store is written at exactly `path` — no subdirectory is
        created — and the rest of the run (solver params, attrs, input points,
        gaps) is stored inside that store alongside the graph. A geff is a zarr
        directory, and writing a geff only replaces geff-controlled groups, so
        these files survive re-saving over the same store.

        Args:
            path (str | Path): The geff store to save the run to. Created if
                it does not exist, and replaced if it does.
            save_segmentation (bool): Ignored. Kept for backwards
                compatibility; the segmentation is never written here.

        Returns:
            (Path): The Path that the run was saved to.
        """
        run_dir = Path(path)
        write_geff_over(self, run_dir)
        self._save_params(run_dir)
        self._save_attrs(run_dir)
        if self.input_points is not None:
            self._save_array(run_dir, IN_POINTS_FILENAME, self.input_points)
        self._save_list(list_to_save=self.gaps, run_dir=run_dir, filename=GAPS_FILENAME)
        return run_dir

    @staticmethod
    def geff_path(run_dir: Path | str) -> Path | None:
        """Return the geff store holding a saved run's graph.

        Mirrors the layouts that :meth:`load` accepts. Runs saved by the
        current version are themselves the geff store. Returns None for v1
        runs, which stored the graph as graph.json rather than as a geff.

        Args:
            run_dir (Path | str): A directory created by MotileRun.save.
        """
        run_dir = Path(run_dir)
        if MotileRun._is_geff(run_dir):
            return run_dir
        tracks_path = run_dir / "tracks.geff"
        if tracks_path.exists():
            return tracks_path
        if (run_dir / "graph.json").exists():
            return None
        return run_dir / "tracks"

    @staticmethod
    def _is_geff(directory: Path) -> bool:
        """Whether the given directory is itself a geff store.

        Distinguishes a run saved as a geff from an older run directory that
        merely contains one, which is exactly what load() needs.
        """
        return is_geff(directory)

    @classmethod
    def load(cls, run_dir: Path | str, output_required: bool = True):
        """Load a run from disk into memory.

        Args:
            run_dir (Path | str): A directory containing the saved run.
                Should be the subdirectory created by MotileRun.save that
                includes the timestamp and run name.
            output_required (bool): If the model outputs are required.
                If true, will raise an error if the output files are not found.
                Defualts to True.

        Returns:
            MotileRun: The run saved in the provided directory.
        """
        if isinstance(run_dir, str):
            run_dir = Path(run_dir)
        params = cls._load_params(run_dir)
        input_points = cls._load_array(run_dir, IN_POINTS_FILENAME, required=False)
        attrs = cls._load_attrs(run_dir)
        time, run_name = cls._resolve_name_and_time(run_dir, attrs)
        # Support the current format (the run dir is itself the geff store) as
        # well as old v1 ("graph.json" at run dir level), intermediate
        # ("tracks" zarr), and ("tracks.geff") save formats
        tracks_path = run_dir / "tracks.geff"
        if cls._is_geff(run_dir):
            tracks = import_from_geff(run_dir)
        elif tracks_path.exists():
            tracks = import_from_geff(tracks_path)
        elif (run_dir / "graph.json").exists():
            tracks = load_v1_tracks(run_dir, solution=True)
        else:
            tracks = import_from_geff(run_dir / "tracks")
        if attrs is not None:
            # New runs use the "shape" key; fall back to the legacy
            # "segmentation_shape" key for runs saved by older versions.
            seg_shape = attrs.get("shape", attrs.get("segmentation_shape"))
            if seg_shape is not None:
                tracks.graph._update_metadata(shape=tuple(seg_shape))
            scale = attrs.get("scale") or tracks.scale
            time_attr = attrs.get("time_attr") or tracks.features.time_key
        else:
            scale = tracks.scale
            time_attr = tracks.features.time_key
        gaps = cls._load_list(run_dir=run_dir, filename=GAPS_FILENAME, required=False)
        return cls(
            graph=tracks.graph_full,
            run_name=run_name,
            solver_params=params,
            input_points=input_points,
            time=time,
            gaps=gaps,
            pos_attr=tracks.features.position_key,
            time_attr=time_attr,
            scale=scale,
            ndim=tracks.ndim,
            _features=tracks.features,
        )

    def _save_params(self, run_dir: Path):
        """Save the run parameters in the provided run directory. Currently
        dumps the parameters dict into a json file. Skips writing if there are
        no params, which only happens for a run loaded from a directory that
        had no params file (see _load_params).

        Args:
            run_dir (Path): A directory in which to save the parameters file.
        """
        if self.solver_params is None:
            return
        params_file = run_dir / PARAMS_FILENAME
        with open(params_file, "w") as f:
            json.dump(self.solver_params.__dict__, f)

    @staticmethod
    def _load_params(run_dir: Path) -> SolverParams | None:
        """Load parameters from the parameters json file in the provided
        directory. Returns None if the file is absent, which is the case for
        v1 run directories and for runs saved by versions that wrapped
        imported (CSV/geff) tracks in a MotileRun with no solver params.

        Args:
            run_dir (Path): The directory in which to find the parameters file.

        Returns:
            SolverParams | None: The solver parameters, or None if no params
                file exists in the run directory.
        """
        params_file = run_dir / PARAMS_FILENAME
        if not params_file.is_file():
            return None
        with open(params_file) as f:
            params_dict = json.load(f)
        return SolverParams(**params_dict)

    def _save_array(self, run_dir: Path, filename: str, array: np.ndarray):
        """Save a segmentation as a numpy array using np.save. In the future,
        could be changed to use zarr or other file types.

        Args:
            run_dir (Path): The directory in which to save the segmentation
            filename (str): The filename to use
            array (np.array): The array to save
        """
        out_path = run_dir / filename
        np.save(out_path, array)

    @staticmethod
    def _load_array(
        run_dir: Path, filename: str, required: bool = True
    ) -> np.ndarray | None:
        """Load an array from file using np.load. In the future,
        could be lazy loading from a zarr.

        Args:
            run_dir (Path): The base run directory containing the array
            filename (str): The name of the file to load
            required (bool, optional): If true, will fail if the array
                file is not present. If false, will return None if the file
                is not present. Defaults to True.

        Raises:
            FileNotFoundError: If the array file is not found, and
                it was required.

        Returns:
            np.ndarray | None: The array, or None if the file was
                not found and not required.
        """
        array_path = run_dir / filename
        if array_path.is_file():
            return np.load(array_path)
        elif required:
            raise FileNotFoundError(f"No segmentation at {array_path}")
        else:
            return None

    def _save_attrs(self, directory: Path):
        """Save the run name, run time, time_attr, scale, and
        shape in a json file.

        The run name and time are stored here rather than being recoverable
        from the directory name alone (see _make_id), so that a run can be
        saved to a directory the user named.

        Note that "time" is when the run was solved, while "time_attr" is the
        name of the graph's time column.

        Args:
            directory (Path):  The directory in which to save the attributes
        """
        out_path = directory / ATTRS_FILENAME
        seg_shape = self.graph.metadata.get("shape")
        scale = (
            self.scale
            if not isinstance(self.scale, np.ndarray)
            else self.scale.tolist()
        )
        attrs_dict = {
            "shape": list(seg_shape) if seg_shape is not None else None,
            "scale": scale,
            "time_attr": self.features.time_key,
            "run_name": self.run_name,
            "time": self.time.isoformat(),
        }
        with open(out_path, "w") as f:
            json.dump(attrs_dict, f)

    @staticmethod
    def _load_attrs(run_dir: Path) -> dict | None:
        """Load attrs from the attrs json file in the provided directory, if present.

        Args:
            run_dir (Path): The directory in which to find the attrs file.

        Returns:
            dict | None: The attrs dict, or None if the file was not found.
        """
        attrs_file = run_dir / ATTRS_FILENAME
        if not attrs_file.is_file():
            return None
        with open(attrs_file) as f:
            return json.load(f)

    def _save_list(self, list_to_save: list | None, run_dir: Path, filename: str):
        if list_to_save is None:
            return
        list_file = run_dir / filename
        with open(list_file, "w") as f:
            f.write(",".join(map(str, list_to_save)))

    @staticmethod
    def _load_list(run_dir: Path, filename: str, required: bool = True) -> list[float]:
        list_file = run_dir / filename
        if list_file.is_file():
            with open(list_file) as f:
                file_content = f.read()
            if file_content == "":
                return None
            list_values = list(map(float, file_content.split(",")))
            return list_values
        elif required:
            raise FileNotFoundError(f"No content found at {list_file}")
        else:
            return None

    def delete(self, base_path: str | Path):
        """Delete this run from the file system. Will look inside base_path
        for the directory corresponding to this run and delete it.

        Args:
            base_path (str | Path): The parent directory where the run is saved
                (not the one created by self.save).
        """
        base_path = Path(base_path)
        run_dir = base_path / self._make_id()
        # Lets be safe and remove the expected files and then the directory.
        # Both files are optional (params for imported runs, gaps when None).
        (run_dir / PARAMS_FILENAME).unlink(missing_ok=True)
        (run_dir / GAPS_FILENAME).unlink(missing_ok=True)
        super().delete(run_dir)
