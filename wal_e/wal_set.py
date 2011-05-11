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

