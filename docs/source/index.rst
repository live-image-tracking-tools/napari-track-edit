Napari Track Edit
=================

|source code| |tests|

.. |source code| image:: https://img.shields.io/badge/GitHub-100000?logo=github&logoColor=white
   :target: https://github.com/live-image-tracking-tools/napari-track-edit

.. |tests| image:: https://github.com/live-image-tracking-tools/napari-track-edit/workflows/tests/badge.svg
   :target: https://github.com/live-image-tracking-tools/napari-track-edit/actions

.. video:: images/results_demo_720p.mp4
   :width: 720

An application for interactive tracking with `motile`_.
Motile is a library that makes it easy to solve tracking problems using optimization
by framing the task as an Integer Linear Program (ILP).
See the `motile documentation`_ for more details on the concepts and method.

.. toctree::
   :maxdepth: 3

   getting_started
   motile
   tree_view
   editing
   view_external_tracks
   key_bindings

.. _motile: https://github.com/funkelab/motile
.. _github link: https://github.com/live-image-tracking-tools/napari-track-edit
.. _motile documentation: https://funkelab.github.io/motile
