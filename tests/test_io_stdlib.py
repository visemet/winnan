"""Unit tests for the io module.

Taken from Lib/test/test_io.py of Python 3.7.0.
Copyright (c) 2007-2018 Python Software Foundation; See THIRD-PARTY-NOTICES.

The following modifications were made to the original sources:
    - Removed test cases that are unrelated to io.open().
    - Added support for running tests with pytest by removing the load_tests() function. This
      necessitated explicitly setting the appropriate open() function and io module as class
      variables.
    - Fixed up test cases so they either pass or are skipped with Python 2 and earlier versions of
      Python 3.
    - Fixed how MiscIOTest._check_warn_on_dealloc() always calls the built-in open() function. This
      necessitated working around how pyio.IOBase.__del__() calling close() prevents a
      ResourceWarning from ever being emitted.
    - Added winnan versions of the BufferedWriterTest, IOTest, MiscIOTest, and TextIOWrapperTest
      test cases.
    - Added unused 'mode' and 'share_flags' keyword arguments to the opener() functions.
"""

# Tests of io are scattered over the test suite:
# * test_bufio - tests file buffering
# * test_memoryio - tests BytesIO and StringIO
# * test_fileio - tests FileIO
# * test_file - tests the file interface
# * test_io - tests everything else in the io module
# * test_univnewlines - tests universal newline support
# * test_largefile - tests operations on a file greater than 2**32 bytes
#     (only enabled with -ulargefile)

################################################################################
# ATTENTION TEST WRITERS!!!
################################################################################
# When writing tests for io, it's important to test both the C and Python
# implementations. This is usually done by writing a base test that refers to
# the type it is testing as an attribute. Then it provides custom subclasses to
# test both implementations. This file has lots of examples.
################################################################################

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import array
import errno
import os
import pickle
import sys
import unittest
import warnings
import weakref
from test import support

import codecs
import io  # C implementation of io
import _pyio as pyio # Python implementation of io

from tests.context import winnan
import tests.mark

if sys.version_info[0] == 2:
    bytes = support.py3k_bytes

    def byteslike(*pos, **kw):
        return memoryview(bytearray(*pos, **kw))
else:
    try:
        import ctypes
    except ImportError:
        def byteslike(*pos, **kw):
            return array.array("b", bytes(*pos, **kw))
    else:
        def byteslike(*pos, **kw):
            """Create a bytes-like object having no string or sequence methods"""
            data = bytes(*pos, **kw)
            obj = EmptyStruct()
            ctypes.resize(obj, len(data))
            memoryview(obj).cast("B")[:] = data
            return obj
        class EmptyStruct(ctypes.Structure):
            pass

def _default_chunk_size():
    """Get the default TextIOWrapper chunk size"""
    with io.open(__file__, "r", encoding="latin-1") as f:
        return f._CHUNK_SIZE


class IOTest(object):

    def setUp(self):
        support.unlink(support.TESTFN)

    def tearDown(self):
        support.unlink(support.TESTFN)

    def write_ops(self, f):
        self.assertEqual(f.write(b"blah."), 5)
        f.truncate(0)
        self.assertEqual(f.tell(), 5)
        f.seek(0)

        self.assertEqual(f.write(b"blah."), 5)
        self.assertEqual(f.seek(0), 0)
        self.assertEqual(f.write(b"Hello."), 6)
        self.assertEqual(f.tell(), 6)
        self.assertEqual(f.seek(-1, 1), 5)
        self.assertEqual(f.tell(), 5)
        buffer = bytearray(b" world\n\n\n")
        self.assertEqual(f.write(buffer), 9)
        buffer[:] = b"*" * 9  # Overwrite our copy of the data
        self.assertEqual(f.seek(0), 0)
        self.assertEqual(f.write(b"h"), 1)
        self.assertEqual(f.seek(-1, 2), 13)
        self.assertEqual(f.tell(), 13)

        self.assertEqual(f.truncate(12), 12)
        self.assertEqual(f.tell(), 13)
        self.assertRaises(TypeError, f.seek, 0.0)

    def read_ops(self, f, buffered=False):
        data = f.read(5)
        self.assertEqual(data, b"hello")
        data = byteslike(data)
        self.assertEqual(f.readinto(data), 5)
        self.assertEqual(bytes(data), b" worl")
        data = bytearray(5)
        self.assertEqual(f.readinto(data), 2)
        self.assertEqual(len(data), 5)
        self.assertEqual(data[:2], b"d\n")
        self.assertEqual(f.seek(0), 0)
        self.assertEqual(f.read(20), b"hello world\n")
        self.assertEqual(f.read(1), b"")
        self.assertEqual(f.readinto(byteslike(b"x")), 0)
        self.assertEqual(f.seek(-6, 2), 6)
        self.assertEqual(f.read(5), b"world")
        self.assertEqual(f.read(0), b"")
        self.assertEqual(f.readinto(byteslike()), 0)
        self.assertEqual(f.seek(-6, 1), 5)
        self.assertEqual(f.read(5), b" worl")
        self.assertEqual(f.tell(), 10)
        self.assertRaises(TypeError, f.seek, 0.0)
        if buffered:
            f.seek(0)
            self.assertEqual(f.read(), b"hello world\n")
            f.seek(6)
            self.assertEqual(f.read(), b"world\n")
            self.assertEqual(f.read(), b"")
            if sys.version_info >= (3, 5):
                f.seek(0)
                data = byteslike(5)
                self.assertEqual(f.readinto1(data), 5)
                self.assertEqual(bytes(data), b"hello")

    LARGE = 2**31

    def large_file_ops(self, f):
        assert f.readable()
        assert f.writable()
        try:
            self.assertEqual(f.seek(self.LARGE), self.LARGE)
        except (OverflowError, ValueError):
            self.skipTest("no largefile support")
        self.assertEqual(f.tell(), self.LARGE)
        self.assertEqual(f.write(b"xxx"), 3)
        self.assertEqual(f.tell(), self.LARGE + 3)
        self.assertEqual(f.seek(-1, 1), self.LARGE + 2)
        self.assertEqual(f.truncate(), self.LARGE + 2)
        self.assertEqual(f.tell(), self.LARGE + 2)
        self.assertEqual(f.seek(0, 2), self.LARGE + 2)
        self.assertEqual(f.truncate(self.LARGE + 1), self.LARGE + 1)
        self.assertEqual(f.tell(), self.LARGE + 2)
        self.assertEqual(f.seek(0, 2), self.LARGE + 1)
        self.assertEqual(f.seek(-1, 2), self.LARGE)
        self.assertEqual(f.read(2), b"x")

    def test_invalid_operations(self):
        # Try writing on a file opened in read mode and vice-versa.
        exc = (IOError, ValueError, self.io.UnsupportedOperation)
        for mode in ("w", "wb"):
            with self.open(support.TESTFN, mode) as fp:
                self.assertRaises(exc, fp.read)
                self.assertRaises(exc, fp.readline)
        with self.open(support.TESTFN, "wb", buffering=0) as fp:
            self.assertRaises(exc, fp.read)
            self.assertRaises(exc, fp.readline)
        with self.open(support.TESTFN, "rb", buffering=0) as fp:
            self.assertRaises(exc, fp.write, b"blah")
            self.assertRaises(exc, fp.writelines, [b"blah\n"])
        with self.open(support.TESTFN, "rb") as fp:
            self.assertRaises(exc, fp.write, b"blah")
            self.assertRaises(exc, fp.writelines, [b"blah\n"])
        with self.open(support.TESTFN, "r") as fp:
            self.assertRaises(exc, fp.write, "blah")
            self.assertRaises(exc, fp.writelines, ["blah\n"])
            # Non-zero seeking from current or end pos
            self.assertRaises(exc, fp.seek, 1, self.io.SEEK_CUR)
            self.assertRaises(exc, fp.seek, -1, self.io.SEEK_END)

    def test_open_handles_NUL_chars(self):
        fn_with_NUL = 'foo\0bar'
        self.assertRaises((TypeError, ValueError), self.open, fn_with_NUL, 'w')

        bytes_fn = bytes_fn = fn_with_NUL.encode('ascii')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.assertRaises((TypeError, ValueError), self.open, bytes_fn, 'w')

    def test_raw_file_io(self):
        with self.open(support.TESTFN, "wb", buffering=0) as f:
            self.assertEqual(f.readable(), False)
            self.assertEqual(f.writable(), True)
            self.assertEqual(f.seekable(), True)
            self.write_ops(f)
        with self.open(support.TESTFN, "rb", buffering=0) as f:
            self.assertEqual(f.readable(), True)
            self.assertEqual(f.writable(), False)
            self.assertEqual(f.seekable(), True)
            self.read_ops(f)

    def test_buffered_file_io(self):
        with self.open(support.TESTFN, "wb") as f:
            self.assertEqual(f.readable(), False)
            self.assertEqual(f.writable(), True)
            self.assertEqual(f.seekable(), True)
            self.write_ops(f)
        with self.open(support.TESTFN, "rb") as f:
            self.assertEqual(f.readable(), True)
            self.assertEqual(f.writable(), False)
            self.assertEqual(f.seekable(), True)
            self.read_ops(f, True)

    def test_readline(self):
        with self.open(support.TESTFN, "wb") as f:
            f.write(b"abc\ndef\nxyzzy\nfoo\x00bar\nanother line")
        with self.open(support.TESTFN, "rb") as f:
            self.assertEqual(f.readline(), b"abc\n")
            self.assertEqual(f.readline(10), b"def\n")
            self.assertEqual(f.readline(2), b"xy")
            self.assertEqual(f.readline(4), b"zzy\n")
            self.assertEqual(f.readline(), b"foo\x00bar\n")
            self.assertEqual(f.readline(None), b"another line")
            self.assertRaises(TypeError, f.readline, 5.3)
        with self.open(support.TESTFN, "r") as f:
            self.assertRaises(TypeError, f.readline, 5.3)

    def test_large_file_ops(self):
        # On Windows and Mac OSX this test consumes large resources; It takes
        # a long time to build the >2 GiB file and takes >2 GiB of disk space
        # therefore the resource must be enabled to run this test.
        if sys.platform[:3] == 'win' or sys.platform == 'darwin':
            support.requires(
                'largefile',
                'test requires %s bytes and a long time to run' % self.LARGE)
        with self.open(support.TESTFN, "w+b", 0) as f:
            self.large_file_ops(f)
        with self.open(support.TESTFN, "w+b") as f:
            self.large_file_ops(f)

    def test_with_open(self):
        for bufsize in (0, 1, 100):
            f = None
            with self.open(support.TESTFN, "wb", bufsize) as f:
                f.write(b"xxx")
            self.assertEqual(f.closed, True)
            f = None
            try:
                with self.open(support.TESTFN, "wb", bufsize) as f:
                    1/0
            except ZeroDivisionError:
                self.assertEqual(f.closed, True)
            else:
                self.fail("1/0 didn't raise an exception")

    # issue 5008
    def test_append_mode_tell(self):
        with self.open(support.TESTFN, "wb") as f:
            f.write(b"xxx")
        with self.open(support.TESTFN, "ab", buffering=0) as f:
            self.assertEqual(f.tell(), 3)
        with self.open(support.TESTFN, "ab") as f:
            self.assertEqual(f.tell(), 3)
        with self.open(support.TESTFN, "a") as f:
            self.assertGreater(f.tell(), 0)

    def test_destructor(self):
        record = []
        class MyFileIO(self.io.FileIO):
            def __del__(self):
                record.append(1)
                try:
                    f = super(MyFileIO, self).__del__
                except AttributeError:
                    pass
                else:
                    f()
            def close(self):
                record.append(2)
                super(MyFileIO, self).close()
            def flush(self):
                record.append(3)
                super(MyFileIO, self).flush()
        expected_warnings = (('', ResourceWarning),) if sys.version_info >= (3, 2) else ()
        with support.check_warnings(*expected_warnings):
            f = MyFileIO(support.TESTFN, "wb")
            f.write(b"xxx")
            del f
            support.gc_collect()
            self.assertEqual(record, [1, 2, 3])
            with self.open(support.TESTFN, "rb") as f:
                self.assertEqual(f.read(), b"xxx")

    def test_close_flushes(self):
        with self.open(support.TESTFN, "wb") as f:
            f.write(b"xxx")
        with self.open(support.TESTFN, "rb") as f:
            self.assertEqual(f.read(), b"xxx")

    def test_closefd(self):
        self.assertRaises(ValueError, self.open, support.TESTFN, 'w',
                          closefd=False)

    def test_read_closed(self):
        with self.open(support.TESTFN, "w") as f:
            f.write("egg\n")
        with self.open(support.TESTFN, "r") as f:
            file = self.open(f.fileno(), "r", closefd=False)
            self.assertEqual(file.read(), "egg\n")
            file.seek(0)
            file.close()
            self.assertRaises(ValueError, file.read)

    def test_no_closefd_with_filename(self):
        # can't use closefd in combination with a file name
        self.assertRaises(ValueError, self.open, support.TESTFN, "r", closefd=False)

    def test_closefd_attr(self):
        with self.open(support.TESTFN, "wb") as f:
            f.write(b"egg\n")
        with self.open(support.TESTFN, "r") as f:
            self.assertEqual(f.buffer.raw.closefd, True)
            file = self.open(f.fileno(), "r", closefd=False)
            self.assertEqual(file.buffer.raw.closefd, False)

    def test_garbage_collection(self):
        # FileIO objects are collected, and collecting them flushes
        # all data to disk.
        expected_warnings = (('', ResourceWarning),) if sys.version_info >= (3, 2) else ()
        with support.check_warnings(*expected_warnings):
            f = self.io.FileIO(support.TESTFN, "wb")
            f.write(b"abcxxx")
            f.f = f
            wr = weakref.ref(f)
            del f
            support.gc_collect()
        self.assertIsNone(wr(), wr)
        with self.open(support.TESTFN, "rb") as f:
            self.assertEqual(f.read(), b"abcxxx")

    def test_unbounded_file(self):
        # Issue #1174606: reading from an unbounded stream such as /dev/zero.
        zero = "/dev/zero"
        if not os.path.exists(zero):
            self.skipTest("{0} does not exist".format(zero))
        if sys.maxsize > 0x7FFFFFFF:
            self.skipTest("test can only run in a 32-bit address space")
        if support.real_max_memuse < support._2G:
            self.skipTest("test requires at least 2 GiB of memory")
        with self.open(zero, "rb", buffering=0) as f:
            self.assertRaises(OverflowError, f.read)
        with self.open(zero, "rb") as f:
            self.assertRaises(OverflowError, f.read)
        with self.open(zero, "r") as f:
            self.assertRaises(OverflowError, f.read)

    def check_flush_error_on_close(self, *args, **kwargs):
        # Test that the file is closed despite failed flush
        # and that flush() is called before file closed.
        f = self.open(*args, **kwargs)
        closed = []
        def bad_flush():
            closed[:] = [f.closed]
            raise OSError()
        f.flush = bad_flush
        self.assertRaises(OSError, f.close) # exception not swallowed
        self.assertTrue(f.closed)
        self.assertTrue(closed)      # flush() called
        self.assertFalse(closed[0])  # flush() called before file closed
        f.flush = lambda: None  # break reference loop

    def test_flush_error_on_close(self):
        # raw file
        # Issue #5700: io.FileIO calls flush() after file closed
        self.check_flush_error_on_close(support.TESTFN, 'wb', buffering=0)
        fd = os.open(support.TESTFN, os.O_WRONLY|os.O_CREAT)
        self.check_flush_error_on_close(fd, 'wb', buffering=0)
        fd = os.open(support.TESTFN, os.O_WRONLY|os.O_CREAT)
        self.check_flush_error_on_close(fd, 'wb', buffering=0, closefd=False)
        os.close(fd)
        # buffered io
        self.check_flush_error_on_close(support.TESTFN, 'wb')
        fd = os.open(support.TESTFN, os.O_WRONLY|os.O_CREAT)
        self.check_flush_error_on_close(fd, 'wb')
        fd = os.open(support.TESTFN, os.O_WRONLY|os.O_CREAT)
        self.check_flush_error_on_close(fd, 'wb', closefd=False)
        os.close(fd)
        # text io
        self.check_flush_error_on_close(support.TESTFN, 'w')
        fd = os.open(support.TESTFN, os.O_WRONLY|os.O_CREAT)
        self.check_flush_error_on_close(fd, 'w')
        fd = os.open(support.TESTFN, os.O_WRONLY|os.O_CREAT)
        self.check_flush_error_on_close(fd, 'w', closefd=False)
        os.close(fd)

    def test_multi_close(self):
        f = self.open(support.TESTFN, "wb", buffering=0)
        f.close()
        f.close()
        f.close()
        self.assertRaises(ValueError, f.flush)

    @tests.mark.skip_unless_winnan_or(sys.version_info >= (3, 3), 'requires opener support')
    def test_opener(self):
        with self.open(support.TESTFN, "w") as f:
            f.write("egg\n")
        fd = os.open(support.TESTFN, os.O_RDONLY)
        def opener(path, flags, mode=None, share_flags=None):
            return fd
        with self.open("non-existent", "r", opener=opener) as f:
            self.assertEqual(f.read(), "egg\n")

    @tests.mark.skip_unless_winnan_or(sys.version_info >= (3, 5), 'requires fix for issue27066')
    def test_bad_opener_negative_1(self):
        # Issue #27066.
        def badopener(fname, flags, mode=None, share_flags=None):
            return -1
        with self.assertRaises((OSError, ValueError)) as cm:
            self.open('non-existent', 'r', opener=badopener)
        self.assertRegexpMatches(str(cm.exception),
                                 r'^(opener returned -1|[Nn]egative file descriptor)$')

    @tests.mark.skip_unless_winnan_or(sys.version_info >= (3, 5), 'requires fix for issue27066')
    def test_bad_opener_other_negative(self):
        # Issue #27066.
        def badopener(fname, flags, mode=None, share_flags=None):
            return -2
        with self.assertRaises((OSError, ValueError)) as cm:
            self.open('non-existent', 'r', opener=badopener)
        self.assertRegexpMatches(str(cm.exception),
                                 r'^(opener returned -2|[Nn]egative file descriptor)$')

    def test_fileio_closefd(self):
        # Issue #4841
        with self.open(__file__, 'rb') as f1, \
             self.open(__file__, 'rb') as f2:
            fileio = self.io.FileIO(f1.fileno(), closefd=False)
            # .__init__() must not close f1
            fileio.__init__(f2.fileno(), closefd=False)
            f1.readline()
            # .close() must not close f2
            fileio.close()
            f2.readline()

    @unittest.skipIf(sys.version_info < (3, 2), 'requires ResourceWarning support')
    def test_nonbuffered_textio(self):
        with warnings.catch_warnings(record=True) as recorded:
            warnings.filterwarnings('always', category=ResourceWarning)
            with self.assertRaises(ValueError):
                self.open(support.TESTFN, 'w', buffering=0)
            support.gc_collect()
        self.assertEqual(recorded, [])

    @unittest.skipIf(sys.version_info < (3, 2), 'requires ResourceWarning support')
    def test_invalid_newline(self):
        with warnings.catch_warnings(record=True) as recorded:
            warnings.filterwarnings('always', category=ResourceWarning)
            with self.assertRaises(ValueError):
                self.open(support.TESTFN, 'w', newline='invalid')
            support.gc_collect()
        self.assertEqual(recorded, [])

    @unittest.skipIf(sys.version_info < (3, 6), 'requires os.PathLike support')
    def test_fspath_support(self):
        from test.support import FakePath

        def check_path_succeeds(path):
            with self.open(path, "w") as f:
                f.write("egg\n")

            with self.open(path, "r") as f:
                self.assertEqual(f.read(), "egg\n")

        check_path_succeeds(FakePath(support.TESTFN))
        check_path_succeeds(FakePath(support.TESTFN.encode('utf-8')))

        with self.open(support.TESTFN, "w") as f:
            bad_path = FakePath(f.fileno())
            with self.assertRaises(TypeError):
                self.open(bad_path, 'w')

        bad_path = FakePath(None)
        with self.assertRaises(TypeError):
            self.open(bad_path, 'w')

        bad_path = FakePath(FloatingPointError)
        with self.assertRaises(FloatingPointError):
            self.open(bad_path, 'w')

        # ensure that refcounting is correct with some error conditions
        with self.assertRaisesRegex(ValueError, 'read/write/append mode'):
            self.open(FakePath(support.TESTFN), 'rwxa')

class CIOTest(IOTest, unittest.TestCase):
    open = io.open
    io = io

class PyIOTest(IOTest, unittest.TestCase):
    open = staticmethod(pyio.open)
    io = pyio

class WinnanIOTest(IOTest, unittest.TestCase):
    open = staticmethod(winnan.open)
    io = io


class BufferedWriterTest(object):
    write_mode = "wb"

    def test_truncate(self):
        # Truncate implicitly flushes the buffer.
        self.addCleanup(support.unlink, support.TESTFN)
        with self.open(support.TESTFN, self.write_mode, buffering=0) as raw:
            bufio = self.tp(raw, 8)
            bufio.write(b"abcdef")
            self.assertEqual(bufio.truncate(3), 3)
            self.assertEqual(bufio.tell(), 6)
        with self.open(support.TESTFN, "rb", buffering=0) as f:
            self.assertEqual(f.read(), b"abc")

    @unittest.skipIf(sys.version_info < (3, 7), 'requires fix for issue32228')
    def test_truncate_after_write(self):
        # Ensure that truncate preserves the file position after
        # writes longer than the buffer size.
        # Issue: https://bugs.python.org/issue32228
        self.addCleanup(support.unlink, support.TESTFN)
        with self.open(support.TESTFN, "wb") as f:
            # Fill with some buffer
            f.write(b'\x00' * 10000)
        buffer_sizes = [8192, 4096, 200]
        for buffer_size in buffer_sizes:
            with self.open(support.TESTFN, "r+b", buffering=buffer_size) as f:
                f.write(b'\x00' * (buffer_size + 1))
                # After write write_pos and write_end are set to 0
                f.read(1)
                # read operation makes sure that pos != raw_pos
                f.truncate()
                self.assertEqual(f.tell(), buffer_size + 2)

class CBufferedWriterTest(BufferedWriterTest, unittest.TestCase):
    open = io.open
    tp = io.BufferedWriter

class PyBufferedWriterTest(BufferedWriterTest, unittest.TestCase):
    open = staticmethod(pyio.open)
    tp = pyio.BufferedWriter

class WinnanBufferedWriterTest(BufferedWriterTest, unittest.TestCase):
    open = staticmethod(winnan.open)
    tp = io.BufferedWriter


# To fully exercise seek/tell, the StatefulIncrementalDecoder has these
# properties:
#   - A single output character can correspond to many bytes of input.
#   - The number of input bytes to complete the character can be
#     undetermined until the last input byte is received.
#   - The number of input bytes can vary depending on previous input.
#   - A single input byte can correspond to many characters of output.
#   - The number of output characters can be undetermined until the
#     last input byte is received.
#   - The number of output characters can vary depending on previous input.

class StatefulIncrementalDecoder(codecs.IncrementalDecoder):
    """
    For testing seek/tell behavior with a stateful, buffering decoder.

    Input is a sequence of words.  Words may be fixed-length (length set
    by input) or variable-length (period-terminated).  In variable-length
    mode, extra periods are ignored.  Possible words are:
      - 'i' followed by a number sets the input length, I (maximum 99).
        When I is set to 0, words are space-terminated.
      - 'o' followed by a number sets the output length, O (maximum 99).
      - Any other word is converted into a word followed by a period on
        the output.  The output word consists of the input word truncated
        or padded out with hyphens to make its length equal to O.  If O
        is 0, the word is output verbatim without truncating or padding.
    I and O are initially set to 1.  When I changes, any buffered input is
    re-scanned according to the new I.  EOF also terminates the last word.
    """

    def __init__(self, errors='strict'):
        codecs.IncrementalDecoder.__init__(self, errors)
        self.reset()

    def __repr__(self):
        return '<SID %x>' % id(self)

    def reset(self):
        self.i = 1
        self.o = 1
        self.buffer = bytearray()

    def getstate(self):
        i, o = self.i ^ 1, self.o ^ 1 # so that flags = 0 after reset()
        return bytes(self.buffer), i*100 + o

    def setstate(self, state):
        buffer, io = state
        self.buffer = bytearray(buffer)
        i, o = divmod(io, 100)
        self.i, self.o = i ^ 1, o ^ 1

    def decode(self, input, final=False):
        output = ''
        for b in input:
            if self.i == 0: # variable-length, terminated with period
                if b in ('.', ord('.')):
                    if self.buffer:
                        output += self.process_word()
                else:
                    self.buffer.append(b)
            else: # fixed-length, terminate after self.i bytes
                self.buffer.append(b)
                if len(self.buffer) == self.i:
                    output += self.process_word()
        if final and self.buffer: # EOF terminates the last word
            output += self.process_word()
        return output

    def process_word(self):
        output = ''
        if self.buffer[0] == ord('i'):
            self.i = min(99, int(self.buffer[1:] or 0)) # set input length
        elif self.buffer[0] == ord('o'):
            self.o = min(99, int(self.buffer[1:] or 0)) # set output length
        else:
            output = self.buffer.decode('ascii')
            if len(output) < self.o:
                output += '-'*self.o # pad out with hyphens
            if self.o:
                output = output[:self.o] # truncate to output length
            output += '.'
        self.buffer = bytearray()
        return output

    codecEnabled = False

    @classmethod
    def lookupTestDecoder(cls, name):
        if cls.codecEnabled and name == 'test_decoder':
            latin1 = codecs.lookup('latin-1')
            return codecs.CodecInfo(
                name='test_decoder', encode=latin1.encode, decode=None,
                incrementalencoder=None,
                streamreader=None, streamwriter=None,
                incrementaldecoder=cls)

# Register the previous decoder for testing.
# Disabled by default, tests will enable it.
codecs.register(StatefulIncrementalDecoder.lookupTestDecoder)


class StatefulIncrementalDecoderTest(unittest.TestCase):
    """
    Make sure the StatefulIncrementalDecoder actually works.
    """

    test_cases = [
        # I=1, O=1 (fixed-length input == fixed-length output)
        (b'abcd', False, 'a.b.c.d.'),
        # I=0, O=0 (variable-length input, variable-length output)
        (b'oiabcd', True, 'abcd.'),
        # I=0, O=0 (should ignore extra periods)
        (b'oi...abcd...', True, 'abcd.'),
        # I=0, O=6 (variable-length input, fixed-length output)
        (b'i.o6.x.xyz.toolongtofit.', False, 'x-----.xyz---.toolon.'),
        # I=2, O=6 (fixed-length input < fixed-length output)
        (b'i.i2.o6xyz', True, 'xy----.z-----.'),
        # I=6, O=3 (fixed-length input > fixed-length output)
        (b'i.o3.i6.abcdefghijklmnop', True, 'abc.ghi.mno.'),
        # I=0, then 3; O=29, then 15 (with longer output)
        (b'i.o29.a.b.cde.o15.abcdefghijabcdefghij.i3.a.b.c.d.ei00k.l.m', True,
         'a----------------------------.' +
         'b----------------------------.' +
         'cde--------------------------.' +
         'abcdefghijabcde.' +
         'a.b------------.' +
         '.c.------------.' +
         'd.e------------.' +
         'k--------------.' +
         'l--------------.' +
         'm--------------.')
    ]

    def test_decoder(self):
        # Try a few one-shot test cases.
        for input, eof, output in self.test_cases:
            d = StatefulIncrementalDecoder()
            self.assertEqual(d.decode(input, eof), output)

        # Also test an unfinished decode, followed by forcing EOF.
        d = StatefulIncrementalDecoder()
        self.assertEqual(d.decode(b'oiabcd'), '')
        self.assertEqual(d.decode(b'', 1), 'abcd.')

class TextIOWrapperTest(object):

    def setUp(self):
        self.testdata = b"AAA\r\nBBB\rCCC\r\nDDD\nEEE\r\n"
        self.normalized = b"AAA\nBBB\nCCC\nDDD\nEEE\n".decode("ascii")
        support.unlink(support.TESTFN)

    def tearDown(self):
        support.unlink(support.TESTFN)

    # Systematic tests of the text I/O API

    def test_basic_io(self):
        for chunksize in (1, 2, 3, 4, 5, 15, 16, 17, 31, 32, 33, 63, 64, 65):
            for enc in "ascii", "latin-1", "utf-8" :# , "utf-16-be", "utf-16-le":
                f = self.open(support.TESTFN, "w+", encoding=enc)
                f._CHUNK_SIZE = chunksize
                self.assertEqual(f.write("abc"), 3)
                f.close()
                f = self.open(support.TESTFN, "r+", encoding=enc)
                f._CHUNK_SIZE = chunksize
                self.assertEqual(f.tell(), 0)
                self.assertEqual(f.read(), "abc")
                cookie = f.tell()
                self.assertEqual(f.seek(0), 0)
                self.assertEqual(f.read(None), "abc")
                f.seek(0)
                self.assertEqual(f.read(2), "ab")
                self.assertEqual(f.read(1), "c")
                self.assertEqual(f.read(1), "")
                self.assertEqual(f.read(), "")
                self.assertEqual(f.tell(), cookie)
                self.assertEqual(f.seek(0), 0)
                self.assertEqual(f.seek(0, 2), cookie)
                self.assertEqual(f.write("def"), 3)
                self.assertEqual(f.seek(cookie), cookie)
                self.assertEqual(f.read(), "def")
                if enc.startswith("utf"):
                    self.multi_line_test(f, enc)
                f.close()

    def multi_line_test(self, f, enc):
        f.seek(0)
        f.truncate()
        sample = "s\xff\u0fff\uffff"
        wlines = []
        for size in (0, 1, 2, 3, 4, 5, 30, 31, 32, 33, 62, 63, 64, 65, 1000):
            chars = []
            for i in range(size):
                chars.append(sample[i % len(sample)])
            line = "".join(chars) + "\n"
            wlines.append((f.tell(), line))
            f.write(line)
        f.seek(0)
        rlines = []
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                break
            rlines.append((pos, line))
        self.assertEqual(rlines, wlines)

    def test_telling(self):
        f = self.open(support.TESTFN, "w+", encoding="utf-8")
        p0 = f.tell()
        f.write("\xff\n")
        p1 = f.tell()
        f.write("\xff\n")
        p2 = f.tell()
        f.seek(0)
        self.assertEqual(f.tell(), p0)
        self.assertEqual(f.readline(), "\xff\n")
        self.assertEqual(f.tell(), p1)
        self.assertEqual(f.readline(), "\xff\n")
        self.assertEqual(f.tell(), p2)
        f.seek(0)
        for line in f:
            self.assertEqual(line, "\xff\n")
            self.assertRaises((IOError, OSError), f.tell)
        self.assertEqual(f.tell(), p2)
        f.close()

    def test_seeking(self):
        chunk_size = _default_chunk_size()
        prefix_size = chunk_size - 2
        u_prefix = "a" * prefix_size
        prefix = bytes(u_prefix.encode("utf-8"))
        self.assertEqual(len(u_prefix), len(prefix))
        u_suffix = "\u8888\n"
        suffix = bytes(u_suffix.encode("utf-8"))
        line = prefix + suffix
        with self.open(support.TESTFN, "wb") as f:
            f.write(line*2)
        with self.open(support.TESTFN, "r", encoding="utf-8") as f:
            s = f.read(prefix_size)
            self.assertEqual(s, prefix.decode("ascii"))
            self.assertEqual(f.tell(), prefix_size)
            self.assertEqual(f.readline(), u_suffix)

    def test_seeking_too(self):
        # Regression test for a specific bug
        data = b'\xe0\xbf\xbf\n'
        with self.open(support.TESTFN, "wb") as f:
            f.write(data)
        with self.open(support.TESTFN, "r", encoding="utf-8") as f:
            f._CHUNK_SIZE  # Just test that it exists
            f._CHUNK_SIZE = 2
            f.readline()
            f.tell()

    def test_seek_and_tell(self):
        #Test seek/tell using the StatefulIncrementalDecoder.
        # Make test faster by doing smaller seeks
        CHUNK_SIZE = 128

        def test_seek_and_tell_with_data(data, min_pos=0):
            """Tell/seek to various points within a data stream and ensure
            that the decoded data returned by read() is consistent."""
            f = self.open(support.TESTFN, 'wb')
            f.write(data)
            f.close()
            f = self.open(support.TESTFN, encoding='test_decoder')
            f._CHUNK_SIZE = CHUNK_SIZE
            decoded = f.read()
            f.close()

            for i in range(min_pos, len(decoded) + 1): # seek positions
                for j in [1, 5, len(decoded) - i]: # read lengths
                    f = self.open(support.TESTFN, encoding='test_decoder')
                    self.assertEqual(f.read(i), decoded[:i])
                    cookie = f.tell()
                    self.assertEqual(f.read(j), decoded[i:i + j])
                    f.seek(cookie)
                    self.assertEqual(f.read(), decoded[i:])
                    f.close()

        # Enable the test decoder.
        StatefulIncrementalDecoder.codecEnabled = 1

        # Run the tests.
        try:
            # Try each test case.
            for input, _, _ in StatefulIncrementalDecoderTest.test_cases:
                test_seek_and_tell_with_data(input)

            # Position each test case so that it crosses a chunk boundary.
            for input, _, _ in StatefulIncrementalDecoderTest.test_cases:
                offset = CHUNK_SIZE - len(input)//2
                prefix = b'.'*offset
                # Don't bother seeking into the prefix (takes too long).
                min_pos = offset*2
                test_seek_and_tell_with_data(prefix + input, min_pos)

        # Ensure our test decoder won't interfere with subsequent tests.
        finally:
            StatefulIncrementalDecoder.codecEnabled = 0

    def test_append_bom(self):
        # The BOM is not written again when appending to a non-empty file
        filename = support.TESTFN
        for charset in ('utf-8-sig', 'utf-16', 'utf-32'):
            with self.open(filename, 'w', encoding=charset) as f:
                f.write('aaa')
                pos = f.tell()
            with self.open(filename, 'rb') as f:
                self.assertEqual(f.read(), 'aaa'.encode(charset))

            with self.open(filename, 'a', encoding=charset) as f:
                f.write('xxx')
            with self.open(filename, 'rb') as f:
                self.assertEqual(f.read(), 'aaaxxx'.encode(charset))

    def test_seek_bom(self):
        # Same test, but when seeking manually
        filename = support.TESTFN
        for charset in ('utf-8-sig', 'utf-16', 'utf-32'):
            with self.open(filename, 'w', encoding=charset) as f:
                f.write('aaa')
                pos = f.tell()
            with self.open(filename, 'r+', encoding=charset) as f:
                f.seek(pos)
                f.write('zzz')
                f.seek(0)
                f.write('bbb')
            with self.open(filename, 'rb') as f:
                self.assertEqual(f.read(), 'bbbzzz'.encode(charset))

    @unittest.skipIf(sys.version_info < (3, 4, 4), 'requires fix for issue22982')
    def test_seek_append_bom(self):
        # Same test, but first seek to the start and then to the end
        filename = support.TESTFN
        for charset in ('utf-8-sig', 'utf-16', 'utf-32'):
            with self.open(filename, 'w', encoding=charset) as f:
                f.write('aaa')
            with self.open(filename, 'a', encoding=charset) as f:
                f.seek(0)
                f.seek(0, self.io.SEEK_END)
                f.write('xxx')
            with self.open(filename, 'rb') as f:
                self.assertEqual(f.read(), 'aaaxxx'.encode(charset))

    def test_errors_property(self):
        with self.open(support.TESTFN, "w") as f:
            self.assertEqual(f.errors, "strict")
        with self.open(support.TESTFN, "w", errors="replace") as f:
            self.assertEqual(f.errors, "replace")


class CTextIOWrapperTest(TextIOWrapperTest, unittest.TestCase):
    open = io.open
    io = io


class PyTextIOWrapperTest(TextIOWrapperTest, unittest.TestCase):
    open = staticmethod(pyio.open)
    io = pyio


class WinnanTextIOWrapperTest(TextIOWrapperTest, unittest.TestCase):
    open = staticmethod(winnan.open)
    io = io


# XXX Tests for open()

class MiscIOTest(object):

    def tearDown(self):
        support.unlink(support.TESTFN)

    def test_attributes(self):
        f = self.open(support.TESTFN, "wb", buffering=0)
        self.assertEqual(f.mode, "wb")
        f.close()

        expected_warnings = (('', DeprecationWarning),) if sys.version_info >= (3, 4) else ()
        with support.check_warnings(*expected_warnings):
            f = self.open(support.TESTFN, "U")
        self.assertEqual(f.name,            support.TESTFN)
        self.assertEqual(f.buffer.name,     support.TESTFN)
        self.assertEqual(f.buffer.raw.name, support.TESTFN)
        self.assertEqual(f.mode,            "U")
        self.assertEqual(f.buffer.mode,     "rb")
        self.assertEqual(f.buffer.raw.mode, "rb")
        f.close()

        f = self.open(support.TESTFN, "w+")
        self.assertEqual(f.mode,            "w+")
        self.assertEqual(f.buffer.mode,     "rb+") # Does it really matter?
        self.assertEqual(f.buffer.raw.mode, "rb+")

        g = self.open(f.fileno(), "wb", closefd=False)
        self.assertEqual(g.mode,     "wb")
        self.assertEqual(g.raw.mode, "wb")
        self.assertEqual(g.name,     f.fileno())
        self.assertEqual(g.raw.name, f.fileno())
        f.close()
        g.close()

    def test_io_after_close(self):
        for kwargs in [
                {"mode": "w"},
                {"mode": "wb"},
                {"mode": "w", "buffering": 1},
                {"mode": "w", "buffering": 2},
                {"mode": "wb", "buffering": 0},
                {"mode": "r"},
                {"mode": "rb"},
                {"mode": "r", "buffering": 1},
                {"mode": "r", "buffering": 2},
                {"mode": "rb", "buffering": 0},
                {"mode": "w+"},
                {"mode": "w+b"},
                {"mode": "w+", "buffering": 1},
                {"mode": "w+", "buffering": 2},
                {"mode": "w+b", "buffering": 0},
            ]:
            f = self.open(support.TESTFN, **kwargs)
            f.close()
            self.assertRaises(ValueError, f.flush)
            self.assertRaises(ValueError, f.fileno)
            self.assertRaises(ValueError, f.isatty)
            self.assertRaises(ValueError, f.__iter__)
            if hasattr(f, "peek"):
                self.assertRaises(ValueError, f.peek, 1)
            self.assertRaises(ValueError, f.read)
            if hasattr(f, "read1"):
                self.assertRaises(ValueError, f.read1, 1024)
                self.assertRaises((TypeError, ValueError), f.read1)
            if hasattr(f, "readall"):
                self.assertRaises(ValueError, f.readall)
            if hasattr(f, "readinto"):
                self.assertRaises(ValueError, f.readinto, bytearray(1024))
            if hasattr(f, "readinto1"):
                self.assertRaises(ValueError, f.readinto1, bytearray(1024))
            self.assertRaises(ValueError, f.readline)
            self.assertRaises(ValueError, f.readlines)
            self.assertRaises(ValueError, f.readlines, 1)
            self.assertRaises(ValueError, f.seek, 0)
            self.assertRaises(ValueError, f.tell)
            self.assertRaises(ValueError, f.truncate)
            self.assertRaises(ValueError, f.write,
                              b"" if "b" in kwargs['mode'] else "")
            self.assertRaises(ValueError, f.writelines, [])
            self.assertRaises(ValueError, next, f)

    @unittest.skipIf(sys.version_info < (3, 2), 'requires ResourceWarning support')
    def _check_warn_on_dealloc(self, *args, **kwargs):
        f = self.open(*args, **kwargs)
        r = repr(f)
        with self.assertWarns(ResourceWarning) as cm:
            f = None
            support.gc_collect()
        self.assertIn(r, str(cm.warning.args[0]))

    def test_warn_on_dealloc(self):
        self._check_warn_on_dealloc(support.TESTFN, "wb", buffering=0)

        # pyio.IOBase.__del__() calls close() on the underlying file object before
        # pyio.FileIO.__del__() is called. This causes pyio.FileIO.__del__() to not log a warning
        # message when the file object is being destructed.
        if self.io != pyio:
            self._check_warn_on_dealloc(support.TESTFN, "wb")
            self._check_warn_on_dealloc(support.TESTFN, "w")

    @unittest.skipIf(sys.version_info < (3, 2), 'requires ResourceWarning support')
    def _check_warn_on_dealloc_fd(self, *args, **kwargs):
        fds = []
        def cleanup_fds():
            for fd in fds:
                try:
                    os.close(fd)
                except OSError as e:
                    if e.errno != errno.EBADF:
                        raise
        self.addCleanup(cleanup_fds)
        r, w = os.pipe()
        fds += r, w
        self._check_warn_on_dealloc(r, *args, **kwargs)
        # When using closefd=False, there's no warning
        r, w = os.pipe()
        fds += r, w
        with warnings.catch_warnings(record=True) as recorded:
            warnings.filterwarnings('always', category=ResourceWarning)
            self.open(r, *args, closefd=False, **kwargs)
            support.gc_collect()
        self.assertEqual(recorded, [])

    def test_warn_on_dealloc_fd(self):
        self._check_warn_on_dealloc_fd("rb", buffering=0)

        # pyio.IOBase.__del__() calls close() on the underlying file object before
        # pyio.FileIO.__del__() is called. This causes pyio.FileIO.__del__() to not log a warning
        # message when the file object is being destructed.
        if self.io != pyio:
            self._check_warn_on_dealloc_fd("rb")
            self._check_warn_on_dealloc_fd("r")


    @unittest.skipIf(sys.version_info < (3, 2), 'requires fix for issue10180')
    def test_pickling(self):
        # Pickling file objects is forbidden
        for kwargs in [
                {"mode": "w"},
                {"mode": "wb"},
                {"mode": "wb", "buffering": 0},
                {"mode": "r"},
                {"mode": "rb"},
                {"mode": "rb", "buffering": 0},
                {"mode": "w+"},
                {"mode": "w+b"},
                {"mode": "w+b", "buffering": 0},
            ]:
            for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
                with self.open(support.TESTFN, **kwargs) as f:
                    self.assertRaises(TypeError, pickle.dumps, f, protocol)

    def test_nonblock_pipe_write_bigbuf(self):
        self._test_nonblock_pipe_write(16*1024)

    def test_nonblock_pipe_write_smallbuf(self):
        self._test_nonblock_pipe_write(1024)

    @unittest.skipUnless(hasattr(os, 'set_blocking'),
                         'os.set_blocking() required for this test')
    def _test_nonblock_pipe_write(self, bufsize):
        sent = []
        received = []
        r, w = os.pipe()
        os.set_blocking(r, False)
        os.set_blocking(w, False)

        # To exercise all code paths in the C implementation we need
        # to play with buffer sizes.  For instance, if we choose a
        # buffer size less than or equal to _PIPE_BUF (4096 on Linux)
        # then we will never get a partial write of the buffer.
        rf = self.open(r, mode='rb', closefd=True, buffering=bufsize)
        wf = self.open(w, mode='wb', closefd=True, buffering=bufsize)

        with rf, wf:
            for N in 9999, 73, 7574:
                try:
                    i = 0
                    while True:
                        msg = bytes([i % 26 + 97]) * N
                        sent.append(msg)
                        wf.write(msg)
                        i += 1

                except self.io.BlockingIOError as e:
                    self.assertEqual(e.args[0], errno.EAGAIN)
                    self.assertEqual(e.args[2], e.characters_written)
                    sent[-1] = sent[-1][:e.characters_written]
                    received.append(rf.read())
                    msg = b'BLOCKED'
                    wf.write(msg)
                    sent.append(msg)

            while True:
                try:
                    wf.flush()
                    break
                except self.io.BlockingIOError as e:
                    self.assertEqual(e.args[0], errno.EAGAIN)
                    self.assertEqual(e.args[2], e.characters_written)
                    self.assertEqual(e.characters_written, 0)
                    received.append(rf.read())

            received += iter(rf.read, None)

        sent, received = b''.join(sent), b''.join(received)
        self.assertEqual(sent, received)
        self.assertTrue(wf.closed)
        self.assertTrue(rf.closed)

    @unittest.skipIf(sys.version_info < (3, 3), "requires mode 'x' support")
    def test_create_fail(self):
        # 'x' mode fails if file is existing
        with self.open(support.TESTFN, 'w'):
            pass
        self.assertRaises(FileExistsError, self.open, support.TESTFN, 'x')

    @unittest.skipIf(sys.version_info < (3, 3), "requires mode 'x' support")
    def test_create_writes(self):
        # 'x' mode opens for writing
        with self.open(support.TESTFN, 'xb') as f:
            f.write(b"spam")
        with self.open(support.TESTFN, 'rb') as f:
            self.assertEqual(b"spam", f.read())

    @unittest.skipIf(sys.version_info < (3, 3), "requires mode 'x' support")
    def test_open_allargs(self):
        # there used to be a buffer overflow in the parser for rawmode
        self.assertRaises(ValueError, self.open, support.TESTFN, 'rwax+')

class CMiscIOTest(MiscIOTest, unittest.TestCase):
    open = io.open
    io = io

class PyMiscIOTest(MiscIOTest, unittest.TestCase):
    open = staticmethod(pyio.open)
    io = pyio

class WinnanMiscIOTest(MiscIOTest, unittest.TestCase):
    open = staticmethod(winnan.open)
    io = io

if __name__ == "__main__":
    unittest.main()
