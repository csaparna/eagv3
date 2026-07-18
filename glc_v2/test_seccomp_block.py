import os
import signal
import sys
import ctypes

try:
    seccomp = ctypes.CDLL("libseccomp.so.2")
except OSError:
    print("libseccomp not found, falling back")
    sys.exit(0)

# SCMP_ACT_KILL_PROCESS = 0x80000000
# SCMP_ACT_ERRNO = 0x00050000
SCMP_ACT_ERRNO_EPERM = 0x00050001
seccomp.seccomp_init.restype = ctypes.c_void_p
seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
seccomp.seccomp_load.argtypes = [ctypes.c_void_p]

# Get syscall number for kill (62 on x86_64)
# syscall 62 = kill
KILL_SYSCALL = 62

# Init with ALLOW
ctx = seccomp.seccomp_init(0x7fff0000) # SCMP_ACT_ALLOW
# Block kill
seccomp.seccomp_rule_add(ctx, SCMP_ACT_ERRNO_EPERM, KILL_SYSCALL, 0)
seccomp.seccomp_load(ctx)

print("Filter loaded. Attempting os.kill...")
try:
    os.kill(os.getpid(), signal.SIGTERM)
    print("Kill succeeded! (This is bad)")
except OSError as e:
    print(f"Kill failed as expected: {e}")
