Editing Tracks
==============

Usage Overview
**************
Predicted tracks can be corrected by deleting, adding, or modifying nodes and/or edges, using the buttons in the 'Editing & Selection' widget or their corresponding keyboard shortcuts, or by editing the napari Points and Segmentation layers directly.

Editing nodes
*************

.. _delete-node:

Deleting nodes
---------------
Nodes can be deleted by selecting one or multiple nodes and clicking the 'Delete' button in the Editing & Selection menu or pressing ``D`` or ``Delete`` on the keyboard.
Deletion of a node results in its removal from the tree view and removal of its corresponding point and segmentation label in the Points and Segmentation napari layers.
If the node was connected to a predecessor and a successor, a new skip edge will be formed between the predecessor and successor nodes, leaving the remaining track intact.
If one of the two children of a dividing node is deleted, the nodes of the remaining sibling are relabeled to match the track ID of the parent.

.. figure:: images/delete_node.png
   :width: 600px
   :align: center

   Examples of deleting nodes. Deletion of a node in a linear track will create a skip edge (top), whereas deletion of one of the two children (green) of a dividing node will relabel the nodes of the remaining sibling (yellow), which is now part of the parent track (grey) (bottom).

.. _add-node:

Adding nodes
-------------
New nodes can be added in two ways, depending on what type of detections you used as input:
    - By painting on the Segmentation layer, if it exists. To continue an existing track, select a node in the track and scroll to a new time frame. The label ID will automatically be updated to create a new node using the same track ID. To start a new track, press "m" to generate a new label with a new track ID.

    - By adding a new point in the Points layer, if there are only point detections. A new, non-connected endpoint node will be created at the clicked position.

.. figure:: images/add_node.png
   :width: 600px
   :align: center

   Add a new node by painting. Press ``M`` on the segmentation layer to select a new label color and track ID for painting.

Updating nodes
---------------
Node attributes (e.g. size, position) can be updated in two ways:
    - If the source layer for tracking was a Points layer and no segmentation was provided, the points can be repositioned by clicking the 'Select points' button in the Points layer menu and clicking and dragging points to their new location.
    - If a segmentation layer was provided, node position is determined by the centroid location of each label. Therefore, nodes cannot be repositioned by moving their corresponding points in the Points layer. Instead, nodes can be updated by painting and/or erasing their labels in the Segmentation layer, which will automatically update their position and size properties.

Editing edges
*************

Connecting and disconnecting nodes
-----------------------------------
Select two or more nodes and click the 'Connect / Disconnect' button in the Edit Tracks menu, or press ``C`` on the keyboard. The selected nodes are sorted by time and connected pairwise, so that they form a single track. The nodes do not have to be in consecutive time points: skip edges spanning one or more time points are allowed.
The tracklet ID of the first (earliest) node is assigned to all of the connected nodes, unless the connection creates a division (see below).

Note that new edges are also added automatically in certain cases when a node is being added or removed (see :ref:`delete-node` and :ref:`add-node`).

.. figure:: images/add_edge.png
   :width: 600px
   :align: center

   Adding an edge between two nodes, creating a new division point.

If all selected nodes are already connected to each other, pressing ``C`` does the inverse: the edges between them are broken, splitting the selection into separate track fragments that each receive their own tracklet ID. Edges to nodes outside of the selection are kept. If even one of the selected nodes is not connected yet, the action connects the missing edges instead and never breaks any of the existing ones.

.. figure:: images/break_edge.png
   :width: 600px
   :align: center

   Examples of breaking edges. In a linear track, breaking an edge will relabel the fragment of the target node (top). If an edge between a dividing node and one of its children is deleted, both fragments maintain their track ID but the remaining sibling (magenta) is relabeled since it is now part of the same track as the parent (cyan) (bottom).

Conflicting edges
-----------------
Connecting nodes can conflict with edges that already exist: the target node may already have an incoming edge (a node in a lineage tree cannot have two parents), or the source node may already have two children, so that the new edge would create a three-way division. In both cases the user is prompted with the question whether the conflicting edges may be broken. If the answer is no, nothing is changed at all.

If a node in the selection already has exactly one child, there are two sensible things to do, and which one you want is asked when you use the button:

    - **With divisions** (``C``): the existing child edge is kept and the new edge turns that node into a division point. The existing child is relabeled with a new tracklet ID, and the newly connected node keeps its own tracklet ID within the lineage of the parent.
    - **Linear** (``Shift`` + ``C``): the existing child edge is treated as a conflict too, so that the selection becomes one linear track without divisions. Outgoing edges of the last node of the selection are never touched, since that node does not get a new child.

The question is only asked when the two modes would actually give a different result, and it is skipped entirely when you use the keyboard shortcuts, which pick a mode directly.

Selecting two or more nodes that are in the same time point is never valid, and cannot be forced: a warning is shown explaining that at most one node per time point may be selected.

Swapping nodes
--------------
The incoming edges of two nodes at the same time point can be swapped with the 'Swap' button (``S`` key). This essentially breaks two incoming edges and creates two new ones in one action.

.. figure:: images/swap_edges.png
   :width: 600px
   :align: center

   Swapping the incoming edges between two nodes at the same time point.

Undoing and redoing actions
***************************
All types of actions described above are appended to the Action History, and can be undone or redone. To undo, click 'Undo' in the Edit Tracks menu or by pressing ``Z``. Similarly, to redo an action, press 'Redo' in the Edit Tracks menu or ``R``.
