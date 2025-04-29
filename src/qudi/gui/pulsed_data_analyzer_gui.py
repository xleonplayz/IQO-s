# -*- coding: utf-8 -*-
"""
This file contains the QuDi GUI for analyzing saved pulsed measurements.

Copyright (c) 2021, the qudi developers. See the AUTHORS.md file at the top-level directory of this
distribution and on <https://github.com/Ulm-IQO/qudi-iqo-modules/>

This file is part of qudi.

Qudi is free software: you can redistribute it and/or modify it under the terms of
the GNU Lesser General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Qudi is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with qudi.
If not, see <https://www.gnu.org/licenses/>.
"""

import os
import numpy as np
import pyqtgraph as pg
from enum import Enum

from PySide2 import QtCore, QtWidgets, QtGui

from qudi.core.module import GuiBase
from qudi.core.connector import Connector
from qudi.core.statusvariable import StatusVar
from qudi.util.colordefs import QudiPalettePale as palette
from qudi.util.widgets.scientific_spinbox import ScienDSpinBox, ScienSpinBox
from qudi.util.widgets.fitting import FitConfigurationDialog


class PulsedDataAnalyzerMainWindow(QtWidgets.QMainWindow):
    """
    Main window for the PulsedDataAnalyzer GUI
    """
    def __init__(self):
        # Initialize the parent
        super().__init__()
        
        # Set window properties
        self.setWindowTitle('Pulsed Data Analyzer')
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        self.centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralwidget)
        
        # Create main layout
        self.layout = QtWidgets.QVBoxLayout(self.centralwidget)
        
        # Create menu bar
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu('File')
        self.edit_menu = self.menu_bar.addMenu('Edit')
        self.view_menu = self.menu_bar.addMenu('View')
        self.tools_menu = self.menu_bar.addMenu('Tools')
        
        # Create actions
        self.action_load_raw_data = QtWidgets.QAction('Load Raw Data', self)
        self.action_load_laser_data = QtWidgets.QAction('Load Laser Data', self)
        self.action_load_signal_data = QtWidgets.QAction('Load Signal Data', self)
        self.action_save_figure = QtWidgets.QAction('Save Figure', self)
        self.action_export_state = QtWidgets.QAction('Export State', self)
        self.action_exit = QtWidgets.QAction('Exit', self)
        
        self.action_fit_settings = QtWidgets.QAction('Fit Settings', self)
        
        # Add actions to menu
        self.file_menu.addAction(self.action_load_raw_data)
        self.file_menu.addAction(self.action_load_laser_data)
        self.file_menu.addAction(self.action_load_signal_data)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_save_figure)
        self.file_menu.addAction(self.action_export_state)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_exit)
        
        self.edit_menu.addAction(self.action_fit_settings)
        
        # Create toolbar
        self.toolbar = QtWidgets.QToolBar('Main Toolbar')
        self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolbar)
        
        # Add actions to toolbar
        self.toolbar.addAction(self.action_load_raw_data)
        self.toolbar.addAction(self.action_load_laser_data)
        self.toolbar.addAction(self.action_load_signal_data)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_save_figure)
        self.toolbar.addAction(self.action_export_state)
        
        # Create splitter for main area
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.layout.addWidget(self.main_splitter)
        
        # Create left panel (controls and parameters)
        self.left_panel = QtWidgets.QWidget()
        self.left_panel_layout = QtWidgets.QVBoxLayout()
        self.left_panel.setLayout(self.left_panel_layout)
        self.left_panel.setMinimumWidth(300)
        self.left_panel.setMaximumWidth(400)
        
        # Create right panel (plots)
        self.right_panel = QtWidgets.QWidget()
        self.right_panel_layout = QtWidgets.QVBoxLayout()
        self.right_panel.setLayout(self.right_panel_layout)
        
        # Add panels to splitter
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)
        
        # Create control groups for left panel
        self.file_group = QtWidgets.QGroupBox('Loaded Files')
        self.file_group_layout = QtWidgets.QVBoxLayout()
        self.file_group.setLayout(self.file_group_layout)
        self.left_panel_layout.addWidget(self.file_group)
        
        self.raw_data_label = QtWidgets.QLabel('Raw Data: None')
        self.laser_data_label = QtWidgets.QLabel('Laser Data: None')
        self.signal_data_label = QtWidgets.QLabel('Signal Data: None')
        
        self.file_group_layout.addWidget(self.raw_data_label)
        self.file_group_layout.addWidget(self.laser_data_label)
        self.file_group_layout.addWidget(self.signal_data_label)
        
        # Create analysis controls
        self.analysis_group = QtWidgets.QGroupBox('Analysis Controls')
        self.analysis_group_layout = QtWidgets.QVBoxLayout()
        self.analysis_group.setLayout(self.analysis_group_layout)
        self.left_panel_layout.addWidget(self.analysis_group)
        
        # Alternative data type
        self.alt_data_layout = QtWidgets.QHBoxLayout()
        self.alt_data_label = QtWidgets.QLabel('Alternative Data:')
        self.alt_data_combobox = QtWidgets.QComboBox()
        self.alt_data_combobox.addItems(['None', 'Delta', 'FFT'])
        self.alt_data_layout.addWidget(self.alt_data_label)
        self.alt_data_layout.addWidget(self.alt_data_combobox)
        self.analysis_group_layout.addLayout(self.alt_data_layout)
        
        # Fit controls
        self.fit_layout = QtWidgets.QHBoxLayout()
        self.fit_label = QtWidgets.QLabel('Fit Method:')
        self.fit_combobox = QtWidgets.QComboBox()
        self.fit_alt_checkbox = QtWidgets.QCheckBox('Use Alt Data')
        self.fit_button = QtWidgets.QPushButton('Fit')
        self.fit_layout.addWidget(self.fit_label)
        self.fit_layout.addWidget(self.fit_combobox)
        self.fit_layout.addWidget(self.fit_alt_checkbox)
        self.fit_layout.addWidget(self.fit_button)
        self.analysis_group_layout.addLayout(self.fit_layout)
        
        # Plot display options
        self.display_options_layout = QtWidgets.QHBoxLayout()
        self.show_error_checkbox = QtWidgets.QCheckBox('Show Errors')
        self.show_error_checkbox.setChecked(True)
        self.display_options_layout.addWidget(self.show_error_checkbox)
        self.analysis_group_layout.addLayout(self.display_options_layout)
        
        # Create state analysis group
        self.state_group = QtWidgets.QGroupBox('Quantum State Analysis')
        self.state_group_layout = QtWidgets.QVBoxLayout()
        self.state_group.setLayout(self.state_group_layout)
        self.left_panel_layout.addWidget(self.state_group)
        
        # Threshold for state discrimination
        self.threshold_layout = QtWidgets.QHBoxLayout()
        self.threshold_label = QtWidgets.QLabel('Threshold:')
        self.threshold_spinbox = QtWidgets.QDoubleSpinBox()
        self.threshold_spinbox.setRange(0.0, 1.0)
        self.threshold_spinbox.setSingleStep(0.05)
        self.threshold_spinbox.setValue(0.5)
        self.analyze_button = QtWidgets.QPushButton('Analyze State')
        self.threshold_layout.addWidget(self.threshold_label)
        self.threshold_layout.addWidget(self.threshold_spinbox)
        self.threshold_layout.addWidget(self.analyze_button)
        self.state_group_layout.addLayout(self.threshold_layout)
        
        # State result display
        self.state_result_label = QtWidgets.QLabel('State: Unknown')
        self.state_result_label.setAlignment(QtCore.Qt.AlignCenter)
        self.state_result_label.setStyleSheet('font-weight: bold; font-size: 14pt;')
        self.state_group_layout.addWidget(self.state_result_label)
        
        # State parameters display
        self.state_params_textedit = QtWidgets.QTextEdit()
        self.state_params_textedit.setReadOnly(True)
        self.state_params_textedit.setMaximumHeight(150)
        self.state_group_layout.addWidget(self.state_params_textedit)
        
        # Add spacer to push everything to the top
        self.left_panel_layout.addStretch(1)
        
        # Create plot widgets for right panel
        self.plot_tabs = QtWidgets.QTabWidget()
        self.right_panel_layout.addWidget(self.plot_tabs)
        
        # Signal plot
        self.signal_plot_widget = pg.PlotWidget(background='w')
        self.plot_tabs.addTab(self.signal_plot_widget, 'Signal')
        
        # Alternative data plot
        self.alt_plot_widget = pg.PlotWidget(background='w')
        self.plot_tabs.addTab(self.alt_plot_widget, 'Alternative Data')
        
        # Raw data plot
        self.raw_plot_widget = pg.PlotWidget(background='w')
        self.plot_tabs.addTab(self.raw_plot_widget, 'Raw Data')
        
        # Laser data plot
        self.laser_plot_widget = pg.PlotWidget(background='w')
        self.plot_tabs.addTab(self.laser_plot_widget, 'Laser Data')
        
        # Set plot styles
        for plot in [self.signal_plot_widget, self.alt_plot_widget, self.raw_plot_widget, self.laser_plot_widget]:
            plot.setLabel('bottom', 'Time')
            plot.setLabel('left', 'Intensity')
            plot.showGrid(x=True, y=True)
            plot.setMenuEnabled(False)
            plot.setMouseEnabled(x=True, y=True)
        
        # Create status bar
        self.statusbar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage('Ready')


class PulsedDataAnalyzerGui(GuiBase):
    """
    GUI for analyzing saved pulsed measurement data
    
    Example config:
    
    pulsed_data_analyzer_gui:
        module.Class: 'pulsed_data_analyzer_gui.PulsedDataAnalyzerGui'
        connect:
            analyzer_logic: 'pulsed_data_analyzer_logic'
    """
    
    # Declare connectors
    analyzer_logic = Connector(interface='PulsedDataAnalyzerLogic')
    
    # Status variables
    _window_geometry = StatusVar('window_geometry', None)
    _window_state = StatusVar('window_state', None)
    _show_errors = StatusVar('show_errors', True)
    _current_fit_method = StatusVar('current_fit_method', 'No Fit')
    _fit_alt_data = StatusVar('fit_alt_data', False)
    _alt_data_type = StatusVar('alt_data_type', 'None')
    _threshold = StatusVar('threshold', 0.5)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mw = None  # Will hold the main window
        self._fcd = None  # Will hold the fit configuration dialog
        self._plot_items = {}  # Will hold plot items
        
    def on_activate(self):
        """
        Initialize, connect and configure the pulsed data analyzer GUI.
        """
        # Create main window
        self._mw = PulsedDataAnalyzerMainWindow()
        
        # Create fit configuration dialog
        self._fcd = FitConfigurationDialog(
            parent=self._mw,
            fit_config_model=self.analyzer_logic().fit_config_model
        )
        
        # Connect signals
        self._connect_signals()
        
        # Initialize values
        self._initialize_gui()
        
        # Restore window geometry and state
        if self._window_geometry:
            self._mw.restoreGeometry(self._window_geometry)
        if self._window_state:
            self._mw.restoreState(self._window_state)
        
        # Show window
        self.show()
        
    def on_deactivate(self):
        """
        Deactivate the module
        """
        # Save window geometry and state
        self._window_geometry = self._mw.saveGeometry()
        self._window_state = self._mw.saveState()
        
        # Disconnect signals
        self._disconnect_signals()
        
        # Close window
        self._mw.close()
        
    def show(self):
        """
        Makes the main window visible
        """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()
        
    def _connect_signals(self):
        """
        Connect GUI signals to methods
        """
        # Connect file menu actions
        self._mw.action_load_raw_data.triggered.connect(self.load_raw_data)
        self._mw.action_load_laser_data.triggered.connect(self.load_laser_data)
        self._mw.action_load_signal_data.triggered.connect(self.load_signal_data)
        self._mw.action_save_figure.triggered.connect(self.save_figure)
        self._mw.action_export_state.triggered.connect(self.export_state)
        self._mw.action_exit.triggered.connect(self._mw.close)
        
        # Connect edit menu actions
        self._mw.action_fit_settings.triggered.connect(self._fcd.show)
        
        # Connect analysis controls
        self._mw.alt_data_combobox.currentTextChanged.connect(self.change_alt_data_type)
        self._mw.fit_combobox.currentTextChanged.connect(self.change_fit_method)
        self._mw.fit_alt_checkbox.stateChanged.connect(self.change_fit_alt_data)
        self._mw.fit_button.clicked.connect(self.do_fit)
        self._mw.show_error_checkbox.stateChanged.connect(self.update_show_errors)
        
        # Connect state analysis controls
        self._mw.threshold_spinbox.valueChanged.connect(self.update_threshold)
        self._mw.analyze_button.clicked.connect(self.analyze_state)
        
        # Connect logic signals
        self.analyzer_logic().sigDataUpdated.connect(self.update_plots)
        self.analyzer_logic().sigStateUpdated.connect(self.update_state_display)
        self.analyzer_logic().sigFitUpdated.connect(self.update_fit_display)
        
    def _disconnect_signals(self):
        """
        Disconnect GUI signals
        """
        # Disconnect file menu actions
        self._mw.action_load_raw_data.triggered.disconnect()
        self._mw.action_load_laser_data.triggered.disconnect()
        self._mw.action_load_signal_data.triggered.disconnect()
        self._mw.action_save_figure.triggered.disconnect()
        self._mw.action_export_state.triggered.disconnect()
        self._mw.action_exit.triggered.disconnect()
        
        # Disconnect edit menu actions
        self._mw.action_fit_settings.triggered.disconnect()
        
        # Disconnect analysis controls
        self._mw.alt_data_combobox.currentTextChanged.disconnect()
        self._mw.fit_combobox.currentTextChanged.disconnect()
        self._mw.fit_alt_checkbox.stateChanged.disconnect()
        self._mw.fit_button.clicked.disconnect()
        self._mw.show_error_checkbox.stateChanged.disconnect()
        
        # Disconnect state analysis controls
        self._mw.threshold_spinbox.valueChanged.disconnect()
        self._mw.analyze_button.clicked.disconnect()
        
        # Disconnect logic signals
        self.analyzer_logic().sigDataUpdated.disconnect()
        self.analyzer_logic().sigStateUpdated.disconnect()
        self.analyzer_logic().sigFitUpdated.disconnect()
        
    def _initialize_gui(self):
        """
        Initialize GUI with saved values
        """
        # Set comboboxes to saved values
        self._mw.alt_data_combobox.setCurrentText(self._alt_data_type)
        self._mw.fit_alt_checkbox.setChecked(self._fit_alt_data)
        self._mw.show_error_checkbox.setChecked(self._show_errors)
        self._mw.threshold_spinbox.setValue(self._threshold)
        
        # Update fit methods combobox
        self.update_fit_methods()
        index = self._mw.fit_combobox.findText(self._current_fit_method)
        if index >= 0:
            self._mw.fit_combobox.setCurrentIndex(index)
            
    def update_fit_methods(self):
        """
        Update the fit methods combobox with available methods
        """
        # Block signals to prevent excessive updates
        self._mw.fit_combobox.blockSignals(True)
        
        # Store current selection
        current_selection = self._mw.fit_combobox.currentText()
        
        # Clear and add "No Fit" option
        self._mw.fit_combobox.clear()
        self._mw.fit_combobox.addItem('No Fit')
        
        # Add methods from the logic
        if hasattr(self.analyzer_logic(), 'fit_config_model'):
            all_fits = self.analyzer_logic().fit_config_model.get_all_configs()
            for fit_name in all_fits:
                self._mw.fit_combobox.addItem(fit_name)
            
        # Restore selection if possible
        index = self._mw.fit_combobox.findText(current_selection)
        if index >= 0:
            self._mw.fit_combobox.setCurrentIndex(index)
        
        # Unblock signals
        self._mw.fit_combobox.blockSignals(False)
        
    def load_raw_data(self):
        """
        Load raw time trace data from file
        """
        file_filter = "Raw Data (*.dat *.csv *.npy);;Text Files (*.dat);;CSV Files (*.csv);;Numpy Files (*.npy);;All Files (*)"
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._mw, 
            'Open Raw Time Trace Data', 
            '', 
            file_filter
        )
        
        if file_path:
            if self.analyzer_logic().load_raw_data(file_path):
                self._mw.raw_data_label.setText(f'Raw Data: {os.path.basename(file_path)}')
                self._mw.statusbar.showMessage(f'Loaded raw data: {file_path}')
            else:
                self._mw.statusbar.showMessage('Failed to load raw data')
                
    def load_laser_data(self):
        """
        Load laser pulse data from file
        """
        file_filter = "Laser Data (*.dat *.csv *.npy);;Text Files (*.dat);;CSV Files (*.csv);;Numpy Files (*.npy);;All Files (*)"
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._mw, 
            'Open Laser Pulse Data', 
            '', 
            file_filter
        )
        
        if file_path:
            if self.analyzer_logic().load_laser_data(file_path):
                self._mw.laser_data_label.setText(f'Laser Data: {os.path.basename(file_path)}')
                self._mw.statusbar.showMessage(f'Loaded laser data: {file_path}')
            else:
                self._mw.statusbar.showMessage('Failed to load laser data')
                
    def load_signal_data(self):
        """
        Load signal data from file
        """
        file_filter = "Signal Data (*.dat *.csv *.npy);;Text Files (*.dat);;CSV Files (*.csv);;Numpy Files (*.npy);;All Files (*)"
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._mw, 
            'Open Signal Data', 
            '', 
            file_filter
        )
        
        if file_path:
            if self.analyzer_logic().load_signal_data(file_path):
                self._mw.signal_data_label.setText(f'Signal Data: {os.path.basename(file_path)}')
                self._mw.statusbar.showMessage(f'Loaded signal data: {file_path}')
            else:
                self._mw.statusbar.showMessage('Failed to load signal data')
    
    def save_figure(self):
        """
        Save plot as a figure
        """
        file_filter = "PNG Files (*.png);;All Files (*)"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._mw, 
            'Save Figure', 
            '', 
            file_filter
        )
        
        if file_path:
            with_error = self._mw.show_error_checkbox.isChecked()
            saved_path = self.analyzer_logic().save_thumbnail_figure(file_path, with_error=with_error)
            if saved_path:
                self._mw.statusbar.showMessage(f'Saved figure to: {saved_path}')
            else:
                self._mw.statusbar.showMessage('Failed to save figure')
                
    def export_state(self):
        """
        Export state analysis to file
        """
        file_filter = "Text Files (*.txt);;All Files (*)"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._mw, 
            'Export State Information', 
            '', 
            file_filter
        )
        
        if file_path:
            saved_path = self.analyzer_logic().export_state_to_file(file_path)
            if saved_path:
                self._mw.statusbar.showMessage(f'Exported state information to: {saved_path}')
            else:
                self._mw.statusbar.showMessage('Failed to export state information')
    
    def change_alt_data_type(self, alt_type):
        """
        Change the alternative data type
        
        @param str alt_type: Alternative data type
        """
        self._alt_data_type = alt_type
        self.analyzer_logic().set_alternative_data_type(alt_type)
        
    def change_fit_method(self, method):
        """
        Change the current fit method
        
        @param str method: Fit method name
        """
        self._current_fit_method = method
        
    def change_fit_alt_data(self, state):
        """
        Toggle whether to fit alternative data
        
        @param int state: Qt checkbox state
        """
        self._fit_alt_data = bool(state)
        
    def do_fit(self):
        """
        Perform fitting on the data
        """
        self.analyzer_logic().do_fit(self._current_fit_method, self._fit_alt_data)
        
    def update_show_errors(self, state):
        """
        Update whether to show error bars in plots
        
        @param int state: Qt checkbox state
        """
        self._show_errors = bool(state)
        self.update_plots()
        
    def update_threshold(self, value):
        """
        Update the threshold for state discrimination
        
        @param float value: Threshold value
        """
        self._threshold = value
        
    def analyze_state(self):
        """
        Analyze quantum state based on the loaded data
        """
        self.analyzer_logic().analyze_quantum_state(self._threshold)
        
    def update_plots(self):
        """
        Update all plot displays
        """
        # Clear plots
        for plot in [self._mw.signal_plot_widget, self._mw.alt_plot_widget, 
                     self._mw.raw_plot_widget, self._mw.laser_plot_widget]:
            plot.clear()
            
        self._plot_items = {}
        
        # Get data from logic
        signal_data = self.analyzer_logic().signal_data
        alt_data = self.analyzer_logic().signal_alt_data
        raw_data = self.analyzer_logic().raw_data
        laser_data = self.analyzer_logic().laser_data
        error_data = self.analyzer_logic().measurement_error
        
        # Update signal plot
        if signal_data.shape[1] > 0:
            # Plot first trace
            self._plot_items['signal1'] = self._mw.signal_plot_widget.plot(
                signal_data[0], signal_data[1], 
                pen=pg.mkPen(color='b', width=2),
                symbol='o', symbolSize=5, symbolBrush='b', symbolPen=None
            )
            
            # Plot error bars if enabled
            if self._show_errors and error_data.shape[1] > 0:
                error_bars = pg.ErrorBarItem(
                    x=signal_data[0], y=signal_data[1],
                    top=error_data[1], bottom=error_data[1],
                    beam=0.5, pen=pg.mkPen(color='b')
                )
                self._mw.signal_plot_widget.addItem(error_bars)
                self._plot_items['signal1_error'] = error_bars
                
            # If alternating data (shape > 2), plot second trace
            if signal_data.shape[0] > 2:
                self._plot_items['signal2'] = self._mw.signal_plot_widget.plot(
                    signal_data[0], signal_data[2],
                    pen=pg.mkPen(color='r', width=2),
                    symbol='o', symbolSize=5, symbolBrush='r', symbolPen=None
                )
                
                # Plot error bars for second trace if enabled
                if self._show_errors and error_data.shape[0] > 2:
                    error_bars2 = pg.ErrorBarItem(
                        x=signal_data[0], y=signal_data[2],
                        top=error_data[2], bottom=error_data[2],
                        beam=0.5, pen=pg.mkPen(color='r')
                    )
                    self._mw.signal_plot_widget.addItem(error_bars2)
                    self._plot_items['signal2_error'] = error_bars2
            
            # Set labels
            if hasattr(self.analyzer_logic(), '_data_labels') and hasattr(self.analyzer_logic(), '_data_units'):
                x_label = f"{self.analyzer_logic()._data_labels[0]}"
                if self.analyzer_logic()._data_units[0]:
                    x_label += f" ({self.analyzer_logic()._data_units[0]})"
                    
                y_label = f"{self.analyzer_logic()._data_labels[1]}"
                if self.analyzer_logic()._data_units[1]:
                    y_label += f" ({self.analyzer_logic()._data_units[1]})"
                    
                self._mw.signal_plot_widget.setLabel('bottom', x_label)
                self._mw.signal_plot_widget.setLabel('left', y_label)
        
        # Update alternative data plot
        if alt_data.shape[1] > 0:
            # Plot first trace
            self._plot_items['alt1'] = self._mw.alt_plot_widget.plot(
                alt_data[0], alt_data[1],
                pen=pg.mkPen(color='g', width=2),
                symbol='o', symbolSize=5, symbolBrush='g', symbolPen=None
            )
            
            # If alternating data (shape > 2), plot second trace
            if alt_data.shape[0] > 2:
                self._plot_items['alt2'] = self._mw.alt_plot_widget.plot(
                    alt_data[0], alt_data[2],
                    pen=pg.mkPen(color='m', width=2),
                    symbol='o', symbolSize=5, symbolBrush='m', symbolPen=None
                )
                
            # Set labels based on alternative data type
            alt_type = self.analyzer_logic().alternative_data_type
            if alt_type == 'FFT':
                if self.analyzer_logic()._data_units[0] == 's':
                    inverse_unit = 'Hz'
                elif self.analyzer_logic()._data_units[0] == 'Hz':
                    inverse_unit = 's'
                else:
                    inverse_unit = f"(1/{self.analyzer_logic()._data_units[0]})"
                    
                x_label = f"FT {self.analyzer_logic()._data_labels[0]} ({inverse_unit})"
                y_label = f"FT({self.analyzer_logic()._data_labels[1]}) (arb. u.)"
            elif alt_type == 'Delta':
                x_label = f"{self.analyzer_logic()._data_labels[0]} ({self.analyzer_logic()._data_units[0]})"
                y_label = f"Δ {self.analyzer_logic()._data_labels[1]} ({self.analyzer_logic()._data_units[1]})"
            else:
                x_label = f"{self.analyzer_logic()._data_labels[0]} ({self.analyzer_logic()._data_units[0]})"
                y_label = f"{self.analyzer_logic()._data_labels[1]} ({self.analyzer_logic()._data_units[1]})"
                
            self._mw.alt_plot_widget.setLabel('bottom', x_label)
            self._mw.alt_plot_widget.setLabel('left', y_label)
            
        # Update raw data plot
        if raw_data is not None:
            if isinstance(raw_data, np.ndarray):
                if raw_data.ndim == 1:
                    # 1D raw data
                    x = np.arange(len(raw_data))
                    self._plot_items['raw'] = self._mw.raw_plot_widget.plot(
                        x, raw_data,
                        pen=pg.mkPen(color='k', width=1)
                    )
                    self._mw.raw_plot_widget.setLabel('bottom', 'Time Bin')
                    self._mw.raw_plot_widget.setLabel('left', 'Counts')
                elif raw_data.ndim == 2:
                    # 2D raw data (gated)
                    # Plot only the first few gates to avoid overcrowding
                    max_gates = min(5, raw_data.shape[0])
                    for i in range(max_gates):
                        x = np.arange(raw_data.shape[1])
                        color = pg.intColor(i, hues=max_gates)
                        self._plot_items[f'raw_{i}'] = self._mw.raw_plot_widget.plot(
                            x, raw_data[i],
                            pen=pg.mkPen(color=color, width=1),
                            name=f'Gate {i+1}'
                        )
                    self._mw.raw_plot_widget.setLabel('bottom', 'Time Bin')
                    self._mw.raw_plot_widget.setLabel('left', 'Counts')
        
        # Update laser data plot
        if laser_data is not None:
            if isinstance(laser_data, np.ndarray) and laser_data.ndim == 2:
                # Plot only the first few laser pulses to avoid overcrowding
                max_lasers = min(5, laser_data.shape[0])
                for i in range(max_lasers):
                    x = np.arange(laser_data.shape[1])
                    color = pg.intColor(i, hues=max_lasers)
                    self._plot_items[f'laser_{i}'] = self._mw.laser_plot_widget.plot(
                        x, laser_data[i],
                        pen=pg.mkPen(color=color, width=1),
                        name=f'Laser {i+1}'
                    )
                self._mw.laser_plot_widget.setLabel('bottom', 'Time Bin')
                self._mw.laser_plot_widget.setLabel('left', 'Counts')
                
        # Update fit display if fits exist
        if hasattr(self.analyzer_logic(), '_fit_result') and self.analyzer_logic()._fit_result is not None:
            self.update_fit_display('', self.analyzer_logic()._fit_result, False)
            
        if hasattr(self.analyzer_logic(), '_fit_result_alt') and self.analyzer_logic()._fit_result_alt is not None:
            self.update_fit_display('', self.analyzer_logic()._fit_result_alt, True)
            
    def update_fit_display(self, fit_name, fit_result, use_alternative_data):
        """
        Update the fit display on the plot
        
        @param str fit_name: Name of the fit configuration
        @param object fit_result: Fit result object
        @param bool use_alternative_data: Whether the fit is for alternative data
        """
        if fit_result is None:
            return
            
        # Determine which plot to update
        plot_widget = self._mw.alt_plot_widget if use_alternative_data else self._mw.signal_plot_widget
        
        # Remove existing fit curve if present
        key = 'alt_fit' if use_alternative_data else 'signal_fit'
        if key in self._plot_items:
            plot_widget.removeItem(self._plot_items[key])
            
        # Add new fit curve if the fit was successful
        if fit_result.success:
            fit_x, fit_y = fit_result.high_res_best_fit
            self._plot_items[key] = plot_widget.plot(
                fit_x, fit_y,
                pen=pg.mkPen(color='k', width=2, style=QtCore.Qt.DashLine)
            )
            
    def update_state_display(self, state, parameters):
        """
        Update the state display
        
        @param str state: State name
        @param dict parameters: State parameters
        """
        # Update state label
        self._mw.state_result_label.setText(f'State: {state}')
        
        # Update style based on state
        if state == 'state_0':
            self._mw.state_result_label.setStyleSheet('font-weight: bold; font-size: 14pt; color: green;')
        elif state == 'state_1':
            self._mw.state_result_label.setStyleSheet('font-weight: bold; font-size: 14pt; color: red;')
        elif state == 'mixed':
            self._mw.state_result_label.setStyleSheet('font-weight: bold; font-size: 14pt; color: orange;')
        elif state == 'unknown':
            self._mw.state_result_label.setStyleSheet('font-weight: bold; font-size: 14pt; color: gray;')
        else:
            self._mw.state_result_label.setStyleSheet('font-weight: bold; font-size: 14pt;')
            
        # Update parameters display
        params_text = ""
        for key, value in parameters.items():
            if isinstance(value, (float, np.float64)):
                params_text += f"{key}: {value:.6f}\n"
            else:
                params_text += f"{key}: {value}\n"
                
        self._mw.state_params_textedit.setText(params_text)