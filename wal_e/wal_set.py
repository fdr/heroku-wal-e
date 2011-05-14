#!/usr/bin/env python

"""
Module to model sets of PostgreSQL Write Ahead Log

This includes understanding the WAL numbering scheme.  Here is
editorialized chunk of the PostgreSQL source, 9.0, in xlog_internal.h.
It defines all relevant paths that fit in the pg_xlog hierarchy as
well as the types of files that can exist.

#define XLogFileName(fname, tli, log, seg) \
 snprintf(fname, MAXFNAMELEN, "%08X%08X%08X", tli, log, seg)

#define XLogFilePath(path, tli, log, seg) \
 snprintf(path, MAXPGPATH, XLOGDIR "/%08X%08X%08X", tli, log, seg)

#define TLHistoryFilePath(path, tli) \
 snprintf(path, MAXPGPATH, XLOGDIR "/%08X.history", tli)

#define BackupHistoryFilePath(path, tli, log, seg, offset) \
 snprintf(path, MAXPGPATH, XLOGDIR "/%08X%08X%08X.%08X.backup", tli, log, seg, offset)


"""
import blist
import collections

from bisect import bisect_left

def interval_union(i1, i2):
    return (min(i1[0], i2[0]), max(i1[1], i2[1]))

def interval_disjoint_check(a):
    last_end = None
    for interval in a:
        if interval[0] < last_end:
            return False
        last_end = interval[1]

    return True

def bin_scalar_in_intervals(a, x):
    # While code is fresh put in this simple check
    assert interval_disjoint_check(a)

    i = bisect_left(a, (x,))

    if i == len(a):
        haystack_low, haystack_high = a[-1]
        assert x >= haystack_low

        if x <= haystack_high:
            return a[-1]
        else:
            return None
    elif i == 0:
        haystack_low, haystack_high = a[0]
        assert x <= haystack_low
        if x == haystack_low:
            return a[0]
        else:
            return None
    else:
        assert i > 0 and i < len(a)
        haystack_low, haystack_high = a[i]

        print 'foo', a[i]

    assert False
