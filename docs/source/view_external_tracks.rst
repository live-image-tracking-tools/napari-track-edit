Importing Externally Generated Tracks
=====================================

Usage Overview
**************

It is also possible to view tracks that were not created from the motile widget using
the synchronized Lineage View and napari layers. Bringing them in is an *import* rather
than a load: because the application cannot assume anything about how another tool
wrote the data, you have to describe its layout as part of importing it. See
:ref:`save-load-vs-import-export` for how this differs from loading tracks you saved
here yourself.

To import, navigate to the ``Results List`` tab and
select ``External tracks from CSV`` or ``External tracks from geff`` in the dropdown menu at the bottom of the widgets, and click ``Load``.
A pop up menu will allow you to select a CSV file or geff zarr folder and map its columns to the required default attributes and optional additional attributes.
You may also provide the accompanying segmentation and specify scaling information.

Once imported, tracks appear in the results list like any other set of tracks, and can
be edited and then saved in the application's own format so that later sessions can load
them back without repeating the column mapping.

The following columns have to be selected:

- time: representing the position of the object in the time dimension.
- x: x centroid coordinate of the object.
- y: y centroid coordinate of the object.
- z (optional): z centroid coordinate of the object, if it is a 3D object.
- id: unique id of the object.
- parent_id: id of the directly connected predecessor (parent) of the object. Should be empty if the object is at the start of a lineage.
- seg_id: label value in the segmentation image data (if provided) that corresponds to the object id.

From this, a `Tracks object`_ is generated, containing a networkx graph representing the tracking result, and optionally
a segmentation. The networkx graph is directed, with nodes representing detections and
edges going from a detection in time t to the same object in t+n (edges go forward in time).
Nodes must have an attribute representing time, by default named "t" but a different name
can be stored in the ``Tracks.time_attr`` attribute. Nodes must also have one or more attributes
representing position. The default way of storing positions on nodes is an attribute called
"pos" containing a list of position values, but dimensions can also be stored in separate attributes
(e.g. "x" and "y", each with one value). The name or list of names of the position attributes
should be specified in ``Tracks.pos_attr``.

The segmentation is expected to be a numpy array with time as the first dimension, followed
by the position dimensions in the same order as the ``Tracks.pos_attr``. The segmentation
must have unique label ids across all time points - there is a helper function in the
funtracks called ensure_unique_labels that relabels a segmentation to be unique
across time if needed. If a segmentation is provided, the node ids in the graph should
match label id of the corresponding segmentation.

An example script that loads a tracks object from a CSV and segmentation array
is provided in ``scripts/view_external_tracks.py``.

Once you have a Tracks object in the format described above, the following code
will view it in the Tree View and create synchronized napari layers (Points,
Labels, and Tracks) to visualize the provided tracks:

.. code-block:: python

    tracks_viewer = TracksViewer.get_instance(viewer)
    tracks_viewer.tracks_list.add_tracks(tracks, "example")

We plan to incorporate loaders from standard formats in the future to make this process easier,
and incorporate the loading into the user interface.

.. _Tracks object: https://funkelab.github.io/funtracks/latest/reference/funtracks/data_model/tracks/#funtracks.data_model.tracks.Tracks
