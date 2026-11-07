.. This file is generated from napari_track_edit's KEYBINDINGS table by
.. docs/source/conf.py. Edit the descriptions and defaults there.

Editing
-------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Default key binding
     - Action
   * - M
     - Start a new track: assign a new track id, and a new segmentation label if necessary
   * - D or Del
     - Delete the selected nodes
   * - S
     - Swap the incoming edges of two nodes at the same time point
   * - C
     - Connect the selected nodes into one track, keeping existing outgoing edges as divisions
   * - Shift+C
     - Connect the selected nodes into one linear track, breaking existing outgoing edges
   * - B
     - Break the edges between the selected nodes. Edges to nodes outside the selection are kept
   * - Y
     - Make or break a division between a parent node and its two children
   * - H
     - Merge each set of selected nodes that shares a time point into a single node.
   * - Z
     - Undo the last editing action
   * - R or Ctrl/Cmd+Shift+Z
     - Redo the last undone editing action

Selection
---------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Default key binding
     - Action
   * - Esc
     - Clear the selection
   * - E
     - Restore the last selection
   * - P
     - Select the previous node set from the selection history
   * - N
     - Select the next node set from the selection history

View
----

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Default key binding
     - Action
   * - /
     - Hide or show all currently active widgets
   * - Q
     - Cycle the display mode: All to Lineage to Group. Skips Group when no groups exist

Lineage view
------------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Default key binding
     - Action
   * - W
     - Switch the lineage view between the tree plot and a feature plot
   * - F
     - Flip the axes of the lineage view
