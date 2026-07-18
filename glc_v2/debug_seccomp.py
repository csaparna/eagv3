import ctypes
import os

seccomp = ctypes.CDLL("libseccomp.so.2")
seccomp.seccomp_init.restype = ctypes.c_void_p
seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
seccomp.seccomp_load.argtypes = [ctypes.c_void_p]

SCMP_ACT_ERRNO_EPERM = 0x00050001
ctx = seccomp.seccomp_init(0x7fff0000) # ALLOW

if not ctx:
    print("seccomp_init failed! returning NULL")
else:
    print("seccomp_init succeeded!")
    res1 = seccomp.seccomp_rule_add(ctx, SCMP_ACT_ERRNO_EPERM, 62, 0)
    print("rule1 res:", res1)
    res2 = seccomp.seccomp_rule_add(ctx, SCMP_ACT_ERRNO_EPERM, 101, 0)
    print("rule2 res:", res2)
    res3 = seccomp.seccomp_load(ctx)
    print("load res:", res3)
