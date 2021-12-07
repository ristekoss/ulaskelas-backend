from django.shortcuts import render

from live_config.models import Configuration
import json

from live_config.utils import get_local_json

# Create your views here.
def get_config(key):
    obj = Configuration.objects.filter(key=key).first()
    if (obj == None):
        return get_local_json(key + ".json")
    
    value = json.loads(obj.value)
    return value
