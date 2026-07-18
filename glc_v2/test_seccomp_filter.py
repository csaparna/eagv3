import ctypes
import os
libc = ctypes.CDLL("libc.so.6", use_errno=True)
res = libc.prctl(22, 2, 0)
print(f"Result: {res}, errno: {ctypes.get_errno()}")
