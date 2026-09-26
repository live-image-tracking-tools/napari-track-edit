.. This file is generated from motile_tracker's KEYBINDINGS table by
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
   * - A
     - Create an edge between two selected nodes, if valid
   * - B
     - Break the edge between two selected nodes, if it exists
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
