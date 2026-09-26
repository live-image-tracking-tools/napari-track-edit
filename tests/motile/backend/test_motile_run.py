import warnings

import numpy as np

from napari_track_edit.motile.backend import MotileRun, SolverParams


def test_geff_path_finds_saved_geff(tmp_path, graph_2d):
    """A run saved by the current version is itself the geff store."""
    run = MotileRun(graph=graph_2d, run_name="test", solver_params=SolverParams())
    run_dir = run.save(tmp_path / "my_run.geff")

    geff = MotileRun.geff_path(run_dir)
    assert geff == run_dir
    assert geff.exists()


def test_geff_path_finds_nested_tracks_geff(tmp_path):
    """Runs saved by the previous version nested the graph in tracks.geff."""
    run_dir = tmp_path / "run"
    (run_dir / "tracks.geff").mkdir(parents=True)

    assert MotileRun.geff_path(run_dir) == run_dir / "tracks.geff"


def test_save_writes_params_inside_the_geff(tmp_path, graph_2d):
    """Solver params live inside the store, not beside it."""
    run = MotileRun(graph=graph_2d, run_name="test", solver_params=SolverParams())
    run_dir = run.save(tmp_path / "my_run.geff")

    assert (run_dir / "solver_params.json").exists()
    assert (run_dir / "attrs.json").exists()
    assert (run_dir / "nodes").exists()


def test_resave_is_quiet(tmp_path, graph_2d):
    """Overwriting a run must not warn about its own files.

    The run keeps solver params, attrs, gaps and input points inside the geff
    store. Zarr walks the directory while the geff is being replaced and warns
    once per file it does not recognise, which is expected and not actionable.
    """
    run = MotileRun(graph=graph_2d, run_name="test", solver_params=SolverParams())
    path = tmp_path / "my_run.geff"
    run.save(path)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run.save(path)

    unrecognized = [
        w for w in caught if "not recognized as a component" in str(w.message)
    ]
    non_geff = [w for w in caught if "non-geff members" in str(w.message)]
    assert unrecognized == []
    assert non_geff == []


def test_resave_preserves_params(tmp_path, graph_2d):
    """Writing a geff only replaces geff-controlled groups, so the run's own
    files survive being saved over."""
    run = MotileRun(graph=graph_2d, run_name="test", solver_params=SolverParams())
    path = tmp_path / "my_run.geff"
    run.save(path)
    run.save(path)

    assert (path / "solver_params.json").exists()
    assert MotileRun.load(path).solver_params == run.solver_params


def test_geff_path_falls_back_to_tracks_dir(tmp_path):
    """Intermediate-format runs stored the graph in a 'tracks' zarr."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "tracks").mkdir()

    assert MotileRun.geff_path(run_dir) == run_dir / "tracks"


def test_geff_path_none_for_v1_run(tmp_path):
    """v1 runs stored the graph as graph.json, so there is no geff to report."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "graph.json").write_text("{}")

    assert MotileRun.geff_path(run_dir) is None


def test_load_run_dir_renamed_to_non_timestamp(tmp_path, graph_2d):
    """A run directory the user renamed must still load.

    The name and time come from the attrs file, so they survive a rename that
    _unpack_id could not parse.
    """
    run = MotileRun(graph=graph_2d, run_name="my_run", solver_params=SolverParams())
    run_dir = run.save(tmp_path / "my_run.geff")
    renamed = run_dir.rename(tmp_path / "not_a_timestamp")

    loaded = MotileRun.load(renamed)

    assert loaded.run_name == "my_run"
    assert loaded.time == run.time


def test_load_falls_back_to_unpack_id_without_attrs(tmp_path, graph_2d):
    """Runs saved before the name/time were written to attrs still load by
    unpacking the timestamped directory name."""
    run = MotileRun(graph=graph_2d, run_name="test", solver_params=SolverParams())
    # reproduce the old layout: a directory named by _make_id
    run_dir = run.save(tmp_path / run._make_id())
    (run_dir / "attrs.json").unlink()

    loaded = MotileRun.load(run_dir)

    assert loaded.run_name == "test"
    # the directory-name timestamp only has second granularity
    assert loaded.time == run.time.replace(microsecond=0)


def test_resolve_name_and_time_falls_back_to_dir_stem(tmp_path):
    """With neither attrs nor a parseable directory name, the directory name
    is used and the time is left for __init__ to fill in."""
    time, name = MotileRun._resolve_name_and_time(tmp_path / "some_run", None)

    assert name == "some_run"
    assert time is None


def test_save_load(tmp_path, graph_2d):
    run_name = "test"
    scale = [1.0, 2.0, 3.0]
    run = MotileRun(
        graph=graph_2d,
        run_name=run_name,
        solver_params=SolverParams(),
        scale=scale,
    )
    path = run.save(tmp_path / "test.geff")
    newrun = MotileRun.load(path)
    assert set(run.graph_solution.node_ids()) == set(newrun.graph_solution.node_ids())
    assert {tuple(e) for e in run.graph_solution.edge_list()} == {
        tuple(e) for e in newrun.graph_solution.edge_list()
    }
    assert run.run_name == newrun.run_name
    assert np.array_equal(np.asarray(run.segmentation), np.asarray(newrun.segmentation))
    # the time now round-trips exactly: it comes from the attrs file rather
    # than from the second-granularity timestamp in the directory name
    assert run.time == newrun.time
    assert run.gaps == newrun.gaps
    assert run.scale == newrun.scale
    assert run.solver_params == newrun.solver_params
    # Verify core accessor methods work on the loaded run
    # (regression: time_attr mismatch after load caused KeyError in get_time)
    node_ids = list(newrun.graph_solution.node_ids())
    for node_id in node_ids:
        newrun.get_time(node_id)
        newrun.get_position(node_id)
        newrun.get_track_id(node_id)
    newrun.get_positions(node_ids, incl_time=True)
