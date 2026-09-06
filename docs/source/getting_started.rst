Getting started with Motile Tracker
===================================

Installation
************
Install from PyPI in the environment of your choice (e.g. ``venv``, ``conda``)::

    pip install motile-tracker

Currently, motile_tracker requires Python >=3.11.

If this is successful, you can then run ``napari`` from your command line, and
the motile tracker should be visible in the ``Plugins`` drop down menu.
Clicking the Main Motile Widget should open the menu widget on the right of the viewer,
and a lineage tree view in the bottom of the viewer.

Recommended extras
------------------
For better performance, you can install optional extras:

- **numba**: Speeds up candidate graph construction significantly.::

    pip install motile-tracker[numba]

- **gurobi**: Uses the Gurobi solver instead of the default open-source solver.
  Gurobi is much faster but requires a license (free for academics).::

    pip install motile-tracker[gurobi]

You can install multiple extras at once: ``pip install motile-tracker[numba,gurobi]``

Gurobi license version mismatch
-------------------------------
If you have a Gurobi license and encounter an error about license version mismatch,
you may need to install a specific version of ``gurobipy`` that matches your license.
Use one of the version-specific extras::

    pip install motile-tracker[gurobi12]  # For Gurobi 12.x licenses
    pip install motile-tracker[gurobi13]  # For Gurobi 13.x licenses

Tutorial video
**************
This video walks through tracking an example dataset from the `Cell Tracking Challenge`_,
covering most of the same information as the rest of this getting started guide.

.. raw:: html

  <iframe src="https://drive.google.com/file/d/1zHvO9inHw0Hlbwq5zmRX4qUnVuO21neo/preview" width="640" height="480" allow="autoplay"></iframe>

You can also follow this `tutorial`_.

Input data
**********
Motile Tracker does not perform detection: you must provide a Labels layer or a Points layer
containing the objects you want to track.
The Labels layer must have time as the
first dimension followed by the spatial dimensions (no channels).
The Points layer must have the point locations with time as the first number,
followed by the spatial dimensions. While source images are
nice to qualitatively evaluate results, they are not necessary to run tracking.

There are two example datasets provided in ``File`` -> ``Open Sample`` -> ``Motile Tracker``.
A 2D HeLa dataset from the `Cell Tracking Challenge`_ is provided, both in full and a cropped subset for testing features on smaller data, and has both a Labels layer and Points layer.
There is also a 3D dataset of images and segmentations of a membrane-labeled developing early mouse embryo (4-26 cells)
from `Fabrèges et al (2024)`_, automatically downloaded from `zenodo`_.

In the future, we could also support Shapes layers as input (for example,
for bounding box tracking) - please react to
`Issue #48`_ if this is important to your use case, and give feedback on what type
of shape linking you want.

Tracker widgets
***************
Motile Tracker comes with several widgets for tracking, viewing, and editing. You can open all widgets via ``Plugins`` -> ``Motile Tracker`` -> ``Open all widgets``,
or select individual from the same dropdown menu. You can optionally close or hide widgets via the close (x) button, or via right mouse-click on the 'eye' button.
Optionally, you can float individual widgets and place them somewhere else (for example, you can move the lineage view to a secondary monitor).
If you press the `/` key, you can hide/show all Tracker widgets.

Running tracking
****************
The ``Tracking`` tab by default opens to the ``Run Editor`` view. In this view,
you can pick a name for your run, select an input layer, set
hyperparameters, and start a motile run. Hovering over the title of each
element in the widget will make a tooltip appear describing the purpose
of the element. All hyperparameters are explained in the :doc:`tracking with motile <motile>` docs page.
When you are ready, click the ``Run Tracking (SCIP)`` button to start tracking.

Viewing and editing run results
*******************************
Clicking the ``Run Tracking (SCIP)`` button will automatically take you to the motile ``Run Viewer``
menu, display a points and a tracks layer in the napari viewer, and populate the Lineage Tree view. If your input was a segmentation, there will also be
a new segmentation layer where the IDs have been relabeled to match across time, and the input segmentation layer will be hidden to avoid confusion.

You can :doc:`view the results <tree_view>` using the synchronized napari layers and tree view, and :doc:`edit the detections and links <editing>` to correct any mistakes that you find. You can also re-run the tracking step with different parameters. Re-running the motile tracking will only take into account the detection corrections
if you select the new labels/points layer as input: our next major feature to add
is incorporating the detection and linking corrections into the optimization task in a more principled manner.

Each ``Tracking Run`` will be stored in the ``Results List`` widget.
These are the runs that are stored in memory - if you run tracking multiple
times with different inputs or parameters, you can click back and forth
between the results here.
If your input was a Labels layer, the ``node_id`` will be determined by segmentation label id. If your original segmentation
repeated labels across time, the application will relabel them all to be unique, and
the new label id will be used as the node id.
If your input was a Points layer, the ``node_id`` is simply the index of the
node in the list of points.
Deleting runs you do not want to keep viewing is a good idea, since these are stored in memory.
Tracks that were saved in previous sessions do not appear here until you load them from disk with the ``Load`` button.
The tracking results can also be visualized as a lineage tree.
You can open the lineage tree widget via ``Plugins`` > ``Motile Tracker`` > ``Widget - Lineage View``.
For more details, go to the :doc:`Tree View <tree_view>` documentation.

Tracking from scratch
*********************
Instead of automatic tracking, it is also possible to manually track from scratch. The ``Tracks List`` widget offers the option to create an empty tree that you can populate yourself by adding nodes as points or as segmentation labels.

Displaying feature measurements
*******************************
If you are tracking with a segmentation layer, you can select size and shape features to measure in the ``Features`` widget.
Once selected, the measurements for these features will appear in the ``Lineage View`` (select ``Plot`` > ``Feature`` to display them), and in the ``Table`` widget.

.. _save-load-vs-import-export:

Saving and loading vs. importing and exporting
**********************************************
The ``Results List`` widget offers two different ways of getting tracks in and out
of the application, and it is worth understanding which one you want.

**Saving and loading** is for continuing your own work. The application controls the
format, so it can make and enforce assumptions about it: tracks are always written
as a `geff`_ store, with the metadata and attributes the application needs already
in place. Anything you save can be loaded back into a later session and picked up
exactly where you left off, including run-specific extras like the motile solver
parameters. Use this while you are still working on a dataset.

**Importing and exporting** is for exchanging tracks with other tools. Here the
application cannot assume much about the format, so it supports more of them (`geff`_
and CSV) and asks you to fill in the gaps - which column means what, how the data is
scaled, where the segmentation lives. An export is a snapshot for another tool to read,
not a session you can resume, and importing tracks from elsewhere requires the
column mapping step described in :doc:`Importing externally generated tracks <view_external_tracks>`.

In short: save/load round-trips within the application, import/export crosses the
boundary to other tools.

Saving tracks
-------------
Above the results list are a ``Save directory`` field, with a ``Browse`` button, and a
``Save filename`` field. Together these are the path that the save (floppy disk) button
beside a set of tracks writes to; the ``.geff`` suffix is added for you and shown as a
fixed label beside the filename. The directory starts out as an application-owned
location (the same place the sample data is downloaded to) and the filename follows
whichever tracks you have selected, so in the common case you can simply click save.

Both fields are editable, and your edits last for the rest of the session - so if you
point the directory somewhere else once, subsequent saves go there too. Once you have
typed your own filename it stops following the selection, so selecting different tracks
will not overwrite what you typed. Because names in the results list are not required to
be unique, always check the filename before saving if you have several similarly named
sets of tracks.

Saving writes to exactly the path shown; there is no timestamped subdirectory. If
something already exists at that path you will be asked to confirm before it is
replaced. Note that saving a set of tracks over an existing geff store replaces the
tracks but leaves any other files in the store alone.

Loading tracks
--------------
The dropdown menu at the bottom of the widget selects what to load, and the ``Load``
button starts it:

- ``Tracks (geff)`` - load tracks previously saved from this application. Select the
  ``.geff`` store itself.
- ``Motile Run`` - load a saved motile run, which restores the solver parameters into
  the ``Run Editor`` along with the tracks. Select the ``.geff`` store the run was
  saved to. Runs saved by older versions, which used a timestamped directory
  containing the tracks and a separate parameters file, can still be loaded.
- ``External tracks from CSV`` and ``External tracks from geff`` - import tracks that
  were generated elsewhere. These open the import dialog, where you map columns to
  attributes and optionally provide a segmentation; see
  :doc:`Importing externally generated tracks <view_external_tracks>`.

Exporting tracks
----------------
The export button beside a set of tracks in the results list opens the export dialog,
where you choose ``GEFF``
or ``CSV`` and pick the location, optionally including the (relabeled) segmentation as
zarr or tiff. You can also export a subset of tracks from the Groups tab. Exported tracks are meant to be read by other tools: to continue working
on them here later, save them instead.

.. _Issue #48: https://github.com/funkelab/motile_tracker/issues/48
.. _Cell Tracking Challenge: https://celltrackingchallenge.net/
.. _Fabrèges et al (2024): https://www.science.org/doi/10.1126/science.adh1145
.. _zenodo: https://zenodo.org/records/13903500
.. _geff: https://github.com/live-image-tracking-tools/geff
.. _tutorial: https://github.com/funkelab/motile_tracker/blob/main/assets/motile-tracker_tutorial.pdf
