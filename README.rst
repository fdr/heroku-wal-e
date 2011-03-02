WAL-E Disaster Recovery
=======================

WAL-E is a program designed perform continuous archiving of PostgreSQL
WAL files and manage the use of pg_start_backup and pg_stop_backup.
It has four critical operators:

* backup-fetch
* backup-push
* wal-fetch
* wal-push

Of these, the "push" operators send things to S3, and "fetch"
operators get things from S3.  "wal" operators send/get write ahead
log, and "backup" send/get a hot backup of the base database that WAL
segments can be applied to.

All of these operators work in a context of three important
environment-variable based settings:

* AWS_ACCESS_KEY_ID
* AWS_SECRET_ACCESS_KEY
* WALE_S3_PREFIX

With the exception of AWS_SECRET_ACCESS_KEY, all of these can be
specified as arguments as well.  The AWS_* variables are the standard
access-control keying system provided by Amazon.

The WALE_S3_PREFIX can be thought of a context whereby this program
operates on a single database cluster at a time.  Generally, for any
one database the WALE_S3_PREFIX will be the same between all four
operators.  This context-driven approach attempts to help users avoid
errors such as one database overwriting the WAL segments of another,
as long as the WALE_S3_PREFIX is set uniquely for each database.

.. IMPORTANT::
   Ensure that all servers have different WALE_S3_PREFIXes set.  Reuse
   of a value between two servers will likely cause unrecoverable
   backups.


Dependencies
------------

* s3cmd
* lzop
* psql
* python-argparse *or* Python 2.7


Examples
--------

Pushing a base backup to S3::

  $ AWS_SECRET_ACCESS_KEY=... python wal_e.py		\
    -k AWS_ACCESS_KEY_ID				\
    --s3-prefix=s3://some-bucket/directory/or/whatever	\
    backup-push /var/lib/my/database

Sending a WAL segment to S3::

  $ AWS_SECRET_ACCESS_KEY=... python wal_e.py		\
    -k AWS_ACCESS_KEY_ID				\
    --s3-prefix=s3://some-bucket/directory/or/whatever	\
    wal-push /var/lib/my/database/pg_xlog/WAL_SEGMENT_LONG_HEX

It is generally recommended that one use some sort of environment
variable management with WAL-E: working with it this way less verbose,
less prone to error, and less likely to expose secret information in
logs.

At this time, AWS_SECRET_KEY is the only secret value, and recording
it frequently in logs is not recommended.  The tool has never and
should never accept secret information in argv to avoid process table
security problems.  However, the user running PostgreSQL (typically
'postgres') must be able to run a program that can access this secret
information, as part of its archive_command_.

.. _archive_command: http://www.postgresql.org/docs/8.3/static/runtime-config-wal.html#GUC-ARCHIVE-COMMAND>

envdir_, part of the daemontools_ package is one recommended approach
to setting environment variables.  One can prepare an
envdir-compatible directory like so::

  # Assumption: the group is trusted to read secret information
  $ umask u=rwx,g=rx,o=
  $ mkdir -p /etc/wal-e.d/env
  $ echo "secret-key-content" > /etc/wal-e.d/env/AWS_SECRET_ACCESS_KEY
  $ echo "access-key" > /etc/wal-e.d/env/AWS_ACCESS_KEY_ID
  $ echo 's3://some-bucket/directory/or/whatever' > /etc/wal-e.d/env/WALE_PREFIX
  $ chown -R root:postgres /etc/wal-e.d

After having done this preparation, it is possible to run WAL-E
commands much more simply, with less risk of accidentally using
incorrect values::

  $ envdir /etc/wal-e.d/env python wal_e.py backup-push ...
  $ envdir /etc/wal-e.d/env python wal_e.py wal-push ...

envdir is conveniently combined with the archive_command functionality
used by PostgreSQL to enable continuous archiving.  To enable
continuous archiving, one needs to edit ``postgresql.conf`` and
restart the server.  The important settings to enable continuous
archiving are related here::

  wal_level = archive # hot_standby in 9.0 is also acceptable
  archive_mode = on
  archive_command = 'envdir /etc/wal-e.d/env python /path/wal_e.py wal-push %p'
  archive_timeout = 60

Every segment archived will be noted in the PostgreSQL log.

.. WARNING::
   PostgreSQL users can check the pg_settings table and see the
   archive_command employed.  Do not put secret information into
   postgresql.conf for that reason, and use envdir instead.

A base backup (via ``backup-push``) can be uploaded at any time, but
this must be done at least once in order to perform a restoration.  It
must be done again if any WAL segment was not correctly uploaded:
point in time recovery will not be able to continue if there are any
gaps in the WAL segments.

.. _envdir: http://cr.yp.to/daemontools/envdir.html
.. _daemontools: http://cr.yp.to/daemontools.html


Compression and Temporary Files
-------------------------------

All assets pushed to S3 are run through the program "lzop" which
compresses the object using the very fast lzo compression algorithm.
It takes roughly 2 CPU seconds to compress a gigabyte, which when
sending things to S3 at about 25MB/s occupies about 5% CPU time.
Compression ratios are expected to make file sizes 10%-30% of the
original file size, making backups and restorations considerably
faster.

Because S3 requires the Content-Length header of a stored object to be
set up-front, it is necessary to completely finish compressing an
entire input file and storing the compressed output in a temporary
file.  Thus, the temporary file directory needs to be big enough and
fast enough to support this, although this tool is designed to avoid
calling fsync(), so some memory can be leveraged.


TODO
----

* setup.py

  * Should have dependencies (e.g. argparse)
  * Should install commands into bin using setuptools entry points

* backup_fetch: fetching a base backup
* wal_fetch: fetching a WAL segment
* wal_push: pushing a WAL segment
* Investigate pg_lesslog.  This tool strips the WAL file of full-page
  binary images, making it *much* smaller, but this also makes the
  recovery process more expensive (has to do more seeking to do
  recovery).  The question is: is the increased speed of fetching a
  WAL segment dominated by recovery time, or vice-versa?
* Ask pgsql-hackers about a pg_cancel_backup() function
* Sane error messages, such as on Ctrl-C or during errors.
* Pipeline-WAL-Segment Management: S3 ACK is long enough that a
  totally non-pipelined, non-parallel archive_command can fall behind.