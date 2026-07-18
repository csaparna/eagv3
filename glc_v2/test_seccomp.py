import ctypes

# Try to use prctl directly
PR_SET_SECCOMP = 22
SECCOMP_MODE_STRICT = 1

libc = ctypes.CDLL("libc.so.6")
# Don't actually run STRICT mode because it will kill the process immediately when it does a read/write to a non-open FD.
# Let's just check if we can load seccomp library
try:
    seccomp = ctypes.CDLL("libseccomp.so.2")
    print("libseccomp found")
except Exception as e:
    print(e)
