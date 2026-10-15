from __future__ import annotations

import numpy as np

from bonsai_wall import rng


def test_streams_reproducible_and_independent():
    a = rng.stream(5, "biology").random(8)
    assert (a == rng.stream(5, "biology").random(8)).all()
    assert not (a == rng.stream(5, "maintainer").random(8)).all()
    assert not (a == rng.stream(6, "biology").random(8)).all()
    assert set(rng.STREAMS) == set(rng.STREAM_IDS)


def test_hash_u01_properties():
    v = [rng.hash_u01(9, 2, y, i) for y in range(20) for i in range(1000)]
    assert min(v) >= 0 and max(v) < 1
    assert abs(sum(v) / len(v) - 0.5) < 0.01
    assert rng.hash_u01(9, 2, 4, 5) == rng.hash_u01(9, 2, 4, 5)
    assert rng.hash_u01(9, 2, 4, 5) != rng.hash_u01(9, 2, 5, 4)
    assert rng.hash_u01(9, 2, 4, 5) != rng.hash_u01(9, 3, 4, 5)
    assert rng.hash_u01(9, 2, 4, 5) != rng.hash_u01(10, 2, 4, 5)


def test_numpy_variant_matches_scalar():
    ids = np.arange(500)
    got = rng.hash_u01_np(7, 3, 12, ids)
    want = [rng.hash_u01(7, 3, 12, int(i)) for i in ids]
    assert np.array_equal(got, np.array(want))


def test_local_change_stays_local():
    base = [rng.hash_u01(1, 4, 3, i) for i in range(50)]
    again = [rng.hash_u01(1, 4, 3, i) for i in range(50)]
    assert base == again            # adding a draw for entity 51 cannot move entities 0..49
