#!/bin/env python3
'''Global variables.'''

import os, yaml

# Load configuration
CONFIG_PATHS = [os.path.expanduser('~/.config/bloomie.yaml'), 'default_config.yaml']

for path in CONFIG_PATHS:
    if os.path.exists(path):
        with open(path, 'r') as config_file:
            config = yaml.safe_load(config_file)
            print('Loaded config from', path)
        break

main_window = None
api = None

# Devices properties
ip_address = '' # local ip address of the devices
ws_url = '' # url of websocket
ws = None # placeholder for websocket object

devices = [] # labels of the devices
channels = [] # should be 0 to 7
device_ids = {} # link a device's name to its zero-indexed id

# Recording properties
experiment_name = '' # name of the experiment
file_path = '' # path to write the data to
running = False # keeps track of whether recording is running
active_devices = [] # list of devices that are currently recording

api = None # placeholder for api object
recorder = None # placeholder for data recorder object

# Cultures properties
cultures = {}
