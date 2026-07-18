import ctypes
s = ctypes.CDLL("libseccomp.so.2")
s.seccomp_init.restype = ctypes.c_void_p
s.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
s.seccomp_load.argtypes = [ctypes.c_void_p]
ctx = s.seccomp_init(0x7fff0000)
print("init done")
s.seccomp_rule_add(ctx, 0x00050001, 62, 0)
print("rule1 done")
s.seccomp_rule_add(ctx, 0x00050001, 101, 0)
print("rule2 done")
s.seccomp_load(ctx)
print("load done")
