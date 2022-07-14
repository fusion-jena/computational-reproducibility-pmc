import config
from db import connect
from utils import base_dir_exists


print("Content:", base_dir_exists())
with connect() as s:
    print("DB:", s)
