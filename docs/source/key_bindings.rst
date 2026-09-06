Key bindings and Mouse Functions
================================

Napari viewer and layer key bindings and mouse functions
********************************************************

.. list-table::
   :widths: 25 25
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - Click on a point or label
     - Select this node (centers view if only one node selected)
   * - SHIFT + click on point or label
     - Add/remove this node to/from selection (does not center view)
   * - CTRL/CMD + click on point or label
     - Center view on this node (does not change selection)
   * - Mouse drag with point layer selection tool active
     - Select multiple nodes at once
   * - ESC
     - Clear selection
   * - E
     - Restore selection
   * - P / Mouse button 4 (Back)
     - Select previous node set
   * - N / Mouse button 5 (Forward)
     - Restore next node set
   * - Q
     - | Cycle display mode: All → Lineage → Group → All.
       | When no groups exist, alternates only between
       | All and Lineage.
   * - /
     - | Toggle between hiding/showing all currently active widgets

Tree view key and mouse functions
*********************************
.. list-table::
   :widths: 25 25
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - Click on a node
     - Select this node (centers view if only one node selected)
   * - SHIFT + click on a node
     - Add/remove this node to/from selection (does not center view)
   * - CTRL/CMD + click on a node
     - Center view on this node (does not change selection)
   * - Scroll
     - Zoom in or out
   * - Scroll + X
     - Restrict zoom to the x-axis of the tree view
   * - Scroll + Y
     - Restrict zoom to the y-axis of the tree view
   * - Mouse drag
     - Pan
   * - Right mouse drag
     - | Squeeze/zoom the axes: drag horizontally to scale the
       | x-axis, vertically to scale the y-axis
   * - SHIFT + Mouse drag
     - Rectangular selection of nodes
   * - ESC
     - Clear selection
   * - E
     - Restore selection
   * - P / Mouse button 4 (Back)
     - Select previous node set
   * - N / Mouse button 5 (Forward)
     - Restore next node set
   * - Right mouse click
     - Reset view
   * - Q
     - | Switch between viewing all lineages (vertically)\
       | or the currently selected lineages (horizontally)
   * - W
     - | Switch between plotting the lineage tree and the
       | object size
   * - Left arrow
     - Select the node to the left
   * - Right arrow
     - Select the node to the right
   * - Up arrow
     - | Select the parent node (vertical view of all
       | lineages) or the next adjacent lineage
       | (horizontal view of selected lineage)
   * - Down arrow
     - | Select the child node (vertical view of all
       | lineages) or the previous adjacent lineage
       | (horizontal view of selected lineage)
   * - /
     - | Toggle between hiding/showing all currently active widgets

Key bindings for editing the tracks
***********************************
.. list-table::
   :widths: 25 25
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - D
     - Delete selected nodes
   * - B
     - Break edge between two selected nodes, if existing
   * - A
     - Create edge between two selected nodes, if valid
   * - S
     - Swap the incoming edges of two horizontal nodes
   * - Z
     - Undo last editing action
   * - R
     - Redo last editing action
