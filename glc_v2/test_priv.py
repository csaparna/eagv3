import os
import pwd
uid = pwd.getpwnam('appuser').pw_uid
os.setgid(uid)
os.setuid(uid)
print("UID dropped")
