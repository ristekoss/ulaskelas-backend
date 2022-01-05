import os
import json

def get_local_json(filename):
    path = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(path, "defaultConfig/{}".format(filename))

    try:
        fd = open(filename, "r")
        as_json = json.load(fd)
        return as_json
    except KeyError:
        return None