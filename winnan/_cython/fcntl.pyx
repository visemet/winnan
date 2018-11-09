# cython: language_level=3
#
# The os.O_CLOEXEC constant was added in Python 3.3. In Python 2, it is possible to use
# open(filename, "e") to atomically set O_CLOEXEC on the underlying file descriptor, but it isn't
# possible to do the same in Python 3. We therefore go through the effort of exposing O_CLOEXEC so
# the same syntax is possible with both Python 2 and Python 3.
#
# References:
#   - https://bugs.python.org/issue12105
#   - https://github.com/cython/cython/blob/0.29.1/Cython/Includes/posix/fcntl.pxd
#   - http://pubs.opengroup.org/onlinepubs/9699919799/basedefs/fcntl.h.html

cdef extern from "<fcntl.h>" nogil:

    cdef int _O_CLOEXEC "O_CLOEXEC"


O_CLOEXEC = _O_CLOEXEC
