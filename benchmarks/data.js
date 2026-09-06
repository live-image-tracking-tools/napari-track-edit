window.BENCHMARK_DATA = {
  "lastUpdate": 1788701099749,
  "repoUrl": "https://github.com/live-image-tracking-tools/napari-track-edit",
  "entries": {
    "motile_tracker benchmarks (pytest-benchmark)": [
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "8b3e4d48bd7820cfd4c5ea759bff0121b44932e1",
          "message": "Merge pull request #449 from funkelab/dependabot/github_actions/dependencies-5bb021c6cc\n\nBump the dependencies group with 2 updates",
          "timestamp": "2026-07-09T11:50:15-04:00",
          "tree_id": "6934d1314849e3011013eb86b24aebf91efea57b",
          "url": "https://github.com/funkelab/motile_tracker/commit/8b3e4d48bd7820cfd4c5ea759bff0121b44932e1"
        },
        "date": 1783616344339,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[small]",
            "value": 86.0943899862679,
            "unit": "iter/sec",
            "range": "stddev: 0.0074215813964221295",
            "extra": "mean: 11.615158666662259 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[small]",
            "value": 0.3249766872692525,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.0771438049999915 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[small]",
            "value": 14.129389346023698,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 70.77446699997836 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[small]",
            "value": 13.708240740447948,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 72.94882100001132 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[small]",
            "value": 38.95536817245519,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 25.670402999992348 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[small]",
            "value": 22.02067966430825,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 45.4118590000121 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[small]",
            "value": 17.938107787950102,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 55.747239999959675 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[small]",
            "value": 78.73325540486424,
            "unit": "iter/sec",
            "range": "stddev: 0.0019368741738160437",
            "extra": "mean: 12.701113333340194 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[small]",
            "value": 5.577762113934787,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 179.28337199998623 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[small]",
            "value": 3.7060068222325953,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 269.832206999979 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[small]",
            "value": 4.025309455224216,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 248.42810500001633 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[small]",
            "value": 5.46830172315023,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 182.8721329999894 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[small]",
            "value": 5.882189070308852,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 170.00473600000987 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[small]",
            "value": 5.539348928523935,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 180.52663100002064 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[small]",
            "value": 5.709404923457718,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 175.14960199991947 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.255342201444282,
            "unit": "iter/sec",
            "range": "stddev: 0.21819040688361985",
            "extra": "mean: 443.39169433339976 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.2112367382488996,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.734025001000077 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 1.7490467022090845,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 571.7400219999718 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 1.685832883864892,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 593.1786060000377 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 5.087842749842765,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 196.54695499991703 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.4387737787355817,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 2.2790787610000507 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.39178054094247183,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 2.552449382999953 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 2.3689067177827923,
            "unit": "iter/sec",
            "range": "stddev: 0.002047763684195715",
            "extra": "mean: 422.135659666651 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.1297463079976066,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 7.707348405000062 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.023145120333509073,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 43.20565136799996 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.18289575539097436,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 5.467595449999976 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.22976232266400867,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.352323690000048 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.23346330625475858,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.283328357000073 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.22620325811256534,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.420802814000012 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.12414135065096278,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 8.055333656000016 sec\nrounds: 1"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "45037215+TeunHuijben@users.noreply.github.com",
            "name": "Teun Huijben",
            "username": "TeunHuijben"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "af109b8ce19723c1e199a95df8865b5b414cb6b1",
          "message": "update motile to 1.0 (#456)\n\n* update motile to 1.0\n\n* upper limit on motile (<2)",
          "timestamp": "2026-07-09T13:26:51-07:00",
          "tree_id": "2c738b95ae2c2db4265665876abc788d127e5519",
          "url": "https://github.com/funkelab/motile_tracker/commit/af109b8ce19723c1e199a95df8865b5b414cb6b1"
        },
        "date": 1783629191540,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[small]",
            "value": 83.49117339662847,
            "unit": "iter/sec",
            "range": "stddev: 0.006236869658827632",
            "extra": "mean: 11.977314000001607 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[small]",
            "value": 0.33102719639800415,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.0208998260000044 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[small]",
            "value": 14.911821182210478,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 67.06089000000759 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[small]",
            "value": 14.274412010203408,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 70.05542500000672 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[small]",
            "value": 41.82952819177797,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 23.90655700000366 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[small]",
            "value": 24.832001576533614,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 40.270616000000814 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[small]",
            "value": 19.233617655566547,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 51.99229900000546 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[small]",
            "value": 82.4761903609879,
            "unit": "iter/sec",
            "range": "stddev: 0.0016312943600020962",
            "extra": "mean: 12.124711333333002 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[small]",
            "value": 5.986464245153882,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 167.04350999999917 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[small]",
            "value": 4.044125272911353,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 247.272260999992 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[small]",
            "value": 4.597495266189062,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 217.509739999997 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[small]",
            "value": 6.165490773990343,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 162.19309000000237 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[small]",
            "value": 6.392226561577939,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 156.44001200000446 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[small]",
            "value": 6.199283814098984,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 161.30895599999917 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[small]",
            "value": 6.3525530758351625,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 157.41702399999724 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.5024409017092393,
            "unit": "iter/sec",
            "range": "stddev: 0.18883199679445717",
            "extra": "mean: 399.60983666666056 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.22428354303742598,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.458641888999992 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 1.9012703647849587,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 525.9641229999943 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 1.8284291863929596,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 546.9175440000242 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 5.303788262589558,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 188.54447999999024 msec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.464546860863096,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 2.1526353620000123 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4139834541254052,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 2.415555476999998 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 2.466393323310228,
            "unit": "iter/sec",
            "range": "stddev: 0.0011787403889912465",
            "extra": "mean: 405.4503353333227 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.13532136186977986,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 7.389816257999996 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.022667139618650408,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 44.11672654 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.20265367394626077,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.934526872999982 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.23679146356392897,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.223125213000003 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.21970614100193292,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.5515341329999615 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.23674132864121863,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.224019548000001 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.13378196915123305,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 7.474848863000034 sec\nrounds: 1"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "45037215+TeunHuijben@users.noreply.github.com",
            "name": "Teun Huijben",
            "username": "TeunHuijben"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "25f0e9df98facc17d944c92901159e7c36df72ee",
          "message": "Update the benchmarks (#455)\n\n* run benchmarks base+head on same machine for fair comparison + average fast tests over multiple rounds + remove the small benchmark, only large for now\n\n* update motile to 1.0\n\n* upper limit on motile (v2)",
          "timestamp": "2026-07-24T14:07:19-07:00",
          "tree_id": "0e6e7a15feb37546cbc234f4eea1349964e7e0de",
          "url": "https://github.com/funkelab/motile_tracker/commit/25f0e9df98facc17d944c92901159e7c36df72ee"
        },
        "date": 1784927676276,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.780368749352561,
            "unit": "iter/sec",
            "range": "stddev: 0.18531539032544717",
            "extra": "mean: 359.6645230000017 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.15907837062773683,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 6.2862097220000095 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 2.287324668587119,
            "unit": "iter/sec",
            "range": "stddev: 0.008966631510129521",
            "extra": "mean: 437.19197966666457 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 1.7123675407150305,
            "unit": "iter/sec",
            "range": "stddev: 0.2104671550456624",
            "extra": "mean: 583.9867763333283 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 6.536067369442587,
            "unit": "iter/sec",
            "range": "stddev: 0.003517174927456958",
            "extra": "mean: 152.99719899999786 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5005501599365643,
            "unit": "iter/sec",
            "range": "stddev: 0.03517214329010231",
            "extra": "mean: 1.997801778999995 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4658453995608423,
            "unit": "iter/sec",
            "range": "stddev: 0.2688091268514354",
            "extra": "mean: 2.146634915666681 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 3.0471404016439076,
            "unit": "iter/sec",
            "range": "stddev: 0.006831302992689951",
            "extra": "mean: 328.17654200000374 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.1294250424438264,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 7.726479984999997 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.019029033949432995,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 52.55127520700003 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.22521683706470735,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.44016536700002 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.25814744707895926,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.8737551400000143 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.2662269410480112,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.756193855000049 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.23367160429254413,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.279510139999957 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.13241766040925632,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 7.551862771999993 sec\nrounds: 1"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "45037215+TeunHuijben@users.noreply.github.com",
            "name": "Teun Huijben",
            "username": "TeunHuijben"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b99f6770180dd452affe539c7fa5f681aa60b730",
          "message": "Benchmark uses separate uvs for base vs main (#466)\n\n* make benchmark comparison use separate uvs\n\n* do all benchmarks 3 times + take the min + report mean/std in table\n\n* precommit fixes",
          "timestamp": "2026-07-27T15:15:07-07:00",
          "tree_id": "8598157a8a067b1578c03bd6ad3b8b75da3d96e6",
          "url": "https://github.com/funkelab/motile_tracker/commit/b99f6770180dd452affe539c7fa5f681aa60b730"
        },
        "date": 1785191145867,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.5802037921845247,
            "unit": "iter/sec",
            "range": "stddev: 0.17427361160577526",
            "extra": "mean: 387.56628566666507 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.18375810779843166,
            "unit": "iter/sec",
            "range": "stddev: 1.3775342841300475",
            "extra": "mean: 5.441936750333336 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 1.4845460823766308,
            "unit": "iter/sec",
            "range": "stddev: 0.22135596065555477",
            "extra": "mean: 673.6065736666698 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 1.470213179587849,
            "unit": "iter/sec",
            "range": "stddev: 0.20582548886304558",
            "extra": "mean: 680.1734699999997 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 5.317385939891561,
            "unit": "iter/sec",
            "range": "stddev: 0.0033118569412281464",
            "extra": "mean: 188.06233199999647 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.46380369111015834,
            "unit": "iter/sec",
            "range": "stddev: 0.050943244353848005",
            "extra": "mean: 2.1560846089999948 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4360654125282766,
            "unit": "iter/sec",
            "range": "stddev: 0.29486139531305816",
            "extra": "mean: 2.293233930666664 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 2.426361921475708,
            "unit": "iter/sec",
            "range": "stddev: 0.00373502104588687",
            "extra": "mean: 412.1396693333376 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.14112009680192888,
            "unit": "iter/sec",
            "range": "stddev: 0.06950303626878884",
            "extra": "mean: 7.08616293966666 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.022383924970601324,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 44.674917437999966 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.1926902474819029,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 5.189676244999987 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.23417751853770044,
            "unit": "iter/sec",
            "range": "stddev: 0.12270870028897254",
            "extra": "mean: 4.270264738666659 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.2396212397544185,
            "unit": "iter/sec",
            "range": "stddev: 0.10112263143424209",
            "extra": "mean: 4.1732527593333275 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.2311269931486551,
            "unit": "iter/sec",
            "range": "stddev: 0.12400382353632634",
            "extra": "mean: 4.326625749666657 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.1303214472985013,
            "unit": "iter/sec",
            "range": "stddev: 0.2796366522738499",
            "extra": "mean: 7.673334057666655 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "863efae9aaf08bd20a6b13dbe4188199298528ba",
          "message": "Merge pull request #452 from funkelab/speedup-colormap\n\nSpeedup colormap",
          "timestamp": "2026-07-29T10:53:00-04:00",
          "tree_id": "ef961442e403cc6e651926b1c330a53d06d703a3",
          "url": "https://github.com/funkelab/motile_tracker/commit/863efae9aaf08bd20a6b13dbe4188199298528ba"
        },
        "date": 1785337346623,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.555861329054773,
            "unit": "iter/sec",
            "range": "stddev: 0.16868805763606767",
            "extra": "mean: 391.2575336666748 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.21786740822682504,
            "unit": "iter/sec",
            "range": "stddev: 1.533312423617969",
            "extra": "mean: 4.58994765733333 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.0533653486017736,
            "unit": "iter/sec",
            "range": "stddev: 0.006406285840962285",
            "extra": "mean: 327.5074830000051 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 2.981179216389873,
            "unit": "iter/sec",
            "range": "stddev: 0.014536680991810496",
            "extra": "mean: 335.43773366667057 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.3538750521482,
            "unit": "iter/sec",
            "range": "stddev: 0.0004975373594065987",
            "extra": "mean: 96.58219700000359 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.4984361104320328,
            "unit": "iter/sec",
            "range": "stddev: 0.22526116356025022",
            "extra": "mean: 2.0062751856666714 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.38550489336742577,
            "unit": "iter/sec",
            "range": "stddev: 0.17032652918648847",
            "extra": "mean: 2.5940007953333484 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 5.936473171327808,
            "unit": "iter/sec",
            "range": "stddev: 0.006868508242176389",
            "extra": "mean: 168.4501843333237 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.14775435448298674,
            "unit": "iter/sec",
            "range": "stddev: 0.31620378282505085",
            "extra": "mean: 6.767990043333346 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.022107515665089627,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 45.233485985000016 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.2260177656323906,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.424430961000041 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.26153552187248846,
            "unit": "iter/sec",
            "range": "stddev: 0.19324290738367084",
            "extra": "mean: 3.8235723883333512 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.268512007057594,
            "unit": "iter/sec",
            "range": "stddev: 0.36856091649699696",
            "extra": "mean: 3.724228242000019 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.24278699878784343,
            "unit": "iter/sec",
            "range": "stddev: 0.3283054719820762",
            "extra": "mean: 4.118836696333308 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.14055007325226637,
            "unit": "iter/sec",
            "range": "stddev: 0.16554991422178206",
            "extra": "mean: 7.114902019333347 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b45a47c8220643c0532298c5aca0b636c9c6b338",
          "message": "Merge pull request #457 from funkelab/pre-commit-ci-update-config\n\n[pre-commit.ci] pre-commit autoupdate",
          "timestamp": "2026-07-29T10:54:11-04:00",
          "tree_id": "516023d82db9af983be5a93166d9899267916ca1",
          "url": "https://github.com/funkelab/motile_tracker/commit/b45a47c8220643c0532298c5aca0b636c9c6b338"
        },
        "date": 1785337428832,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.6499213449463115,
            "unit": "iter/sec",
            "range": "stddev: 0.15574423912449545",
            "extra": "mean: 377.3696913333329 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.21103341111262097,
            "unit": "iter/sec",
            "range": "stddev: 1.372547012331199",
            "extra": "mean: 4.738586154333333 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.155490047488728,
            "unit": "iter/sec",
            "range": "stddev: 0.004879969497785679",
            "extra": "mean: 316.90798733332787 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.066103414339387,
            "unit": "iter/sec",
            "range": "stddev: 0.016640544504701378",
            "extra": "mean: 326.1468596666551 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.770582433138486,
            "unit": "iter/sec",
            "range": "stddev: 0.00028957098784136503",
            "extra": "mean: 92.84548966667217 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.4926212086922272,
            "unit": "iter/sec",
            "range": "stddev: 0.05039672067323379",
            "extra": "mean: 2.0299572619999915 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.3854251897706158,
            "unit": "iter/sec",
            "range": "stddev: 0.0394839948003764",
            "extra": "mean: 2.594537218999998 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.522778960660822,
            "unit": "iter/sec",
            "range": "stddev: 0.006814653001995327",
            "extra": "mean: 153.30888966666598 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.13962777022483408,
            "unit": "iter/sec",
            "range": "stddev: 0.16346477814243815",
            "extra": "mean: 7.161899086333335 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.02005753335360352,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 49.85657918999999 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.23269335434209434,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.297501330999978 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.26372833088080944,
            "unit": "iter/sec",
            "range": "stddev: 0.11136516066385047",
            "extra": "mean: 3.7917807186666814 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.25835687254376216,
            "unit": "iter/sec",
            "range": "stddev: 0.2893897868223169",
            "extra": "mean: 3.8706150533333052 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.2516230381910731,
            "unit": "iter/sec",
            "range": "stddev: 0.3471009412453733",
            "extra": "mean: 3.974198893666634 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.13857151095516218,
            "unit": "iter/sec",
            "range": "stddev: 0.13707982308293143",
            "extra": "mean: 7.21649055499995 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "48103308bc88895ea2c9edff9039222838f5f68a",
          "message": "Merge pull request #464 from funkelab/fix_colliding_attributes_in_import_widget\n\nFix colliding features widges in import menu",
          "timestamp": "2026-07-29T11:17:14-04:00",
          "tree_id": "5fedd8cf7052bc695569266e87df74249dda2687",
          "url": "https://github.com/funkelab/motile_tracker/commit/48103308bc88895ea2c9edff9039222838f5f68a"
        },
        "date": 1785338821172,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.27742372762941,
            "unit": "iter/sec",
            "range": "stddev: 0.19742428794119937",
            "extra": "mean: 439.0926413333318 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.21523757580600525,
            "unit": "iter/sec",
            "range": "stddev: 1.5151917525680993",
            "extra": "mean: 4.646028911333332 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.143701464124737,
            "unit": "iter/sec",
            "range": "stddev: 0.008748488232679822",
            "extra": "mean: 318.09636233331656 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.1564904175779684,
            "unit": "iter/sec",
            "range": "stddev: 0.015177754819868362",
            "extra": "mean: 316.8075513333311 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.986020055111748,
            "unit": "iter/sec",
            "range": "stddev: 0.0009080350670616505",
            "extra": "mean: 91.02477466666414 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5899711459763478,
            "unit": "iter/sec",
            "range": "stddev: 0.09523388632729893",
            "extra": "mean: 1.694998148333326 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4088871029572519,
            "unit": "iter/sec",
            "range": "stddev: 0.041861078752342046",
            "extra": "mean: 2.4456628560000033 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.558803097839976,
            "unit": "iter/sec",
            "range": "stddev: 0.008290026955072229",
            "extra": "mean: 152.46684266666458 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.14641492425314342,
            "unit": "iter/sec",
            "range": "stddev: 0.3833789824299775",
            "extra": "mean: 6.82990484133335 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.021541761798276743,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 46.421458438 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.22564298654569356,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.43177966799999 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.2626874468895398,
            "unit": "iter/sec",
            "range": "stddev: 0.14850272087579286",
            "extra": "mean: 3.806805433000003 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.2490767696172377,
            "unit": "iter/sec",
            "range": "stddev: 0.5582789725186729",
            "extra": "mean: 4.014826439000008 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.2416395068297768,
            "unit": "iter/sec",
            "range": "stddev: 0.5007877985465562",
            "extra": "mean: 4.138396130333319 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.1377240845364146,
            "unit": "iter/sec",
            "range": "stddev: 0.12984051617266024",
            "extra": "mean: 7.2608941519999535 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "45037215+TeunHuijben@users.noreply.github.com",
            "name": "Teun Huijben",
            "username": "TeunHuijben"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "e85a0dd57646074d207b0bc2386b8fabe3e45037",
          "message": "make table lazy (QTableView) to fix OOM on large datasets (#461)\n\n* make table lazy (QTableView) to fix OOM on large datasets\n\n* remove unused special selection from table view\n\n* Use QStyle selected flag instead of iterating rows\n\n---------\n\nCo-authored-by: AnniekStok <anniek.stokkermans@gmail.com>\nCo-authored-by: Caroline Malin-Mayor <malinmayorc@janelia.hhmi.org>",
          "timestamp": "2026-07-29T11:11:24-07:00",
          "tree_id": "414e43ee39c59b52c56887a4fa01a1b25d31a7a7",
          "url": "https://github.com/funkelab/motile_tracker/commit/e85a0dd57646074d207b0bc2386b8fabe3e45037"
        },
        "date": 1785349224556,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.5281860851209985,
            "unit": "iter/sec",
            "range": "stddev: 0.1587341178063402",
            "extra": "mean: 395.5405046666651 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.22812761143950305,
            "unit": "iter/sec",
            "range": "stddev: 1.4047125924455603",
            "extra": "mean: 4.383511464000004 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.4037364410131348,
            "unit": "iter/sec",
            "range": "stddev: 0.006527046342932577",
            "extra": "mean: 293.79478033332873 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 2.3012409168563774,
            "unit": "iter/sec",
            "range": "stddev: 0.21092738361786834",
            "extra": "mean: 434.54815733332924 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 11.34590267477973,
            "unit": "iter/sec",
            "range": "stddev: 0.0009807919799373994",
            "extra": "mean: 88.13754433332595 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5004266696168248,
            "unit": "iter/sec",
            "range": "stddev: 0.020748335440350246",
            "extra": "mean: 1.998294776666673 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.43711674540831896,
            "unit": "iter/sec",
            "range": "stddev: 0.05108846092548533",
            "extra": "mean: 2.287718350999986 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.779540961620329,
            "unit": "iter/sec",
            "range": "stddev: 0.005401390272355007",
            "extra": "mean: 147.50261200000145 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.14976131129068063,
            "unit": "iter/sec",
            "range": "stddev: 0.2843013636920345",
            "extra": "mean: 6.677291961333329 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.02090115998588049,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 47.84423451499998 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.25428495307426235,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.932596042 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.2895360752396501,
            "unit": "iter/sec",
            "range": "stddev: 0.09669504524185055",
            "extra": "mean: 3.4538010476666727 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.275779457510947,
            "unit": "iter/sec",
            "range": "stddev: 0.36289103084257224",
            "extra": "mean: 3.626085891333313 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.2590941719921866,
            "unit": "iter/sec",
            "range": "stddev: 0.35278534394873484",
            "extra": "mean: 3.8596005163333302 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.1480490101589305,
            "unit": "iter/sec",
            "range": "stddev: 0.13230432354701793",
            "extra": "mean: 6.754519999333335 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "c7c186143e82debee902642db7b3eb153a05e9f7",
          "message": "Merge pull request #469 from funkelab/dependabot/github_actions/dependencies-9e9b9688a3\n\nBump the dependencies group with 3 updates",
          "timestamp": "2026-08-03T11:04:02-04:00",
          "tree_id": "2666251001c57495447516bd8c0f94adf1b02de7",
          "url": "https://github.com/funkelab/motile_tracker/commit/c7c186143e82debee902642db7b3eb153a05e9f7"
        },
        "date": 1785769859677,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.4635207270484485,
            "unit": "iter/sec",
            "range": "stddev: 0.18669631107808302",
            "extra": "mean: 405.9231119999964 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.22458141592669967,
            "unit": "iter/sec",
            "range": "stddev: 1.3719564808857305",
            "extra": "mean: 4.452728182666665 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.41971121865606,
            "unit": "iter/sec",
            "range": "stddev: 0.0054949893270443235",
            "extra": "mean: 292.422352666667 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.3161281770820277,
            "unit": "iter/sec",
            "range": "stddev: 0.011868865413654974",
            "extra": "mean: 301.556498000006 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 11.338411576072062,
            "unit": "iter/sec",
            "range": "stddev: 0.0005097225785094128",
            "extra": "mean: 88.19577533332297 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.4926509758733269,
            "unit": "iter/sec",
            "range": "stddev: 0.048031626577547754",
            "extra": "mean: 2.029834606999998 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.43059085075867126,
            "unit": "iter/sec",
            "range": "stddev: 0.06482650979010589",
            "extra": "mean: 2.3223902649999864 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.728528926088352,
            "unit": "iter/sec",
            "range": "stddev: 0.004967028660395058",
            "extra": "mean: 148.62089633333161 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.30128975642894207,
            "unit": "iter/sec",
            "range": "stddev: 0.0788185359138268",
            "extra": "mean: 3.3190640526666755 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.2532302145561644,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.9489758429999995 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.22990989455789398,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.349530071000004 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.2807884212592801,
            "unit": "iter/sec",
            "range": "stddev: 0.06545242056863163",
            "extra": "mean: 3.561400415000018 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.2691746879441361,
            "unit": "iter/sec",
            "range": "stddev: 0.3475522563724837",
            "extra": "mean: 3.715059568333326 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.2837813117149218,
            "unit": "iter/sec",
            "range": "stddev: 0.1558697629793096",
            "extra": "mean: 3.52384022033336 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.25631425559267773,
            "unit": "iter/sec",
            "range": "stddev: 0.174615515334436",
            "extra": "mean: 3.901460719333348 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "9cb42698e483a271c158841f0124f19dc3841429",
          "message": "Merge pull request #425 from funkelab/fix_out_of_slice_points\n\nRestrict out of slice point display to the last non-displayed dim",
          "timestamp": "2026-08-04T10:12:27-04:00",
          "tree_id": "dd4c5c9bfa3a9be54d7196aba00eb7a551f0ded2",
          "url": "https://github.com/funkelab/motile_tracker/commit/9cb42698e483a271c158841f0124f19dc3841429"
        },
        "date": 1785853176412,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.6274206416518675,
            "unit": "iter/sec",
            "range": "stddev: 0.15276365148359744",
            "extra": "mean: 380.6014096666672 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.21511300138254377,
            "unit": "iter/sec",
            "range": "stddev: 1.455226449873429",
            "extra": "mean: 4.648719480333322 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.0911721854448406,
            "unit": "iter/sec",
            "range": "stddev: 0.005039533400161906",
            "extra": "mean: 323.5018756666553 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 2.305939114600167,
            "unit": "iter/sec",
            "range": "stddev: 0.18840608910155288",
            "extra": "mean: 433.66279433331556 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.231553318511843,
            "unit": "iter/sec",
            "range": "stddev: 0.000996468585548065",
            "extra": "mean: 97.73687033333545 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5243457844613837,
            "unit": "iter/sec",
            "range": "stddev: 0.18779580596835327",
            "extra": "mean: 1.9071384373333256 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.41466454518350987,
            "unit": "iter/sec",
            "range": "stddev: 0.05773861930795923",
            "extra": "mean: 2.4115879006666696 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.135335726399482,
            "unit": "iter/sec",
            "range": "stddev: 0.006219122670454036",
            "extra": "mean: 162.99026566665967 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.2882838710521809,
            "unit": "iter/sec",
            "range": "stddev: 0.06468611772529727",
            "extra": "mean: 3.4688031500000043 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.2383495770699339,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.195518248000042 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.2220046304025219,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.504410553000071 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.274801132244089,
            "unit": "iter/sec",
            "range": "stddev: 0.08679496463369453",
            "extra": "mean: 3.6389951956666664 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.2640259076541328,
            "unit": "iter/sec",
            "range": "stddev: 0.35842670860528547",
            "extra": "mean: 3.7875071006667063 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.27175285543089955,
            "unit": "iter/sec",
            "range": "stddev: 0.15207674287394224",
            "extra": "mean: 3.67981414 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.2510195257609845,
            "unit": "iter/sec",
            "range": "stddev: 0.14196347488931582",
            "extra": "mean: 3.983753841333358 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "9aed13ff1928d265784f7edbb6897dc345f2ce9f",
          "message": "Merge pull request #439 from funkelab/test-speedup\n\nTest speedup",
          "timestamp": "2026-08-04T10:13:40-04:00",
          "tree_id": "01b98f86d9f773a1841d7d6f62af13a961581219",
          "url": "https://github.com/funkelab/motile_tracker/commit/9aed13ff1928d265784f7edbb6897dc345f2ce9f"
        },
        "date": 1785853324335,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.7832428632664215,
            "unit": "iter/sec",
            "range": "stddev: 0.1347581410456705",
            "extra": "mean: 359.29311566666416 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.2214866628329009,
            "unit": "iter/sec",
            "range": "stddev: 1.3619751949940853",
            "extra": "mean: 4.514944544333322 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.174731181780178,
            "unit": "iter/sec",
            "range": "stddev: 0.005007057995025103",
            "extra": "mean: 314.9872989999949 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.154385602394185,
            "unit": "iter/sec",
            "range": "stddev: 0.009630914441870643",
            "extra": "mean: 317.0189463333202 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.5785244451371,
            "unit": "iter/sec",
            "range": "stddev: 0.0011252244013182928",
            "extra": "mean: 94.53114233334266 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.47391907137375094,
            "unit": "iter/sec",
            "range": "stddev: 0.03120855486159729",
            "extra": "mean: 2.110064904333342 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4159812807136941,
            "unit": "iter/sec",
            "range": "stddev: 0.04641622712958973",
            "extra": "mean: 2.4039543276666486 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.154747587646847,
            "unit": "iter/sec",
            "range": "stddev: 0.003222690396401028",
            "extra": "mean: 162.47619999999566 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.2907050252557328,
            "unit": "iter/sec",
            "range": "stddev: 0.10260349320046236",
            "extra": "mean: 3.4399130153333317 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.24313824945753906,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.112886402000015 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.25312706980423105,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.9505849799999737 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.275092088915297,
            "unit": "iter/sec",
            "range": "stddev: 0.19299214219136976",
            "extra": "mean: 3.635146339333327 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.292948488149156,
            "unit": "iter/sec",
            "range": "stddev: 0.07798921482920113",
            "extra": "mean: 3.413569417333349 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.28539049239773046,
            "unit": "iter/sec",
            "range": "stddev: 0.08748575652051262",
            "extra": "mean: 3.503970968333325 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.2730748031132039,
            "unit": "iter/sec",
            "range": "stddev: 0.22845635813063747",
            "extra": "mean: 3.6620002599999943 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "e01d537669751a5368ea44d329a68c21f39c73e0",
          "message": "Merge pull request #433 from funkelab/feature_widget\n\nAdd a feature widget to enable/disable regionprops features",
          "timestamp": "2026-08-18T10:14:27-04:00",
          "tree_id": "faf1a38526da5a125c7d7342d215c9a28065c6cb",
          "url": "https://github.com/funkelab/motile_tracker/commit/e01d537669751a5368ea44d329a68c21f39c73e0"
        },
        "date": 1787062861934,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 3.1321377340654455,
            "unit": "iter/sec",
            "range": "stddev: 0.1361659228656029",
            "extra": "mean: 319.27076166667234 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.2477566177136673,
            "unit": "iter/sec",
            "range": "stddev: 1.300093860153233",
            "extra": "mean: 4.0362191299999965 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.7434770473971284,
            "unit": "iter/sec",
            "range": "stddev: 0.0012918440846228943",
            "extra": "mean: 267.1313293333289 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.6310633885398964,
            "unit": "iter/sec",
            "range": "stddev: 0.012401551472657214",
            "extra": "mean: 275.4014163333333 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 12.422501036791589,
            "unit": "iter/sec",
            "range": "stddev: 0.0012679175920542207",
            "extra": "mean: 80.4990876666712 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5099146076193579,
            "unit": "iter/sec",
            "range": "stddev: 0.012520058458925025",
            "extra": "mean: 1.961112674666661 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4504368928410419,
            "unit": "iter/sec",
            "range": "stddev: 0.010374372131089967",
            "extra": "mean: 2.2200668193333306 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 8.71171632630544,
            "unit": "iter/sec",
            "range": "stddev: 0.006548009100444242",
            "extra": "mean: 114.7879433333306 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.32134022025480236,
            "unit": "iter/sec",
            "range": "stddev: 0.031344239629398744",
            "extra": "mean: 3.1119664983333357 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.28439597184332444,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.5162242050000145 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.28438068104798137,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.516413268000008 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.3022092887051622,
            "unit": "iter/sec",
            "range": "stddev: 0.22290959357977058",
            "extra": "mean: 3.3089651356666536 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.3184372149023634,
            "unit": "iter/sec",
            "range": "stddev: 0.06544951811923959",
            "extra": "mean: 3.1403364720000204 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.31456116356429575,
            "unit": "iter/sec",
            "range": "stddev: 0.09542242562262984",
            "extra": "mean: 3.179031984333316 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.31153571718917633,
            "unit": "iter/sec",
            "range": "stddev: 0.10544765387093893",
            "extra": "mean: 3.2099048193333224 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "0270d1202a8aca70c9e824b7f6c3da0bcda44bee",
          "message": "Merge pull request #470 from funkelab/pre-commit-ci-update-config\n\n[pre-commit.ci] pre-commit autoupdate",
          "timestamp": "2026-08-18T10:19:43-04:00",
          "tree_id": "9734238646a4c1e5dbbf755b0ea5e63c663f50a8",
          "url": "https://github.com/funkelab/motile_tracker/commit/0270d1202a8aca70c9e824b7f6c3da0bcda44bee"
        },
        "date": 1787063191113,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.7995007866742108,
            "unit": "iter/sec",
            "range": "stddev: 0.13305847821507225",
            "extra": "mean: 357.2065436666634 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.2235510759890194,
            "unit": "iter/sec",
            "range": "stddev: 1.4043364975892678",
            "extra": "mean: 4.473250668000001 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.2035964752955097,
            "unit": "iter/sec",
            "range": "stddev: 0.005338598359229355",
            "extra": "mean: 312.14917600000075 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.1081870295971123,
            "unit": "iter/sec",
            "range": "stddev: 0.01311813990366593",
            "extra": "mean: 321.7309609999954 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.731793255180351,
            "unit": "iter/sec",
            "range": "stddev: 0.0008747098974232918",
            "extra": "mean: 93.18107199999304 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.4849802198982449,
            "unit": "iter/sec",
            "range": "stddev: 0.020727917212129424",
            "extra": "mean: 2.0619397636666768 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.42668041346760693,
            "unit": "iter/sec",
            "range": "stddev: 0.045155485997733155",
            "extra": "mean: 2.3436744889999943 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 7.271627520594818,
            "unit": "iter/sec",
            "range": "stddev: 0.004737910840642377",
            "extra": "mean: 137.52079533333963 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.2984715793344491,
            "unit": "iter/sec",
            "range": "stddev: 0.09394264976479674",
            "extra": "mean: 3.3504027493333317 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.25178736308019156,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.971605197999992 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.25338395507245876,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.9465798050000274 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.2760667284643879,
            "unit": "iter/sec",
            "range": "stddev: 0.1729509044244267",
            "extra": "mean: 3.622312639999999 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.29352072472338114,
            "unit": "iter/sec",
            "range": "stddev: 0.15154890971187152",
            "extra": "mean: 3.4069144553333217 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.2831986891802031,
            "unit": "iter/sec",
            "range": "stddev: 0.13407331641771605",
            "extra": "mean: 3.53108979033334 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.2653595420993461,
            "unit": "iter/sec",
            "range": "stddev: 0.15969487252119027",
            "extra": "mean: 3.7684719836666623 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "59f1de460933a3f234d3c6aeb6bba57e607acbbe",
          "message": "Merge pull request #473 from funkelab/fix_giant_point_bug\n\nFix increasing point size bug",
          "timestamp": "2026-08-18T10:34:44-04:00",
          "tree_id": "f9772b331ccba87ecef3ba94da60d07706849b80",
          "url": "https://github.com/funkelab/motile_tracker/commit/59f1de460933a3f234d3c6aeb6bba57e607acbbe"
        },
        "date": 1787064104584,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.715480024555085,
            "unit": "iter/sec",
            "range": "stddev: 0.14168441029008583",
            "extra": "mean: 368.2590153333365 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.22294463069994438,
            "unit": "iter/sec",
            "range": "stddev: 1.4025947151912892",
            "extra": "mean: 4.485418629999998 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.1841203519715844,
            "unit": "iter/sec",
            "range": "stddev: 0.00845287567953801",
            "extra": "mean: 314.05848066666425 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.1380053586085603,
            "unit": "iter/sec",
            "range": "stddev: 0.008454563648446737",
            "extra": "mean: 318.6737706666681 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.59477401470672,
            "unit": "iter/sec",
            "range": "stddev: 0.0009884212230130455",
            "extra": "mean: 94.38615666666313 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.4831141020209886,
            "unit": "iter/sec",
            "range": "stddev: 0.03292448808806189",
            "extra": "mean: 2.0699043886666666 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.42682740296150434,
            "unit": "iter/sec",
            "range": "stddev: 0.024026285596193672",
            "extra": "mean: 2.3428673816666596 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 7.387873978059864,
            "unit": "iter/sec",
            "range": "stddev: 0.0035499970530683505",
            "extra": "mean: 135.35693799999157 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.29949759793082903,
            "unit": "iter/sec",
            "range": "stddev: 0.07417704088430582",
            "extra": "mean: 3.3389249426666745 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.24891568568687863,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.017424604000013 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.25630979499746187,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.9015286169999968 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.27689303686566624,
            "unit": "iter/sec",
            "range": "stddev: 0.21236328623062434",
            "extra": "mean: 3.6115028796666593 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.2894812550264845,
            "unit": "iter/sec",
            "range": "stddev: 0.08435008989184396",
            "extra": "mean: 3.45445510766668 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.2740857446092102,
            "unit": "iter/sec",
            "range": "stddev: 0.10983748083541915",
            "extra": "mean: 3.648493289666684 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.2782065260539366,
            "unit": "iter/sec",
            "range": "stddev: 0.11631910797847947",
            "extra": "mean: 3.5944519856666752 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "f56af1595523464e5c4fa4624e9f151d7c579be7",
          "message": "Merge pull request #476 from funkelab/widget_cleanup\n\nClean up table and tree view widgets when their menus are closed",
          "timestamp": "2026-08-18T10:45:35-04:00",
          "tree_id": "64ed39b5edc64b35e81a67f58fdc56dd4bf5aeb4",
          "url": "https://github.com/funkelab/motile_tracker/commit/f56af1595523464e5c4fa4624e9f151d7c579be7"
        },
        "date": 1787064713283,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 3.695001837524302,
            "unit": "iter/sec",
            "range": "stddev: 0.11689500209493275",
            "extra": "mean: 270.6358600000082 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.28886005426417705,
            "unit": "iter/sec",
            "range": "stddev: 1.0248461289300543",
            "extra": "mean: 3.461883999666668 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 4.449375948178759,
            "unit": "iter/sec",
            "range": "stddev: 0.0035343463777436296",
            "extra": "mean: 224.75061933333032 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.0368490750502635,
            "unit": "iter/sec",
            "range": "stddev: 0.16317974978405747",
            "extra": "mean: 329.2886723333292 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 14.596028350623902,
            "unit": "iter/sec",
            "range": "stddev: 0.0006829496171565345",
            "extra": "mean: 68.5117880000045 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.6242099935900143,
            "unit": "iter/sec",
            "range": "stddev: 0.2053483909638828",
            "extra": "mean: 1.6020249759999956 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.5596710626160218,
            "unit": "iter/sec",
            "range": "stddev: 0.243838724447201",
            "extra": "mean: 1.7867638096666763 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 10.236320960334524,
            "unit": "iter/sec",
            "range": "stddev: 0.007831196426459195",
            "extra": "mean: 97.69134866667173 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.35403714723367347,
            "unit": "iter/sec",
            "range": "stddev: 0.062206862834406476",
            "extra": "mean: 2.824562359666667 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.3132511404065951,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.192326766000008 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.3814512389591949,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 2.621567051999989 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.33580634047270325,
            "unit": "iter/sec",
            "range": "stddev: 0.03391140268365889",
            "extra": "mean: 2.9779068453333366 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.3961085235491289,
            "unit": "iter/sec",
            "range": "stddev: 0.41405690487392854",
            "extra": "mean: 2.5245606709999797 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.3896453391274017,
            "unit": "iter/sec",
            "range": "stddev: 0.4301805786830596",
            "extra": "mean: 2.5664364476666606 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.38601776756713496,
            "unit": "iter/sec",
            "range": "stddev: 0.48077786957850815",
            "extra": "mean: 2.590554331999973 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "9546021c77ceeb365e7317cfd750b6838ede95ab",
          "message": "Merge pull request #447 from funkelab/deprecate-motile-run\n\nDeprecate motile run",
          "timestamp": "2026-08-18T10:53:47-04:00",
          "tree_id": "374b781cd9180cfdbb0a36398a32afd410ceb787",
          "url": "https://github.com/funkelab/motile_tracker/commit/9546021c77ceeb365e7317cfd750b6838ede95ab"
        },
        "date": 1787065201392,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.530274760706085,
            "unit": "iter/sec",
            "range": "stddev: 0.17961037211021574",
            "extra": "mean: 395.2139963333252 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.24784734397299063,
            "unit": "iter/sec",
            "range": "stddev: 1.346353845887357",
            "extra": "mean: 4.034741643666659 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 4.077599662893552,
            "unit": "iter/sec",
            "range": "stddev: 0.01191787331070136",
            "extra": "mean: 245.24231966665866 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.809615636982913,
            "unit": "iter/sec",
            "range": "stddev: 0.02646721934198642",
            "extra": "mean: 262.4936726666647 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 13.179196480208137,
            "unit": "iter/sec",
            "range": "stddev: 0.0038898492766364498",
            "extra": "mean: 75.87715999998561 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5807435200593517,
            "unit": "iter/sec",
            "range": "stddev: 0.25158162659699557",
            "extra": "mean: 1.721930534666664 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.5178688172941073,
            "unit": "iter/sec",
            "range": "stddev: 0.2473050107635835",
            "extra": "mean: 1.9309909510000125 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 9.360434724798079,
            "unit": "iter/sec",
            "range": "stddev: 0.010659164869556537",
            "extra": "mean: 106.83264499999723 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.32060275475764666,
            "unit": "iter/sec",
            "range": "stddev: 0.12611209352233768",
            "extra": "mean: 3.119124789666671 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.2731177981313441,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.6614237770000386 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.3346703140179834,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 2.988015243999996 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.3027730030152808,
            "unit": "iter/sec",
            "range": "stddev: 0.03737525141681186",
            "extra": "mean: 3.3028043783333296 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.35642167932996394,
            "unit": "iter/sec",
            "range": "stddev: 0.3820589911180662",
            "extra": "mean: 2.8056654743333715 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.3544565440418812,
            "unit": "iter/sec",
            "range": "stddev: 0.5219281809150089",
            "extra": "mean: 2.8212203070000137 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.35553362072183725,
            "unit": "iter/sec",
            "range": "stddev: 0.5137571858190542",
            "extra": "mean: 2.8126735186666942 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "45037215+TeunHuijben@users.noreply.github.com",
            "name": "Teun Huijben",
            "username": "TeunHuijben"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "cfa7568c1b9e3b8237f82e8823061733973b75c8",
          "message": "0.4.0 compatibility (#481)",
          "timestamp": "2026-08-19T21:56:21-07:00",
          "tree_id": "2ef95802e18d5636155d5ec3e48433aadeca4be7",
          "url": "https://github.com/funkelab/motile_tracker/commit/cfa7568c1b9e3b8237f82e8823061733973b75c8"
        },
        "date": 1787202181957,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.7534781091074265,
            "unit": "iter/sec",
            "range": "stddev: 0.1374455330726083",
            "extra": "mean: 363.1770293333337 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.23180588958491283,
            "unit": "iter/sec",
            "range": "stddev: 1.43337037835164",
            "extra": "mean: 4.313954238999997 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.2364153969238716,
            "unit": "iter/sec",
            "range": "stddev: 0.008402825495549715",
            "extra": "mean: 308.9838223333364 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.123618634972803,
            "unit": "iter/sec",
            "range": "stddev: 0.019853945967104325",
            "extra": "mean: 320.14151433332927 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.206995417386606,
            "unit": "iter/sec",
            "range": "stddev: 0.0042550364209026185",
            "extra": "mean: 97.97202399999112 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5361355111098234,
            "unit": "iter/sec",
            "range": "stddev: 0.19763340749653585",
            "extra": "mean: 1.86520008333333 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4403477351146383,
            "unit": "iter/sec",
            "range": "stddev: 0.1736552457483544",
            "extra": "mean: 2.2709325386666612 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 7.311759322892978,
            "unit": "iter/sec",
            "range": "stddev: 0.005398871408881243",
            "extra": "mean: 136.7659896666756 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.2970863372447139,
            "unit": "iter/sec",
            "range": "stddev: 0.07416157996530157",
            "extra": "mean: 3.3660248709999983 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.25068094759526016,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.9891344339999932 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.30056371750139416,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.3270815530000277 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.28368749338635674,
            "unit": "iter/sec",
            "range": "stddev: 0.03676810417751313",
            "extra": "mean: 3.5250055900000157 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.324011341803172,
            "unit": "iter/sec",
            "range": "stddev: 0.2856657472299455",
            "extra": "mean: 3.086311715000003 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.31901585643186403,
            "unit": "iter/sec",
            "range": "stddev: 0.3678968883376124",
            "extra": "mean: 3.1346404256666838 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.31502582561556874,
            "unit": "iter/sec",
            "range": "stddev: 0.4178884765296609",
            "extra": "mean: 3.1743429226666535 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "32863964+AnniekStok@users.noreply.github.com",
            "name": "Anniek Stokkermans",
            "username": "AnniekStok"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "c5858c454f3b279b99f33f001fd033769a5170af",
          "message": "Merge pull request #474 from funkelab/optimize_ortho_view_integration\n\nOptimize ortho view integration",
          "timestamp": "2026-08-20T08:18:29+02:00",
          "tree_id": "fa93681689d5292612dda323d0ee5cc68ebf29f0",
          "url": "https://github.com/funkelab/motile_tracker/commit/c5858c454f3b279b99f33f001fd033769a5170af"
        },
        "date": 1787207222040,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 1.9768626115337347,
            "unit": "iter/sec",
            "range": "stddev: 0.2455666638389296",
            "extra": "mean: 505.8520476666596 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.1846537775447289,
            "unit": "iter/sec",
            "range": "stddev: 1.8715562277745377",
            "extra": "mean: 5.415540441666669 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 2.716980865503669,
            "unit": "iter/sec",
            "range": "stddev: 0.02188211552305204",
            "extra": "mean: 368.0555916666795 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 2.710909647069364,
            "unit": "iter/sec",
            "range": "stddev: 0.00789035954463409",
            "extra": "mean: 368.8798706666792 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 9.49943223160172,
            "unit": "iter/sec",
            "range": "stddev: 0.004163749186331253",
            "extra": "mean: 105.26944933333009 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.42500908475335475,
            "unit": "iter/sec",
            "range": "stddev: 0.38973705979630296",
            "extra": "mean: 2.3528908813333467 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.3792443068289934,
            "unit": "iter/sec",
            "range": "stddev: 0.34078855360652854",
            "extra": "mean: 2.6368227076666813 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.181963129745523,
            "unit": "iter/sec",
            "range": "stddev: 0.009587195020653019",
            "extra": "mean: 161.7609130000043 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.22431466614920328,
            "unit": "iter/sec",
            "range": "stddev: 0.13505151439347787",
            "extra": "mean: 4.458023263333341 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.18923566712612458,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 5.284416068000041 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.2527192942284391,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.956959452000035 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.21776734417717847,
            "unit": "iter/sec",
            "range": "stddev: 0.04319629457650444",
            "extra": "mean: 4.592056737333337 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.25430941754931374,
            "unit": "iter/sec",
            "range": "stddev: 0.7236967216665217",
            "extra": "mean: 3.932217727666682 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.24431464976036393,
            "unit": "iter/sec",
            "range": "stddev: 0.7648656288102407",
            "extra": "mean: 4.093082428666681 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.24905003839353806,
            "unit": "iter/sec",
            "range": "stddev: 0.7721607136243802",
            "extra": "mean: 4.015257361333322 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "45037215+TeunHuijben@users.noreply.github.com",
            "name": "Teun Huijben",
            "username": "TeunHuijben"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "572524fad248d7096f9840ad471b5909d3640894",
          "message": "mask conversion UI dialog (uint64 to bool) (#462)\n\n* UI option to convert legacy uint64 masks in geff to bool upon import using tracksdata util\n\n* do boolean conversion per specified mask key\n\n* added tests + pin unreased td code + alter geff inplace\n\n* bump funtracks to get latest tracksdata fixes\n\n* remove tracksdata commit pin",
          "timestamp": "2026-08-20T09:38:52-07:00",
          "tree_id": "082561ef10c60112f96c2fba6ec52f7f4a79f317",
          "url": "https://github.com/funkelab/motile_tracker/commit/572524fad248d7096f9840ad471b5909d3640894"
        },
        "date": 1787244354282,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.428496663716689,
            "unit": "iter/sec",
            "range": "stddev: 0.1797019402363843",
            "extra": "mean: 411.77738266667063 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.21595856040809355,
            "unit": "iter/sec",
            "range": "stddev: 1.4624184706085723",
            "extra": "mean: 4.630517994333336 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.12725874732699,
            "unit": "iter/sec",
            "range": "stddev: 0.008320005336164116",
            "extra": "mean: 319.7688713333188 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.0269914710579284,
            "unit": "iter/sec",
            "range": "stddev: 0.018989562409427504",
            "extra": "mean: 330.36102333334344 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.704992289926583,
            "unit": "iter/sec",
            "range": "stddev: 0.003466025536391137",
            "extra": "mean: 93.41435966665775 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5144770382124743,
            "unit": "iter/sec",
            "range": "stddev: 0.22448726843319922",
            "extra": "mean: 1.9437213436666714 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.45713974385575995,
            "unit": "iter/sec",
            "range": "stddev: 0.23545591677896321",
            "extra": "mean: 2.1875148976666687 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 7.082675045905713,
            "unit": "iter/sec",
            "range": "stddev: 0.006377814706667571",
            "extra": "mean: 141.18959199999873 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.28363233775277263,
            "unit": "iter/sec",
            "range": "stddev: 0.08833489648410286",
            "extra": "mean: 3.5256910686666743 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.2420709334709591,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.131020546999991 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.2883361865501272,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.4681737730000464 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.2754611469558073,
            "unit": "iter/sec",
            "range": "stddev: 0.032535324218207935",
            "extra": "mean: 3.63027603366667 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.3116212384624512,
            "unit": "iter/sec",
            "range": "stddev: 0.32926170705934593",
            "extra": "mean: 3.2090238936666537 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.30787238594531535,
            "unit": "iter/sec",
            "range": "stddev: 0.4298695040288346",
            "extra": "mean: 3.248099036000004 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.30089554174022126,
            "unit": "iter/sec",
            "range": "stddev: 0.3914500638731578",
            "extra": "mean: 3.323412484666695 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "45037215+TeunHuijben@users.noreply.github.com",
            "name": "Teun Huijben",
            "username": "TeunHuijben"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "7bd21308aba0ff3067c1209eef227ae4d9407759",
          "message": "segmentation_shape consistency (#463)\n\n* segmentation_shape consistency\n\n* update funtracks (include mask.__isub__ fix)\n\n* make benchmark comparison use separate uvs\n\n* wrong funtracks commit (funtracks PR 260)\n\n* few cosmetic benchmark changes\n\n* renew pinned funtracks commit\n\n* fix tests, because the latest funtracks writes segmentation_shape in two places in the zattrs (within geff, and in top level)\n\n* Update to funtracks 2.1.0-a3\n\n* Use new geff helper functions from funtracks\n\n* Fix zarr v2 incompatibility\n\n---------\n\nCo-authored-by: Caroline Malin-Mayor <malinmayorc@janelia.hhmi.org>",
          "timestamp": "2026-08-20T12:39:37-07:00",
          "tree_id": "11d81e124685e4af2d28308a41ee105ee21082be",
          "url": "https://github.com/funkelab/motile_tracker/commit/7bd21308aba0ff3067c1209eef227ae4d9407759"
        },
        "date": 1787255186558,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.6849198616529657,
            "unit": "iter/sec",
            "range": "stddev: 0.14164914617626367",
            "extra": "mean: 372.45059500001315 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.22266646836515488,
            "unit": "iter/sec",
            "range": "stddev: 1.3764504237628037",
            "extra": "mean: 4.491021963666668 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.1815015756529177,
            "unit": "iter/sec",
            "range": "stddev: 0.008821571360841366",
            "extra": "mean: 314.3169903333387 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.12743533715475,
            "unit": "iter/sec",
            "range": "stddev: 0.021059520620454998",
            "extra": "mean: 319.75081566667046 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 10.916400332271387,
            "unit": "iter/sec",
            "range": "stddev: 0.002207375157762485",
            "extra": "mean: 91.60528833335017 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.530340138376618,
            "unit": "iter/sec",
            "range": "stddev: 0.19257677486802305",
            "extra": "mean: 1.8855823416666528 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.456069491877657,
            "unit": "iter/sec",
            "range": "stddev: 0.20470954171050681",
            "extra": "mean: 2.192648308666643 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 6.990465331509233,
            "unit": "iter/sec",
            "range": "stddev: 0.00719817265102095",
            "extra": "mean: 143.05199333333954 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.2819616579283544,
            "unit": "iter/sec",
            "range": "stddev: 0.0411037516718954",
            "extra": "mean: 3.5465815010000292 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.24103047758152188,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.148852916999999 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.2872368928659921,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.4814469340000187 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.2791851130959714,
            "unit": "iter/sec",
            "range": "stddev: 0.022730468895351047",
            "extra": "mean: 3.5818528749999814 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.319431131520572,
            "unit": "iter/sec",
            "range": "stddev: 0.3269270380554076",
            "extra": "mean: 3.1305652496666503 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.3151986920311659,
            "unit": "iter/sec",
            "range": "stddev: 0.3767661268549983",
            "extra": "mean: 3.172601997666675 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.31020663026500156,
            "unit": "iter/sec",
            "range": "stddev: 0.4090633164131715",
            "extra": "mean: 3.2236577250000287 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "66853113+pre-commit-ci[bot]@users.noreply.github.com",
            "name": "pre-commit-ci[bot]",
            "username": "pre-commit-ci[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1e1a8adca6ce92d9bb1adacba702c57117e761ac",
          "message": "[pre-commit.ci] pre-commit autoupdate (#484)\n\nupdates:\n- [github.com/astral-sh/ruff-pre-commit: v0.16.3 → v0.16.5](https://github.com/astral-sh/ruff-pre-commit/compare/v0.16.3...v0.16.5)\n\nCo-authored-by: pre-commit-ci[bot] <66853113+pre-commit-ci[bot]@users.noreply.github.com>",
          "timestamp": "2026-08-31T16:27:29-07:00",
          "tree_id": "17ab1f24cdaa3c90b09df47c899796b3f427f1e5",
          "url": "https://github.com/funkelab/motile_tracker/commit/1e1a8adca6ce92d9bb1adacba702c57117e761ac"
        },
        "date": 1788219236781,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 3.348025731332105,
            "unit": "iter/sec",
            "range": "stddev: 0.019722754115149774",
            "extra": "mean: 298.6834870000005 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.2329871320404721,
            "unit": "iter/sec",
            "range": "stddev: 1.579594278996316",
            "extra": "mean: 4.292082533666668 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.3815602323458283,
            "unit": "iter/sec",
            "range": "stddev: 0.007313295602040829",
            "extra": "mean: 295.72148099999634 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.2586853109580196,
            "unit": "iter/sec",
            "range": "stddev: 0.019100378020748952",
            "extra": "mean: 306.8722213333359 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 11.524483890874327,
            "unit": "iter/sec",
            "range": "stddev: 0.0027118388838811933",
            "extra": "mean: 86.77178166666977 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5638719180681434,
            "unit": "iter/sec",
            "range": "stddev: 0.19193041310881603",
            "extra": "mean: 1.7734523886666598 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.4552629707157641,
            "unit": "iter/sec",
            "range": "stddev: 0.16295330591088122",
            "extra": "mean: 2.1965326949999926 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 7.525771005644298,
            "unit": "iter/sec",
            "range": "stddev: 0.007729237265860993",
            "extra": "mean: 132.87675099999774 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.2947435253123149,
            "unit": "iter/sec",
            "range": "stddev: 0.057573132671891056",
            "extra": "mean: 3.3927802110000016 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.24957598724405014,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 4.006795730000022 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.30523208533592194,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.2761955510000007 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.29900372318240026,
            "unit": "iter/sec",
            "range": "stddev: 0.3430312813607488",
            "extra": "mean: 3.3444399600000074 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.30350353773319383,
            "unit": "iter/sec",
            "range": "stddev: 0.42386639648231833",
            "extra": "mean: 3.2948545096666635 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.3060600123623026,
            "unit": "iter/sec",
            "range": "stddev: 0.4485135635460096",
            "extra": "mean: 3.267333070666666 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.32422882649154655,
            "unit": "iter/sec",
            "range": "stddev: 0.4722432081509063",
            "extra": "mean: 3.084241493333328 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "e130fc07318e337481a791cbf5318b6575fcdf40",
          "message": "Merge pull request #486 from live-image-tracking-tools/fix_stale_seg\n\nFix stale segmentation when loading tracks from geff or MotileRun",
          "timestamp": "2026-09-04T10:24:30-04:00",
          "tree_id": "7fc570b430bc6105c8ef19185ee3a6c3de6f4038",
          "url": "https://github.com/live-image-tracking-tools/napari-track-edit/commit/e130fc07318e337481a791cbf5318b6575fcdf40"
        },
        "date": 1788536916007,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 3.230828002512911,
            "unit": "iter/sec",
            "range": "stddev: 0.01855533612799499",
            "extra": "mean: 309.51817899999884 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_add_tracks[large]",
            "value": 0.23926966703114558,
            "unit": "iter/sec",
            "range": "stddev: 1.471348429648894",
            "extra": "mean: 4.17938476033333 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_treeview[large]",
            "value": 3.3837125573538787,
            "unit": "iter/sec",
            "range": "stddev: 0.011244501057892316",
            "extra": "mean: 295.5333773333327 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_click_node_canvas[large]",
            "value": 3.312508004054469,
            "unit": "iter/sec",
            "range": "stddev: 0.014276992538410319",
            "extra": "mean: 301.8860630000025 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_set_display_mode_lineage[large]",
            "value": 11.145796540980754,
            "unit": "iter/sec",
            "range": "stddev: 0.0017045568524765853",
            "extra": "mean: 89.71992233333974 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_flip_axes[large]",
            "value": 0.5497086234534877,
            "unit": "iter/sec",
            "range": "stddev: 0.16692660656805675",
            "extra": "mean: 1.8191455570000035 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_tree_feature_recolor[large]",
            "value": 0.45730063098231366,
            "unit": "iter/sec",
            "range": "stddev: 0.1431812855570982",
            "extra": "mean: 2.1867452879999973 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_label_colormap_rebuild[large]",
            "value": 7.480859976622048,
            "unit": "iter/sec",
            "range": "stddev: 0.007517739428654273",
            "extra": "mean: 133.67447099999671 msec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_node[large]",
            "value": 0.2973469710991692,
            "unit": "iter/sec",
            "range": "stddev: 0.13002696894440452",
            "extra": "mean: 3.363074445666664 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_nodes_bulk[large]",
            "value": 0.2520731692899409,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.967102103000002 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo_bulk_delete[large]",
            "value": 0.30798090029467845,
            "unit": "iter/sec",
            "range": "stddev: 0",
            "extra": "mean: 3.2469545969999842 sec\nrounds: 1"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_delete_edge[large]",
            "value": 0.30258419212223137,
            "unit": "iter/sec",
            "range": "stddev: 0.34301662191035376",
            "extra": "mean: 3.304865310333336 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_create_edge[large]",
            "value": 0.3067615186779923,
            "unit": "iter/sec",
            "range": "stddev: 0.37637235021475335",
            "extra": "mean: 3.2598612900000035 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_undo[large]",
            "value": 0.30073632917388293,
            "unit": "iter/sec",
            "range": "stddev: 0.4414925905796943",
            "extra": "mean: 3.3251719296666997 sec\nrounds: 3"
          },
          {
            "name": "tests/benchmarks/bench_ui_actions.py::test_redo[large]",
            "value": 0.3237386299395598,
            "unit": "iter/sec",
            "range": "stddev: 0.4605909441161579",
            "extra": "mean: 3.0889115710000206 sec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b628b4af19c1ad818ad3ba98ac3b9b371ad66a14",
          "message": "Merge pull request #453 from live-image-tracking-tools/fastplotlib-treeview\n\nFastplotlib TreePlot",
          "timestamp": "2026-09-06T09:15:21-04:00",
          "tree_id": "2e6a0ba1c1b25b4c5ff66c57cb382aee5767bddc",
          "url": "https://github.com/live-image-tracking-tools/napari-track-edit/commit/b628b4af19c1ad818ad3ba98ac3b9b371ad66a14"
        },
        "date": 1788700580588,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.8933781360978865,
            "unit": "iter/sec",
            "range": "stddev: 0.13201687803136258",
            "extra": "mean: 345.6167679999946 msec\nrounds: 3"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "malinmayorc@janelia.hhmi.org",
            "name": "Caroline Malin-Mayor",
            "username": "cmalinmayor"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "7b7939c0c423fded945969a89f218d9c901b6f42",
          "message": "Merge pull request #458 from live-image-tracking-tools/track_from_scratch\n\nTracking from scratch",
          "timestamp": "2026-09-06T09:23:51-04:00",
          "tree_id": "a36c6e90cd9ff3936b486bf8d7248bfec0555e99",
          "url": "https://github.com/live-image-tracking-tools/napari-track-edit/commit/7b7939c0c423fded945969a89f218d9c901b6f42"
        },
        "date": 1788701098971,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/benchmarks/bench_data_model.py::test_extract_sorted_tracks[large]",
            "value": 2.7087656498855814,
            "unit": "iter/sec",
            "range": "stddev: 0.12645361329277743",
            "extra": "mean: 369.17184033334155 msec\nrounds: 3"
          }
        ]
      }
    ]
  }
}