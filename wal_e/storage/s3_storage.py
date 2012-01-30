#!/usr/bin/env python
"""
S3 Storage Abstraction

This module is used to define and provide accessors to the logical
structure and metadata for an S3-backed WAL-E prefix.

"""

import collections
import re

import wal_e.exception
import wal_e.storage.s3_storage

from urlparse import urlparse

CURRENT_VERSION = '005'

SEGMENT_REGEXP = (r'(?P<filename>(?P<tli>[0-9A-F]{8,8})(?P<log>[0-9A-F]{8,8})'
                  '(?P<seg>[0-9A-F]{8,8}))')

BASE_BACKUP_REGEXP = (r'base_' + SEGMENT_REGEXP + r'_(?P<offset>[0-9A-F]{8})')

COMPLETE_BASE_BACKUP_REGEXP = (
    r'base_' + SEGMENT_REGEXP +
    r'_(?P<offset>[0-9A-F]{8})_backup_stop_sentinel\.json')

VOLUME_REGEXP = (r'part_(\d+)\.tar\.lzo')


# A representation of a timeline, log number and segment number.
class SegmentNumber(collections.namedtuple('SegmentNumber',
                                           ['tli', 'log', 'seg'])):

    def __new__(cls, *args, **kwargs):
        instance = super(SegmentNumber, cls).__new__(cls, *args, **kwargs)
        instance._check()
        return instance

    @classmethod
    def from_string(cls, s):
        d = re.match(SEGMENT_REGEXP, s).groupdict()
        return cls(tli=d['tli'], log=d['log'], seg=d['seg'])

    def _check(self):
        assert self.tli is None or (len(self.tli) == 8 and
                                    int(self.tli, 16) > 0)
        assert len(self.log) == 8
        assert len(self.seg) == 8

    @property
    def as_an_integer_with_timeline(self):
        """
        Convert this segment into an integer

        This number is useful for determining how to copy lineages
        between contexts.
        """
        self._check()
        return int(self.tli + self.log + self.seg, 16)

    @property
    def as_an_integer_without_timeline(self):
        """
        Convert this segment into an integer stripped of timeline

        This number always increases even when diverging into two
        timelines, so it's useful for conservative garbage collection.
        """
        self._check()
        return int(self.log + self.seg, 16)

# Exhaustively enumerates all possible metadata about a backup.  These
# may not always all be filled depending what access method is used to
# get information, in which case the unfilled items should be given a
# None value.  If an item was intended to be fetch, but could not be
# after some number of retries and timeouts, the field should be
# filled with the string 'timeout'.
BackupInfo = collections.namedtuple('BackupInfo',
                                    ['name',
                                     'last_modified',
                                     'expanded_size_bytes',
                                     'wal_segment_backup_start',
                                     'wal_segment_offset_backup_start',
                                     'wal_segment_backup_stop',
                                     'wal_segment_offset_backup_stop'])


class ParseError(Exception):
    pass


class StorageLayout(object):
    """
    Encapsulates and defines S3 URL path manipulations for WAL-E

    Without a trailing slash
    >>> sl = StorageLayout('s3://foo/bar')
    >>> sl.basebackups()
    'bar/basebackups_005/'
    >>> sl.wal_directory()
    'bar/wal_005/'
    >>> sl.bucket_name()
    'foo'

    With a trailing slash
    >>> sl = StorageLayout('s3://foo/bar/')
    >>> sl.basebackups()
    'bar/basebackups_005/'
    >>> sl.wal_directory()
    'bar/wal_005/'
    >>> sl.bucket_name()
    'foo'

    """

    def __init__(self, prefix, version=CURRENT_VERSION):
        self.VERSION = version

        url_tup = urlparse(prefix)

        if url_tup.scheme != 's3':
            raise wal_e.exception.UserException(
                msg='bad S3 URL scheme passed',
                detail='The scheme {0} was passed when "s3" was expected.'
                .format(url_tup.scheme))

        self._url_tup = url_tup

        # S3 api requests absolutely cannot contain a leading slash.
        s3_api_prefix = url_tup.path.lstrip('/')

        # Also canonicalize a trailing slash onto the prefix, should
        # none already exist.
        if s3_api_prefix[-1] != '/':
            self._s3_api_prefix = s3_api_prefix + '/'
        else:
            self._s3_api_prefix = s3_api_prefix

    def _error_on_unexpected_version(self):
        if self.VERSION != '005':
            raise ValueError('Backwards compatibility of this '
                             'operator is not implemented')

    def basebackups(self):
        return self._s3_api_prefix + 'basebackups_' + self.VERSION + '/'

    def basebackup_directory(self, backup_info):
        self._error_on_unexpected_version()
        return (self.basebackups() +
                'base_{0}_{1}/'.format(
                backup_info.wal_segment_backup_start,
                backup_info.wal_segment_offset_backup_start))

    def basebackup_sentinel(self, backup_info):
        self._error_on_unexpected_version()

        with_delimiter = self.basebackup_directory(backup_info)
        assert with_delimiter[-1] == '/'
        without_delimiter = with_delimiter[:-1]

        return without_delimiter + '_backup_stop_sentinel.json'

    def basebackup_tar_partition_directory(self, backup_info):
        self._error_on_unexpected_version()
        return (self.basebackup_directory(backup_info) +
                'tar_partitions/')

    def basebackup_extended_version(self, backup_info):
        self._error_on_unexpected_version()
        return (self.basebackup_directory(backup_info) +
                'extended_version.txt')

    def basebackup_tar_partition(self, backup_info, part_name):
        self._error_on_unexpected_version()
        return (self.basebackup_tar_partition_directory(backup_info) +
                part_name)

    def wal_directory(self):
        return self._s3_api_prefix + 'wal_' + self.VERSION + '/'

    def wal_path(self, wal_file_name):
        self._error_on_unexpected_version()
        return self.wal_directory() + wal_file_name

    def bucket_name(self):
        return self._url_tup.netloc

    def parse(self, url):
        submitted_url_tup = urlparse(url)

        if (submitted_url_tup.scheme != self._url_tup.scheme or
            submitted_url_tup.netloc != self._url_tup.netloc or
            not submitted_url_tup.path.startswith(self._url_tup.path)):
            raise ValueError('Passed URI is not contained within this '
                             'Storage Context.')

        def groupdict_to_backup_info(regexp, s):
            match = re.match(regexp, s)

            if match is None:
                raise ParseError
            else:
                matchdict = match.groupdict()

                return wal_e.storage.s3_storage.BackupInfo(
                    name=s,
                    wal_segment_backup_start=matchdict['filename'],
                    wal_segment_offset_backup_start=matchdict['offset'],

                    # Fields that are not present in nor necessary to
                    # to format key strings, but must be specified to
                    # make namedtuple not raise an error.
                    last_modified=None,
                    expanded_size_bytes=None,
                    wal_segment_backup_stop=None,
                    wal_segment_offset_backup_stop=None)

        # "Cliques" are different levels of keys that occur in the
        # storage layout, as determined by the number of slashes that
        # are not at the beginning nor end of the string (otherwise
        # it's a meta-key, which more closely resembles a 'directory')
        cliques = [self.basebackups().count('/')]
        for i in xrange(2):
            cliques.append(cliques[-1] + 1)
        cliques = tuple(cliques)

        basebackup_metakey_name = self.basebackup_directory

        relative_path = submitted_url_tup.path[len(self._url_tup.path):]
        key_parts = relative_path.strip('/').split('/')
        key_depth = len(key_parts)

        # These conditionals have the following pattern:
        #
        # The first level contains the test against the clique of the
        # key beikng considered.
        #
        # The second level rechecks the key against the possible
        # prefixes that can contain keys of a given clique.
        if key_depth == cliques[0]:
            if submitted_url_tup.path.startswith('/' + self.basebackups()):
                return (self.basebackup_sentinel,
                        (groupdict_to_backup_info(
                            COMPLETE_BASE_BACKUP_REGEXP,
                            key_parts[-1]),))
            elif submitted_url_tup.path.startswith('/' + self.wal_directory()):
                return (self.wal_path, (key_parts[-1],))
            else:
                raise ParseError
        elif key_depth == cliques[1]:
            bi = groupdict_to_backup_info(BASE_BACKUP_REGEXP, key_parts[-2])
            if (submitted_url_tup.path ==
                '/' + self.basebackup_extended_version(bi)):
                return (self.basebackup_extended_version, (bi,))
            else:
                raise ParseError
        elif key_depth == cliques[2]:
            bi = groupdict_to_backup_info(BASE_BACKUP_REGEXP, key_parts[-3])
            if submitted_url_tup.path.startswith(
                '/' + self.basebackup_tar_partition_directory(bi)):
                return (self.basebackup_tar_partition,
                        (groupdict_to_backup_info(
                            BASE_BACKUP_REGEXP, key_parts[-3]), key_parts[-1]))
            else:
                raise ParseError
        else:
            assert key_depth < clique_one and key_depth > clique_three
            raise ParseError
