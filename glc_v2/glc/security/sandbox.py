import os
import ctypes

def apply_sandbox():
    try:
        seccomp = ctypes.CDLL("libseccomp.so.2")
        seccomp.seccomp_init.restype = ctypes.c_void_p
        seccomp.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p]
        seccomp.seccomp_load.argtypes = [ctypes.c_void_p]

        SCMP_ACT_ERRNO_EPERM = 0x00050001
        ctx = seccomp.seccomp_init(0x7fff0000) # ALLOW
        seccomp.seccomp_rule_add_array(ctx, SCMP_ACT_ERRNO_EPERM, 62, 0, None)
        seccomp.seccomp_rule_add_array(ctx, SCMP_ACT_ERRNO_EPERM, 101, 0, None)
        seccomp.seccomp_load(ctx)
    except OSError:
        pass

    if os.geteuid() == 0:
        try:
            import pwd
            uid = pwd.getpwnam('appuser').pw_uid
            os.setgid(uid)
            os.setuid(uid)
        except KeyError:
            pass

apply_sandbox()
