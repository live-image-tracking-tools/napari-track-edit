Lineage Tree View
=================

Usage Overview
**************
In addition to performing tracking with motile, the tracker also provides the ability to
visualize tracks (and segmentations) in napari, through a lineage tree view and
synchronized points, segmentation, and tracks layers. To visualize results generated
through the motile widget in the tree view, you can open the tree widget from the UI
via ``Plugins`` > ``Napari Track Edit`` > ``Widget - Lineage View``.

Clicking on individual nodes in the tree widget or in the napari Points or Labels layer will select that node,
highlighting it both in the tree view and in the napari layers. The view is centered on the selected node
only when a single node is selected. Use ``SHIFT + click`` to add/remove nodes to/from the selection without centering,
or ``CTRL(/CMD) + click`` to center the view on a node without changing the selection.
Use ``ALT(/OPTION) + click`` to adopt a node's tracklet id as the current one without selecting the node:
this works like the pipette tool of the Labels layer, but it can be used on a node in any time point,
so neither the current time point nor the camera moves.
When multiple nodes are selected, you can cycle through them using the arrow buttons in the Editing & Selection widget.
You can jump back/forward to your previous/future selection using the ``P`` (previous) and ``N`` (next) keys.
You can navigate and select nodes in the tree view using the arrow keys (make sure to click on the tree widget first).
Optionally, you can display only selected lineages in the tree view and/or napari layers (press ``Q`` in the tree widget and/or in the napari viewer).
If you used a Labels layer as input for tracking, you will also have the option to plot the object features such as area or volume in calibrated units
(make sure that your input layer has the correct scaling before starting the tracking).
Please visit :doc:`key bindings <key_bindings>` page for a complete list of available key bindings in the napari viewer and in the tree view.
