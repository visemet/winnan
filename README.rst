.. image:: https://travis-ci.com/visemet/winnan.svg?branch=master
    :target: https://travis-ci.com/visemet/winnan
    :alt: Travis CI build status

.. image:: https://ci.appveyor.com/api/projects/status/f58mmgibijt4annn/branch/master?svg=true
    :target: https://ci.appveyor.com/project/visemet/winnan/branch/master
    :alt: AppVeyor build status

.. image:: https://img.shields.io/pypi/v/winnan.svg?label=pypi
    :target: https://pypi.org/project/winnan
    :alt: Latest version

.. image:: https://img.shields.io/pypi/pyversions/winnan.svg
    :target: https://pypi.org/project/winnan
    :alt: Supported Python versions

.. image:: https://img.shields.io/pypi/l/winnan.svg
    :target: LICENSE
    :alt: License

----

winnan
======

    **winnan**

    1. (verb) to struggle, suffer, contend

    https://en.wiktionary.org/wiki/winnan

*Because everything about managing files on Windows is terrible.*


Installation
------------

.. code-block:: console

    $ python -m pip install --upgrade winnan


Usage
-----

Use the ``winnan.open()`` function exactly like using |Python's built-in open() function|_. It aims
to be a drop-in replacement.

.. |Python's built-in open() function| replace:: Python's built-in ``open()`` function
.. _Python's built-in open() function: https://docs.python.org/3/library/functions.html#open

.. code-block:: python

    import winnan

    with winnan.open("myfile") as fileobj:
        pass

The file descriptor underlying the returned ``file`` object has the following two properties
**on both POSIX and Windows systems**:

1. The file descriptor is non-inheritable.

2. The file can be *scheduled for deletion* while the file descriptor is still open.

   Saying "scheduled for deletion" rather than "deleted" is to be pedantic about how the file is put
   into a "delete pending" state on Windows until the last file handle is closed. See
   `Mercurial's developer documentation`_ as a reference for the semantics of certain operations on
   the file while it is in a "delete pending" state.

.. _Mercurial's developer documentation: https://www.mercurial-scm.org/wiki/UnlinkingFilesOnWindows


Motivation
----------

Unsurprisingly, the complications around managing files involve dealing with other processes.
Depending on what the Python application is doing, there may be a need to deal with not only
processes spawned by the Python application but also other processes running on the machine.

1. As documented by PEP-446_, opening a file concurrently with spawning a subprocess may lead to the
   file descriptor being inherited unintentionally.

        The process cannot access the file because it is being used by another process.

   is perhaps the most classic representation of this issue on Windows. In modern versions of
   Python, the ``O_NOINHERIT`` flag is set by default when opening file descriptors on Windows.
   Setting it on the opened file descriptor prevents it from being inherited by a child process. The
   equivalent ``O_CLOEXEC`` flag is also set by default in modern versions of Python when opening
   file descriptors on POSIX systems.

   It is worth mentioning that due to limitations with being able to set ``close_fds=True`` when
   redirecting ``stdin``, ``stdout``, or ``stderr`` in older versions of Python, setting the
   ``O_NOINHERIT`` flag isn't sufficient for preventing files descriptors from being leaked when
   spawning subprocesses concurrently. Consider guarding all calls to ``subprocess.Popen`` with a
   ``threading.Lock`` instance to avoid this as an additional issue in older versions of Python.

2. On POSIX systems, it is possible to ``unlink()`` a file while it is still open in another thread
   or process. On Windows, in all versions of Python, non-``O_TEMPORARY`` files are opened with
   ``FILE_SHARE_READ | FILE_SHARE_WRITE`` as their sharing mode. Omitting ``FILE_SHARE_DELETE``
   prevents another thread or process from attempting to delete a file while it is still open.

The purpose of this library is to mask these behavioral differences across different platforms and
in older versions of Python.

.. _PEP-446: https://www.python.org/dev/peps/pep-0446/


References
----------

There have been multiple attempts to address the ``FILE_SHARE_DELETE`` issue within CPython itself
but they unfortunately never succeeded in being integrated.

* bpo-12939_: ``tempfile.NamedTemporaryFile`` not particularly useful on Windows
* bpo-14243_: Support for opening files with ``FILE_SHARE_DELETE`` on Windows
* bpo-15244_: Add new ``io.FileIO`` using the native Windows API

.. _bpo-12939: https://bugs.python.org/issue12939
.. _bpo-14243: https://bugs.python.org/issue14243
.. _bpo-15244: https://bugs.python.org/issue15244

Starting in Python 3.7, ``close_fds=True`` is able to be set even when redirecting ``stdin``,
``stdout``, or ``stderr``.

* bpo-19575_: ``subprocess``: on Windows, unwanted file handles are inherited by child processes
  in a multi-threaded application
* bpo-19764_: ``subprocess``: use ``PROC_THREAD_ATTRIBUTE_HANDLE_LIST`` with ``STARTUPINFOEX`` on
  Windows Vista
* bpo-33369_: Removing ``Popen`` log files in threads is racy on Windows

.. _bpo-19575: https://bugs.python.org/issue19575
.. _bpo-19764: https://bugs.python.org/issue19764
.. _bpo-33369: https://bugs.python.org/issue33369
