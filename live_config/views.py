from django.shortcuts import render

from live_config.models import Configuration
import json

# Create your views here.
def get_config(key):
    obj = Configuration.objects.filter(key=key).first()
    if (obj == None):
        return None
    
    value = json.loads(obj.value)
    return value
