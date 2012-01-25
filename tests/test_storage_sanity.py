import pytest

from wal_e.storage.s3_storage import *


def pytest_funcarg__sl(request):
    return StorageLayout('s3://foo/bar')


def pytest_funcarg__bi(request):
    return BackupInfo('hello', 'sometime', '37',
                      '0' * 24, '1' * 8, '2' * 24, '3' * 8)


def test_sn_timeline_comparison():
    sn = SegmentNumber('00000001', '00000001', '00000002')

    assert sn.as_an_integer_with_timeline > sn.as_an_integer_without_timeline


def test_bogus_zero_timeline():
    """
    Timeline 0 is not a legitimate timeline

    The existence of such a timeline can cause numerical comparison of
    timelines to make less sense.
    """
    with pytest.raises(AssertionError):
        SegmentNumber('00000000', '00000001', '00000002')


def test_sn_different_timeline_comparison():
    # Two timelines, whereby an earlier timeline has progresed farther
    # than a later one.
    earlier_timeline = SegmentNumber('00000001', '00000010', '00000001')
    later_timeline = SegmentNumber('00000007', '00000001', '00000002')

    # Ensure that timeline-sensitive comparisons work
    assert (later_timeline.as_an_integer_with_timeline
            >
            earlier_timeline.as_an_integer_with_timeline)

    # Ensure that timeline-insensitive comparisons work.
    assert (later_timeline.as_an_integer_without_timeline
            <
            earlier_timeline.as_an_integer_without_timeline)


def test_backup_sentinel(sl, bi):
    sentinel_location = sl.basebackup_sentinel(bi)
    assert (sentinel_location.split('/')[-1] ==
            'base_000000000000000000000000_11111111_backup_stop_sentinel.json')
