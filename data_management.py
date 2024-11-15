#!/bin/env python3
'''Receive data from the OD readers.'''

from PyQt5.QtCore import QThread, pyqtSignal
import websocket
import json
import time
from datetime import datetime
from random import random
import traceback

import mem

class culture:
    '''Store information about a single reactor.'''

    def __init__(self, name):
        self.name = name
        self.times = []
        self.ods = []
        self.growth_rate = 1.05

class data_recorder(QThread):
    '''Receive data from the OD readers.'''

    data_updated = pyqtSignal()  # Define a custom signal

    def __init__(self):

        super().__init__()

    def initialize_cultures(self):
        '''Find the labels of the reactors from the reactor layout tab. If a cell is empty string, the reactor is inactive.'''
       
        # Create data structures to store the measurements
        mem.cultures = {}

        for device in mem.devices:

            mem.cultures[device] = []

            for channel in mem.channels:

                # Read the culture's label from the setup table
                reactor_label = mem.main_window.reactors_table.item(channel, mem.device_ids[device]).text()
                
                # Make a culture object to store temporary data
                mem.cultures[device].append(culture(reactor_label))

    def clear_backend(self):
        '''Clear the backend of any existing data.'''
        
        if not mem.config['simulation'] and mem.api:

            # Check for any existing experiments
            if mem.api.experiments():
                print('\nWarning: the backend is already listing experiments. You should restart it and restart this application.')

            # Stop the experiment if any
            for experiment in mem.api.experiments():
                try:
                    experiment.close()
                except:
                    
                    print('\nWarning: there was an error while clearing the backend:')
                    traceback.print_exc()

                    print('If the problem persists, try restarting the backend.\n')

            # Remove the samples
            mem.api.remove_sample(mem.api.samples())
                
    def start_backend(self):
        '''Connect to the API and tell the backed to start recording data.'''

        if not mem.config['simulation']:

            # Get data from the setup tab
            standard_curve = mem.main_window.exp_details['standard_curve'].text()
            recording_interval = int(mem.main_window.exp_details['interval'].text())
            mem.experiment_name = mem.main_window.exp_details['experiment_name'].text()

            # Clear the backend of any existing data
            self.clear_backend()

            # Create the samples on the backend side
            for device in mem.devices:
                for channel in mem.channels:

                    # channel is one-indexed in backend, zero-indexed in frontend
                    mem.api.create_samples(device, channel + 1, mem.cultures[device][channel].name, standard_curve)

            # Create the experiment on the backend side
            backend_experiment_name = f'mem.experiment_name_{round(datetime.now().timestamp())}' # avoid name conflicts
            mem.api.create_experiment(backend_experiment_name, samples = mem.api.samples(), interval = recording_interval)

            # Tell the backend to start recording
            print(f'Starting the experiment ({recording_interval}s interval).')
            mem.api.experiments()[0].start()

    def run(self):
        '''Run the data recording loop.'''

        # Connect to the websocket
        mem.ws = websocket.WebSocket()

        if not mem.config['simulation']:
            print(f'Connecting to websocket at {mem.ws_url}.')
            mem.ws.connect(mem.ws_url)
            print(f'Connected to websocket at {mem.ws_url}.')

        # Open the record file
        file = open(mem.file_path, 'a')

        # Run the data request loop
        mem.running = True

        while mem.running and mem.main_window.record_button.isChecked():

            # Wait for the next data point from the readers
            if not mem.config['simulation']:
                data = self.request_data()
            else:
                data = self.request_simulated_data()

            # Data is received as a list of reactors, batched by device
            for reading in data:
                device = reading['device']
                channel = int(reading['channel']) - 1 # one-indexed in backend, zero-indexed in frontend
                name = mem.cultures[device][channel].name
                time = reading['t']
                od = reading['converted_od']

                # Add the data to memory
                mem.cultures[device][channel].times.append(time)
                mem.cultures[device][channel].ods.append(od)

                # Write the data to the record file
                # columns: time, device, channel, name, intensity, intensity_blank, raw_od, converted_od, annotation
                new_line = f"{time}\t{device}\t{channel}\t{name}\t{reading['intensity']}\t" + \
                           f"{reading['intensity_blank']}\t{reading['raw_od']}\t{od}\t{mem.main_window.annotation}"

                file.write(new_line + '\n')

            # Emit the custom signal to indicate that new data is available (only after reading the last device)
            if data[-1]['device'] == mem.devices[-1] or mem.config['always_refresh']:
                self.data_updated.emit()

        # When the recording button is unchecked, stop the recording
        print('Recording stopped.')
        mem.running = False
        file.close()
        
    def request_data(self):
        '''Request data from the websocket. Data is returned when the next measurement is performed.
        The data is a list of dictionaries, each containing the readings for a single reactor.
        The keys are: t, device, channel, intensity, intensity_blank, raw_od, converted_od. 
        '''
        raw_data = mem.ws.recv()  # Receive data from websocket
        data = json.loads(raw_data)['readings']

        return data

    def request_simulated_data(self):
        time.sleep(mem.config['sim_data_rate'])

        simulated_data = []
        for device in mem.devices:
            for channel in mem.channels:
                new_time = datetime.now().isoformat()
                if mem.cultures[device][channel].ods:
                    new_od = mem.cultures[device][channel].ods[-1] * mem.cultures[device][channel].growth_rate
                else:
                    new_od = 0.01 * random()

                simulated_data.append({'t': new_time, 'device': device, 'channel': channel, 
                                       'intensity': 0, 'intensity_blank': 0, 'raw_od': new_od, 'converted_od': new_od})
        return simulated_data                

