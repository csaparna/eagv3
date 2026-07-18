import os, pwd
uid = pwd.getpwnam('nobody').pw_uid
os.setgid(uid)
os.setuid(uid)
