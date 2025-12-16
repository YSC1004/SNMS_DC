sudo dnf install python38 -y

/usr/bin/python3.8 -m pip install --user pymysql

/usr/bin/python3.8 -m pip install --user oracledb

/usr/bin/python3.8 -m pip install --user paramiko

/usr/bin/python3.8 -m pip install --user ping3

[sqinms_m02(ncadmin)(5GNMS_DC):/home/ncadmin/project/5GNMS_DC/server/src/Common] git --version
git version 2.43.5

[sqinms_m02(ncadmin)(5GNMS_DC):/home/ncadmin/SNMS/SNMS_DC] git init
[sqinms_m02(ncadmin)(5GNMS_DC):/home/ncadmin/SNMS/SNMS_DC] git remote add origin https://github.com/YSC1004/SNMS_DC.git
[sqinms_m02(ncadmin)(5GNMS_DC):/home/ncadmin/SNMS/SNMS_DC] git remote -v
origin  https://github.com/YSC1004/SNMS_DC.git (fetch)
origin  https://github.com/YSC1004/SNMS_DC.git (push)
[sqinms_m02(ncadmin)(5GNMS_DC):/home/ncadmin/SNMS/SNMS_DC] git config --global user.name "YSC1004"
[sqinms_m02(ncadmin)(5GNMS_DC):/home/ncadmin/SNMS/SNMS_DC] git config --global user.email "scyang@sqisoft.com"
[sqinms_m02(ncadmin)(5GNMS_DC):/home/ncadmin/SNMS/SNMS_DC] git config --global --list
user.name=YSC1004
user.email=scyang@sqisoft.com