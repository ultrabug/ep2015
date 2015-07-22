#!/usr/bin/env python
"""This is a standalone python script handling watcher events from consul.

It receives a JSON from stdin containing the watcher event and passes
the Key and its base64 encoded Value to our EP2015 web service at
http:/{{ fqdn }}/set_kv which in turn will update the k/v
in all our datacenters.

Documentation : http://www.consul.io/docs/agent/watches.html
"""
import sys

from json import loads
from base64 import b64decode
try:
    # python3
    from urllib.request import urlopen
except:
    from urllib2 import urlopen

# get a valid JSON from stdin
json = loads(sys.stdin.read())

# get the key and decode its value
key = json['Key']
value = b64decode(json['Value']).decode()

# call our WS with the given key/value pair
url = 'http://{{ fqdn }}/set_kv'
url = '{}/{}/{}'.format(url, key, value)
urlopen(url)
