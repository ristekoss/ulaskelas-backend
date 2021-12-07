import os
import json

def get_local_json(filename):
    path = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(path, "defaultConfig/{}".format(filename))

    with open(filename, "r") as fd:
        as_json = json.load(fd)
        return as_json