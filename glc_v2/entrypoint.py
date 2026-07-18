import os
import sys
import ctypes

def main():
    if os.geteuid() == 0:
        try:
            import pwd
            uid = pwd.getpwnam('appuser').pw_uid
            os.setgid(uid)
            os.setuid(uid)
        except KeyError:
            pass

    try:
        seccomp = ctypes.CDLL("libseccomp.so.2")
        SCMP_ACT_ERRNO_EPERM = 0x00050001
        
        ctx = seccomp.seccomp_init(0x7fff0000) # SCMP_ACT_ALLOW
        
        # Block kill (62) and ptrace (101)
        seccomp.seccomp_rule_add(ctx, SCMP_ACT_ERRNO_EPERM, 62, 0)
        seccomp.seccomp_rule_add(ctx, SCMP_ACT_ERRNO_EPERM, 101, 0)
        
        seccomp.seccomp_load(ctx)
    except OSError:
        pass

    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])

if __name__ == "__main__":
    main()
