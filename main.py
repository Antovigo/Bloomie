#D3D3D3!/bin/env python3
import sys, os
import math
import requests

from datetime import datetime
import iso8601 # parse ISO 8601 dates
from fnmatch import fnmatch # match strings with wildcards

from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit
from PyQt5.QtWidgets import QTabWidget, QTableWidgetItem, QSizePolicy, QFormLayout, QLabel, QMessageBox

from PyQt5.QtCore import Qt
from PyQt5 import QtGui
import pyqtgraph as pg

import websocket

from copy_paste_table_widget import CopyPasteTableWidget # variant of QTableWidget that allows for copy-pasting
import mem
import data_management
import odmeter_api

class OD_reader_app(QMainWindow):

    def __init__(self):

        super().__init__()
        self.setWindowTitle("Bloomie")
        self.setGeometry(100, 100, 1200, 900)

        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        ################
        # Setup widget #
        ################

        setup_tab_layout = QHBoxLayout()
        
        ### Experiment setup ###

        # Experiment details fields
        exp_details_layout = QVBoxLayout()
        exp_details_form = QFormLayout()

        self.ip_field = QLineEdit()
        self.ip_field.setText(mem.config['default_ip_address'])
        self.ip_field.returnPressed.connect(self.connect_to_devices)
        exp_details_form.addRow('IP address:', self.ip_field)

        self.exp_details = {}
        self.exp_details['experiment_name'] = QLineEdit()
        mem.experiment_name = f'{datetime.now().strftime("%Y-%m-%d")}{mem.config["default_experiment_name"]}'
        self.exp_details['experiment_name'].setText(mem.experiment_name)
        exp_details_form.addRow('Experiment Name:', self.exp_details['experiment_name'])

        self.exp_details['interval'] = QLineEdit()
        self.exp_details['interval'].setText(str(mem.config['default_interval']))
        self.exp_details['interval'].setValidator(QtGui.QIntValidator())
        exp_details_form.addRow('Recording interval (s):', self.exp_details['interval'])

        self.exp_details['standard_curve'] = QLineEdit()
        self.exp_details['standard_curve'].setText(mem.config['default_standard_curve'])
        exp_details_form.addRow('Standard curve:', self.exp_details['standard_curve']) 

        self.exp_details['username'] = QLineEdit()
        self.exp_details['username'].setText(mem.config['default_username'])
        exp_details_form.addRow('Username:', self.exp_details['username'])

        # Experiment details bottom strip (connect)
        exp_details_bottom_strip = QHBoxLayout()
        self.exp_details_connect_button = QPushButton("Connect")
        self.exp_details_connect_button.setFixedWidth(100)
        self.exp_details_connect_button.setFocus()
        self.exp_details_connect_button.clicked.connect(self.connect_to_devices)
        exp_details_bottom_strip.addWidget(self.exp_details_connect_button)

        self.exp_details_note = QLabel()
        exp_details_bottom_strip.addWidget(self.exp_details_note)

        exp_details_layout.addLayout(exp_details_form)
        exp_details_layout.addStretch()
        exp_details_layout.addLayout(exp_details_bottom_strip)

        setup_tab_layout.addLayout(exp_details_layout)

        ### Reactor specification table ###

        self.reactors_table = CopyPasteTableWidget() # modified version of QTableWidget that allows for copy-pasting
        self.reactors_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        setup_tab_layout.addWidget(self.reactors_table)

        setup_widget = QWidget()
        setup_widget.setLayout(setup_tab_layout)
        self.tabs.addTab(setup_widget, "Setup")

        #######################
        # OD recording widget #
        #######################

        # Main widget and layout
        recording_tab_layout = QVBoxLayout()

        # Visualisation control strip
        self.highlight_strip_layout = QHBoxLayout()

        self.highlight_fields = {}
        for i in range(len(mem.config['highlight_colors'])):
            color = mem.config['highlight_colors'][i]

            highlight_field = QLineEdit()
            highlight_field.setStyleSheet(f"color: {color}")
            highlight_field.setPlaceholderText(f"Highlight keyword {i + 1}")
            highlight_field.editingFinished.connect(self.draw_plots)

            self.highlight_strip_layout.addWidget(highlight_field)
            self.highlight_fields[color] = highlight_field

        self.log_scale_button = QPushButton("Log Scale")
        self.log_scale_button.setCheckable(True)
        self.log_scale_button.clicked.connect(self.toggle_log_scale)
        self.highlight_strip_layout.addWidget(self.log_scale_button)

        self.freeze_button = QPushButton("Freeze plots")
        self.freeze_button.setCheckable(True)
        self.highlight_strip_layout.addWidget(self.freeze_button)

        # Plot area using PyQtGraph
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x = False, y = True)
        self.plot_widget.setAxisItems({'bottom': pg.DateAxisItem()})

        self.plot_widget.getAxis('left').setTextPen(mem.config['axis_text_color'])
        self.plot_widget.getAxis('bottom').setTextPen(mem.config['axis_text_color'])
        self.plot_widget.getAxis('left').setPen(mem.config['grid_color'])
        self.plot_widget.getAxis('bottom').setPen(mem.config['grid_color'])
        
        pg.setConfigOptions(antialias = mem.config['antialiasing'])

        # Strip of buttons for recording data
        self.record_strip_layout = QHBoxLayout()

        self.record_button = QPushButton("Record")
        self.record_button.setCheckable(True)
        self.record_button.clicked.connect(self.start_recording_loop)
        self.record_strip_layout.addWidget(self.record_button)

        self.folder_field = QLineEdit()
        self.folder_field.setText(mem.config['default_folder'])
        self.record_strip_layout.addWidget(self.folder_field)

        self.filename_field = QLineEdit()
        self.filename_field.setText(mem.experiment_name + '.tsv')
        self.record_strip_layout.addWidget(self.filename_field)

        # Annotation field: changes color while being edited, and black when the annotation is saved
        self.annotation = ''
        self.annotation_field = QLineEdit()
        self.annotation_field.setPlaceholderText('Live annotation (e.g. "growing")')

        def edit_annotation(self):
            self.annotation_field.setStyleSheet(f"color: {mem.config['highlight_colors'][0]}")

        def set_annotation(self):
            self.annotation = self.annotation_field.text()
            print(f'{datetime.now().isoformat()}: annotation changed to "{self.annotation}"')
            self.annotation_field.setStyleSheet("color: black")

        self.annotation_field.textChanged.connect(lambda: edit_annotation(self))
        self.annotation_field.editingFinished.connect(lambda: set_annotation(self))
        self.record_strip_layout.addWidget(self.annotation_field)

        self.record_strip_layout.addWidget(QLabel("Points:"))

        self.max_points_field = QLineEdit()
        self.max_points_field.setFixedWidth(50)
        self.max_points_field.setText(str(mem.config['max_points']))
        self.max_points_field.setValidator(QtGui.QIntValidator(1, mem.config['max_points']))
        self.max_points_field.setToolTip('Plot the last N points.')
        self.max_points_field.editingFinished.connect(self.draw_plots)
        self.record_strip_layout.addWidget(self.max_points_field)

        self.record_strip_layout.addWidget(QLabel("Downsample:"))

        self.downsample_field = QLineEdit()
        self.downsample_field.setFixedWidth(50)
        self.downsample_field.setText('1')
        self.downsample_field.setToolTip('Only plot every Nth point (all data is still recorded).')
        self.downsample_field.setValidator(QtGui.QIntValidator(1, mem.config['max_points']))
        self.downsample_field.editingFinished.connect(self.draw_plots)
        self.record_strip_layout.addWidget(self.downsample_field)

        # Build the tab layout
        recording_tab_layout.addLayout(self.record_strip_layout)
        recording_tab_layout.addWidget(self.plot_widget)
        recording_tab_layout.addLayout(self.highlight_strip_layout)

        recording_tab_widget = QWidget()
        recording_tab_widget.setLayout(recording_tab_layout)
        self.tabs.addTab(recording_tab_widget, "Measurement")

        # Initially disable the tab
        self.tabs.setTabEnabled(1, False)

        # Set websocket to receive data
        self.ws = websocket.WebSocket()

        # Try to connect to the default IP address (can be disabled in config)
        if mem.config['auto_connect']:
            self.connect_to_devices()

    def connect_to_devices(self):
        '''Connect to the devices at the IP address entered, and determine the number of devices/channels.'''

        mem.ip_address = self.ip_field.text()
        mem.experiment_name = self.exp_details['experiment_name'].text()
        self.filename_field.setText(mem.experiment_name + '.tsv') # update the filename field to match experiment name
        
        # Try to connect to the devices
        self.exp_details_note.setText(f'Connecting to {mem.ip_address}.')

        try:
            device_status = requests.get(f"http://{mem.ip_address}/api/device/", timeout = mem.config['connection_timeout']).json()
        except:
            device_status = []

        if device_status: # successfully connected to the devices
            self.exp_details_note.setText(f'Connected to {mem.ip_address}.')

            # Enable the recording tab
            self.tabs.setTabEnabled(1, True)

            # Set the devices and channels
            mem.ws_url = f"ws://{mem.ip_address}/api/ws/"
            mem.devices = [device['label'] for device in device_status]
            mem.channels = list(range(len(device_status[0]['channels'])))

            # Setup the reactors table
            self.setup_reactors_table()

            # Start the API
            print(f'Starting the API...')
            username = self.exp_details['username'].text()
            mem.api = odmeter_api.ODMeterSystem(user = username, server_addr = mem.ip_address)


        else: # failed to connect
            self.exp_details_note.setText(f'Failed to connect to the devices at {mem.ip_address}.')
            self.tabs.setTabEnabled(1, False)

    def setup_reactors_table(self):

        self.reactors_table.setRowCount(len(mem.channels))
        self.reactors_table.setColumnCount(len(mem.devices))
        self.reactors_table.setHorizontalHeaderLabels([f"Device {device}" for device in mem.devices])
        self.reactors_table.setVerticalHeaderLabels([f"Channel {channel}" for channel in mem.channels])

        # Fill in the table cells with placeholders
        for device_id, device in enumerate(mem.devices):

            mem.device_ids[device] = device_id # to find the column index for each device

            for channel_id in mem.channels:

                if mem.config['use_placeholder_names']:
                    item = QTableWidgetItem(f"D{device}C{channel_id}")
                else:
                    item = QTableWidgetItem("")

                item.setTextAlignment(Qt.AlignCenter)
                self.reactors_table.setItem(channel_id, device_id, item)

    def setup_data_file(self):
        '''Create a file to store the data.'''

        # Construct the filename
        folder = os.path.expanduser(self.folder_field.text())
        filename = os.path.expanduser(self.filename_field.text())
        mem.file_path = os.path.join(folder, filename)

        def make_headers():
            '''Create a new file with tab-separated headers.'''

            with open(mem.file_path, 'w') as file:
                print(f'Creating data file {mem.file_path}.')
                file.write("time\tdevice\tchannel\tname\tintensity\tintensity_blank\traw_od\tconverted_od\tannotation\n")

        if os.path.exists(mem.file_path): # The file already exists

            # Ask the user if they want to overwrite the file, append to it or cancel
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setText(f"The file '{mem.file_path}' already exists.")
            
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            msg_box.button(QMessageBox.Yes).setText("Overwrite")
            msg_box.button(QMessageBox.No).setText("Append data")
            msg_box.button(QMessageBox.No).setIcon(QtGui.QIcon.fromTheme("list-add"))
            msg_box.button(QMessageBox.Cancel).setText("Cancel")

            user_response = msg_box.exec()

            if user_response == QMessageBox.Yes:
                make_headers()
                return True

            elif user_response == QMessageBox.No:
                print(f'New data will be appended to {mem.file_path}.')
                return True

            else: # User canceled
                self.record_button.setChecked(False)
                return False
                
        else: # The file doesn't exist, create one with appropriate headers
            make_headers()
            return True

    def start_recording_loop(self):
        '''Start recording data. If the button is unchecked, the recording loop will stop at the next iteration.'''

        if self.record_button.isChecked(): # Only proceed if the button is being checked

            mem.recorder = data_management.data_recorder()

            # Prepare a file to save data to
            file_setup_succeeded = self.setup_data_file()

            if not file_setup_succeeded: # If the user canceled, stop here
                return

            # Update the reactors' labels
            mem.recorder.initialize_cultures()

            # Start the backend
            mem.recorder.start_backend()

            # Connect data reception to plotting
            mem.recorder.data_updated.connect(self.draw_plots)

            # Start recording data
            mem.recorder.start()

    def draw_line(self, culture, color, linewidth):
        '''Draw the curve for one culture.'''
        
        # Prepare the data to plot
        downsampling = int(self.downsample_field.text()) if self.downsample_field.text() else int()
        if not downsampling or downsampling < 1:
            downsampling = 1
            self.downsample_field.setText('1')

        max_points = int(self.max_points_field.text()) if self.max_points_field.text() else int()
        if not max_points or max_points < 1:
            max_points = 1
            self.max_points_field.setText('1')

        # Domnsample starting from the end, then keep only the <max_points> most recent points
        times_str = culture.times[::-downsampling][:max_points]
        ods = culture.ods[::-downsampling][:max_points]
        
        times = [iso8601.parse_date(t).timestamp() for t in times_str]

        # Plot the data
        pen = pg.mkPen(color = color, width = linewidth)
        self.plot_widget.plot(times, ods, pen = pen, name = culture.name)

        # Add the name of the culture at the end of the curve
        if not self.log_scale_button.isChecked() or ods[-1] > 0: # avoid log of negative numbers

            text = pg.TextItem(html=f'<div style="text-align: center"><span style="color: {color}">{culture.name}</span></div>')
            text.setAnchor((0, 0.5))
            font = pg.QtGui.QFont()
            font.setPointSize(12)
            font.setBold(True)
            text.setFont(font)

            try:
                # Last point is element 0 because the list is reversed
                if self.log_scale_button.isChecked():
                    text.setPos(times[0], math.log10(ods[0]))
                else:
                    text.setPos(times[0], ods[0])

            except:
                print('Error setting label position:')
                print(times)
                print(ods)

            self.plot_widget.addItem(text)

    def draw_plots(self):
        '''Draw plots of the data in <mem>. The cultures that match the regexes in the text fields will be highlighted
        in colors, while the rest is gray.'''

        if not mem.cultures:
            return

        # Pause plotting when the button is checked
        if self.freeze_button.isChecked():
            return

        self.plot_widget.clear()
 
        # Get highlight keywords from the text fields
        highlight_colors = {self.highlight_fields[color].text(): color for color in mem.config['highlight_colors'] \
                            if self.highlight_fields[color].text()}
        highlighted_cultures = {color:[] for color in mem.config['highlight_colors']}

        # Plot the cultures that are not highlighted in gray
        for device in mem.devices:
            for channel in mem.channels:

                if mem.cultures[device][channel]:

                    culture = mem.cultures[device][channel]
                    highlighted = False

                    for keyword, color in highlight_colors.items():
                        
                        # Check if the keyword is in the name, allowing '*' for a wild-card
                        if fnmatch(culture.name.lower(), f'*{keyword}*'.lower()) and not highlighted:
                            highlighted_cultures[color].append(culture)
                            highlighted = True

                    if not highlighted:
                        self.draw_line(culture, mem.config['normal_color'], mem.config['normal_line_width'])

        # Plot the highlighted cultures
        for color, cultures in highlighted_cultures.items():
            for culture in cultures:
                if culture.times: # Do not plot cultures without data
                    self.draw_line(culture, color, mem.config['highlight_line_width'])

        # Ensure the labels fit in the field of view
        self.plot_widget.getViewBox().autoRange(padding = mem.config['padding'])

    def toggle_log_scale(self):
        '''Switch log scale and redraw the plots.'''

        if self.log_scale_button.isChecked():
            self.plot_widget.setLogMode(y=True)
        else:
            self.plot_widget.setLogMode(y=False)

        self.draw_plots()

    def closeEvent(self, a0):
        '''Stop the recording loop and close the websocket when the window is closed.'''

        # Confirm before closing the window
        if self.record_button.isChecked():
            reply = QMessageBox.question(
                self,
                "Closing",
                "Recording is in progress. Are you sure you want to quit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
        
            confirmed = reply == QMessageBox.Yes

        else:
            confirmed = True

        # If the user confirms the exit, close the websocket and the API
        if confirmed:

            mem.running = False

            if mem.ws:
                if mem.ws.connected:
                    mem.ws.close()

            if mem.api:
                mem.api.experiments()[0].close()
                mem.api.remove_sample(mem.api.samples())
            
            a0.accept()  # Allow the window to close
        else:
            a0.ignore()  # Ignore the close event

if __name__ == "__main__":

    # Start the application
    app = QApplication(sys.argv)
    mem.main_window = OD_reader_app()
    mem.main_window.show()
    sys.exit(app.exec_())

