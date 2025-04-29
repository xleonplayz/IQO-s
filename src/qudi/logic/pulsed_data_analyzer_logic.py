# -*- coding: utf-8 -*-
"""
This file contains the Qudi logic module for analyzing saved pulsed measurement data.

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
import time
import datetime
import matplotlib.pyplot as plt

from PySide2 import QtCore

from qudi.core.configoption import ConfigOption
from qudi.core.statusvariable import StatusVar
from qudi.core.module import LogicBase
from qudi.util.mutex import Mutex
from qudi.util.datafitting import FitConfigurationsModel, FitContainer
from qudi.util.datastorage import TextDataStorage, CsvDataStorage, NpyDataStorage
from qudi.util.units import ScaledFloat
from qudi.util.colordefs import QudiMatplotlibStyle
from qudi.logic.pulsed.pulse_extractor import PulseExtractor
from qudi.logic.pulsed.pulse_analyzer import PulseAnalyzer


def _data_storage_from_cfg_option(cfg_str):
    cfg_str = cfg_str.lower()
    if cfg_str == 'text':
        return TextDataStorage
    if cfg_str == 'csv':
        return CsvDataStorage
    if cfg_str == 'npy':
        return NpyDataStorage
    raise ValueError('Invalid ConfigOption value to specify data storage type.')


class PulsedDataAnalyzerLogic(LogicBase):
    """
    This logic module is designed to load and analyze saved pulsed measurement data files.
    
    Example config:
    
    pulsed_data_analyzer_logic:
        module.Class: 'pulsed_data_analyzer_logic.PulsedDataAnalyzerLogic'
        options:
            default_data_storage_type: 'text'
            save_thumbnails: True
    """
    
    # Config options
    _default_data_storage_cls = ConfigOption(name='default_data_storage_type',
                                           default='text',
                                           constructor=_data_storage_from_cfg_option)
    _save_thumbnails = ConfigOption(name='save_thumbnails', default=True)
    
    # Status variables
    _data_units = StatusVar(default=('s', ''))
    _data_labels = StatusVar(default=('Tau', 'Signal'))
    
    # Alternative signal computation settings:
    _alternative_data_type = StatusVar(default=None)
    zeropad = StatusVar(default=0)
    psd = StatusVar(default=False)
    window = StatusVar(default='none')
    base_corr = StatusVar(default=True)
    
    # signals
    sigDataUpdated = QtCore.Signal()
    sigStateUpdated = QtCore.Signal(str, dict)
    sigFitUpdated = QtCore.Signal(str, object, bool)
    
    # Data fitting
    _fit_configs = StatusVar(name='fit_configs', default=None)
    
    __default_fit_configs = (
        {'name': 'Gaussian Dip',
         'model': 'Gaussian',
         'estimator': 'Dip',
         'custom_parameters': None},

        {'name': 'Gaussian Peak',
         'model': 'Gaussian',
         'estimator': 'Peak',
         'custom_parameters': None},

        {'name': 'Lorentzian Dip',
         'model': 'Lorentzian',
         'estimator': 'Dip',
         'custom_parameters': None},

        {'name': 'Lorentzian Peak',
         'model': 'Lorentzian',
         'estimator': 'Peak',
         'custom_parameters': None},

        {'name': 'Double Lorentzian Dips',
         'model': 'DoubleLorentzian',
         'estimator': 'Dips',
         'custom_parameters': None},

        {'name': 'Double Lorentzian Peaks',
         'model': 'DoubleLorentzian',
         'estimator': 'Peaks',
         'custom_parameters': None},

        {'name': 'Triple Lorentzian Dip',
         'model': 'TripleLorentzian',
         'estimator': 'Dips',
         'custom_parameters': None},

        {'name': 'Triple Lorentzian Peaks',
         'model': 'TripleLorentzian',
         'estimator': 'Peaks',
         'custom_parameters': None},

        {'name': 'Sine',
         'model': 'Sine',
         'estimator': 'default',
         'custom_parameters': None},

        {'name': 'Double Sine',
         'model': 'DoubleSine',
         'estimator': 'default',
         'custom_parameters': None},

        {'name': 'Exp. Decay Sine',
         'model': 'ExponentialDecaySine',
         'estimator': 'Decay',
         'custom_parameters': None},

        {'name': 'Stretched Exp. Decay Sine',
         'model': 'ExponentialDecaySine',
         'estimator': 'Stretched Decay',
         'custom_parameters': None},

        {'name': 'Stretched Exp. Decay',
         'model': 'ExponentialDecay',
         'estimator': 'Stretched Decay',
         'custom_parameters': None},
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # threading
        self._threadlock = Mutex()
        
        # measurement data
        self.signal_data = np.empty((2, 0), dtype=float)
        self.signal_alt_data = np.empty((2, 0), dtype=float)
        self.measurement_error = np.empty((2, 0), dtype=float)
        self.laser_data = None
        self.raw_data = None
        
        # for fit:
        self.fit_config_model = None
        self.fc = None  # Fit container
        self.alt_fc = None
        self._fit_result = None
        self._fit_result_alt = None
        
        # Currently loaded file info
        self.current_raw_data_path = None
        self.current_laser_data_path = None
        self.current_signal_data_path = None
        
        # Metadata from loaded files
        self.current_metadata = {
            'raw_data': {},
            'laser_data': {},
            'signal_data': {}
        }
        
        # Quantum state information
        self._current_state = None
        self._state_parameters = {}
        
    @_fit_configs.representer
    def __repr_fit_configs(self, value):
        configs = self.fit_config_model.dump_configs()
        if len(configs) < 1:
            configs = None
        return configs

    @_fit_configs.constructor
    def __constr_fit_configs(self, value):
        if not value:
            return self.__default_fit_configs
        return value
        
    def on_activate(self):
        """
        Initialization performed during activation of the module.
        """
        # Create fit model
        self.fit_config_model = FitConfigurationsModel(parent=self)
        self.fit_config_model.load_configs(self._fit_configs)
        self.fc = FitContainer(parent=self, config_model=self.fit_config_model)
        self.alt_fc = FitContainer(parent=self, config_model=self.fit_config_model)
        
        # Create PulseExtractor and PulseAnalyzer
        self._pulseextractor = PulseExtractor(pulsedmeasurementlogic=self)
        self._pulseanalyzer = PulseAnalyzer(pulsedmeasurementlogic=self)
        
    def on_deactivate(self):
        """
        Deinitialize the module
        """
        pass
    
    def load_raw_data(self, file_path):
        """
        Load the raw time trace file
        
        @param str file_path: Path to the raw timetrace data file
        @return bool: Success flag
        """
        try:
            storage_cls = self._get_storage_class_from_file_extension(file_path)
            data_storage = storage_cls(root_dir=os.path.dirname(file_path))
            
            # Load data and metadata
            data, metadata = data_storage.load_data(os.path.basename(file_path))
            
            # Data could be 1D or 2D depending on gated/non-gated counter
            if data.ndim == 2:
                self.raw_data = data
            else:
                self.raw_data = data[:, 0]
                
            # Store metadata and file path
            self.current_raw_data_path = file_path
            self.current_metadata['raw_data'] = metadata
            
            # Initialize state parameters
            self._initialize_state_parameters()
            
            self.sigDataUpdated.emit()
            return True
        except Exception as e:
            self.log.error(f"Error loading raw data: {str(e)}")
            return False
    
    def load_laser_data(self, file_path):
        """
        Load the laser pulses file
        
        @param str file_path: Path to the laser pulses data file
        @return bool: Success flag
        """
        try:
            storage_cls = self._get_storage_class_from_file_extension(file_path)
            data_storage = storage_cls(root_dir=os.path.dirname(file_path))
            
            # Load data and metadata
            data, metadata = data_storage.load_data(os.path.basename(file_path))
            
            self.laser_data = data
            
            # Store metadata and file path
            self.current_laser_data_path = file_path
            self.current_metadata['laser_data'] = metadata
            
            # Initialize state parameters
            self._initialize_state_parameters()
            
            self.sigDataUpdated.emit()
            return True
        except Exception as e:
            self.log.error(f"Error loading laser data: {str(e)}")
            return False
    
    def load_signal_data(self, file_path):
        """
        Load the pulsed measurement result file
        
        @param str file_path: Path to the pulsed measurement data file
        @return bool: Success flag
        """
        try:
            storage_cls = self._get_storage_class_from_file_extension(file_path)
            data_storage = storage_cls(root_dir=os.path.dirname(file_path))
            
            # Load data and metadata
            data, metadata = data_storage.load_data(os.path.basename(file_path))
            
            # Check if alternating
            alternating = metadata.get('alternating', False)
            
            # Process data based on shape
            if data.shape[1] >= 3 and alternating:
                self.signal_data = np.empty((3, data.shape[0]), dtype=float)
                self.signal_data[0] = data[:, 0]  # x values
                self.signal_data[1] = data[:, 1]  # y values for first trace
                self.signal_data[2] = data[:, 2]  # y values for second trace
                
                if data.shape[1] >= 5:  # If error data is included
                    self.measurement_error = np.empty((3, data.shape[0]), dtype=float)
                    self.measurement_error[0] = data[:, 0]  # x values
                    self.measurement_error[1] = data[:, 3]  # error values for first trace
                    self.measurement_error[2] = data[:, 4]  # error values for second trace
            else:
                self.signal_data = np.empty((2, data.shape[0]), dtype=float)
                self.signal_data[0] = data[:, 0]  # x values
                self.signal_data[1] = data[:, 1]  # y values
                
                if data.shape[1] >= 3:  # If error data is included
                    self.measurement_error = np.empty((2, data.shape[0]), dtype=float)
                    self.measurement_error[0] = data[:, 0]  # x values
                    self.measurement_error[1] = data[:, 2]  # error values

            # Get labels and units from metadata
            if 'labels' in metadata:
                self._data_labels = metadata.get('labels', ('Tau', 'Signal'))
            if 'units' in metadata:
                self._data_units = metadata.get('units', ('s', ''))
                
            # Store metadata and file path
            self.current_signal_data_path = file_path
            self.current_metadata['signal_data'] = metadata
            
            # Initialize state parameters
            self._initialize_state_parameters()
            
            # Compute alternative data (FFT, etc.)
            self._compute_alt_data()
            
            self.sigDataUpdated.emit()
            return True
        except Exception as e:
            self.log.error(f"Error loading signal data: {str(e)}")
            return False
    
    def _initialize_state_parameters(self):
        """
        Initialize the quantum state parameters based on loaded data
        """
        # Default state is unknown
        self._current_state = "unknown"
        self._state_parameters = {}
        
        # This will be updated when analyze_quantum_state is called
        self.sigStateUpdated.emit(self._current_state, self._state_parameters)
    
    def analyze_quantum_state(self, threshold=0.5):
        """
        Analyze the signal data to determine the quantum state based on the signal
        
        @param float threshold: Threshold for state discrimination
        @return tuple(str, dict): State name and parameters
        """
        if self.signal_data.shape[1] == 0:
            return "unknown", {}
        
        try:
            # Simple threshold-based state determination
            # For more complex analysis, this would be extended based on the specific quantum system
            
            # For alternating measurements
            if self.signal_data.shape[0] > 2:
                # Calculate difference signal (often used to determine state in NV systems)
                diff_signal = np.mean(self.signal_data[1] - self.signal_data[2])
                contrast = np.abs(np.mean(self.signal_data[1] - self.signal_data[2])) / np.mean(self.signal_data[1])
                
                # Analyze the state based on the difference
                if diff_signal > threshold:
                    state = "state_0"
                elif diff_signal < -threshold:
                    state = "state_1"
                else:
                    state = "mixed"
                    
                params = {
                    "diff_signal": diff_signal,
                    "contrast": contrast,
                    "mean_signal_0": np.mean(self.signal_data[1]),
                    "mean_signal_1": np.mean(self.signal_data[2]),
                    "std_signal_0": np.std(self.signal_data[1]),
                    "std_signal_1": np.std(self.signal_data[2])
                }
            else:
                # For non-alternating measurements
                mean_signal = np.mean(self.signal_data[1])
                
                # Basic threshold-based discrimination
                if mean_signal > threshold:
                    state = "state_0"
                else:
                    state = "state_1"
                    
                params = {
                    "mean_signal": mean_signal,
                    "std_signal": np.std(self.signal_data[1])
                }
            
            # Update the current state information
            self._current_state = state
            self._state_parameters = params
            
            # Emit the state updated signal
            self.sigStateUpdated.emit(state, params)
            
            return state, params
            
        except Exception as e:
            self.log.error(f"Error analyzing quantum state: {str(e)}")
            return "error", {"error": str(e)}
    
    def get_state(self):
        """
        Return the current state determination
        
        @return tuple(str, dict): Current state and parameters
        """
        return self._current_state, self._state_parameters
        
    def _get_storage_class_from_file_extension(self, file_path):
        """
        Determine the appropriate storage class based on file extension
        
        @param str file_path: File path
        @return class: Storage class
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.dat':
            return TextDataStorage
        elif ext == '.csv':
            return CsvDataStorage
        elif ext == '.npy':
            return NpyDataStorage
        else:
            # Default to text
            return TextDataStorage
    
    def _compute_alt_data(self):
        """
        Performing transformations on the measurement data (e.g. fourier transform).
        """
        from qudi.util.math import compute_ft
        
        if self._alternative_data_type == 'Delta' and len(self.signal_data) == 3:
            self.signal_alt_data = np.empty((2, self.signal_data.shape[1]), dtype=float)
            self.signal_alt_data[0] = self.signal_data[0]
            self.signal_alt_data[1] = self.signal_data[1] - self.signal_data[2]
        elif self._alternative_data_type == 'FFT' and self.signal_data.shape[1] >= 2:
            fft_x, fft_y = compute_ft(x_val=self.signal_data[0],
                                      y_val=self.signal_data[1],
                                      zeropad_num=self.zeropad,
                                      window=self.window,
                                      base_corr=self.base_corr,
                                      psd=self.psd)
            self.signal_alt_data = np.empty((len(self.signal_data), len(fft_x)), dtype=float)
            self.signal_alt_data[0] = fft_x
            self.signal_alt_data[1] = fft_y
            for dim in range(2, len(self.signal_data)):
                dummy, self.signal_alt_data[dim] = compute_ft(x_val=self.signal_data[0],
                                                          y_val=self.signal_data[dim],
                                                          zeropad_num=self.zeropad,
                                                          window=self.window,
                                                          base_corr=self.base_corr,
                                                          psd=self.psd)
        else:
            self.signal_alt_data = np.zeros(self.signal_data.shape, dtype=float)
            self.signal_alt_data[0] = self.signal_data[0]
        return
    
    def set_alternative_data_type(self, alt_data_type):
        """
        Set the type of alternative data calculation

        @param str alt_data_type: Alternative data type ('Delta', 'FFT', 'None')
        """
        with self._threadlock:
            if alt_data_type != self.alternative_data_type:
                self.do_fit('No Fit', True)
            if alt_data_type == 'Delta' and len(self.signal_data) != 3:
                if self._alternative_data_type == 'Delta':
                    self._alternative_data_type = None
                self.log.error('Can not set "Delta" as alternative data calculation if data is '
                               'not alternating.\n'
                               'Setting to previous type "{0}".'.format(self.alternative_data_type))
            elif alt_data_type == 'None':
                self._alternative_data_type = None
            else:
                self._alternative_data_type = alt_data_type

            self._compute_alt_data()
            self.sigDataUpdated.emit()
        return
    
    @property
    def alternative_data_type(self):
        return str(self._alternative_data_type) if self._alternative_data_type else 'None'
    
    @QtCore.Slot(str)
    @QtCore.Slot(str, bool)
    def do_fit(self, fit_config, use_alternative_data=False):
        """
        Performs the chosen fit on the loaded data.

        @param str fit_config: name of the fit configuration to use
        @param bool use_alternative_data: Flag indicating if the signal data (False) or the
                                        alternative signal data (True) should be fitted.

        @return result_object: the lmfit result object
        """
        container = self.alt_fc if use_alternative_data else self.fc
        data = self.signal_alt_data if use_alternative_data else self.signal_data
        
        # Ensure we have data to fit
        if data.shape[1] == 0:
            self.log.error('No data available for fitting.')
            self.sigFitUpdated.emit('', None, use_alternative_data)
            return None
            
        try:
            config, result = container.fit_data(fit_config, data[0], data[1])
            if result:
                result.result_str = container.formatted_result(result)
            if use_alternative_data:
                self._fit_result_alt = result
            else:
                self._fit_result = result

        except Exception as e:
            config, result = '', None
            self.log.exception(f'Something went wrong while trying to perform data fit: {str(e)}')

        self.sigFitUpdated.emit(config, result, use_alternative_data)
        return result
    
    def save_thumbnail_figure(self, file_path=None, with_error=True):
        """
        Generate and save a thumbnail figure of the current data

        @param str file_path: Optional file path to save the figure 
        @param bool with_error: Whether to include error bars
        @return str: Path where the figure was saved
        """
        if self.signal_data.shape[1] == 0:
            self.log.error('No data available to plot.')
            return None
            
        try:
            # Create the figure
            fig = self._plot_data_thumbnail(with_error=with_error)
            
            # Determine save path
            if file_path is None:
                # Generate a default path in the same directory as the current signal data
                if self.current_signal_data_path:
                    base_dir = os.path.dirname(self.current_signal_data_path)
                    base_name = os.path.splitext(os.path.basename(self.current_signal_data_path))[0]
                    file_path = os.path.join(base_dir, f"{base_name}_thumbnail.png")
                else:
                    # Create a timestamp-based filename in the default data dir
                    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    file_path = os.path.join(self.module_default_data_dir, f"pulsed_data_{timestamp}.png")
            
            # Save the figure
            fig.savefig(file_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            return file_path
            
        except Exception as e:
            self.log.error(f"Error saving thumbnail figure: {str(e)}")
            return None
    
    def _plot_data_thumbnail(self, with_error=True):
        """
        Create a plot of the current data
        
        @param bool with_error: Include error bars
        @return matplotlib.figure.Figure: Figure object
        """
        # For the implementation, I've simplified the plotting that's in 
        # the standard pulsed_measurement_logic.py to focus on the main elements
        
        plt.style.use(QudiMatplotlibStyle.style)

        # Extract colors from style
        prop_cycle = plt.rcParams['axes.prop_cycle']
        colors = {}
        for i, color_setting in enumerate(prop_cycle):
            colors[i] = color_setting['color']

        # Scale the x_axis for plotting
        max_val = np.max(self.signal_data[0])
        scaled_float = ScaledFloat(max_val)
        counts_prefix = scaled_float.scale
        x_axis_scaled = self.signal_data[0] / scaled_float.scale_val

        # Create the figure object
        if self._alternative_data_type and self._alternative_data_type != 'None':
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        else:
            fig, ax1 = plt.subplots(figsize=(10, 5))

        if with_error and self.measurement_error.shape[1] > 0:
            ax1.errorbar(x=x_axis_scaled, y=self.signal_data[1],
                         yerr=self.measurement_error[1],
                         linestyle=':', linewidth=0.5, color=colors[0],
                         ecolor=colors[1], capsize=3, capthick=0.9,
                         elinewidth=1.2, label='data trace 1')

            if len(self.signal_data) > 2:  # alternating
                ax1.errorbar(x=x_axis_scaled, y=self.signal_data[2],
                             yerr=self.measurement_error[2], fmt='-D',
                             linestyle=':', linewidth=0.5, color=colors[3],
                             ecolor=colors[4],  capsize=3, capthick=0.7,
                             elinewidth=1.2, label='data trace 2')
        else:
            ax1.plot(x_axis_scaled, self.signal_data[1], color=colors[0],
                     linestyle=':', linewidth=0.5, label='data trace 1')

            if len(self.signal_data) > 2:  # alternating
                ax1.plot(x_axis_scaled, self.signal_data[2], '-o',
                         color=colors[3], linestyle=':', linewidth=0.5,
                         label='data trace 2')

        # Add fit results if available
        if self._fit_result:
            fit_x, fit_y = self._fit_result.high_res_best_fit
            x_axis_fit_scaled = fit_x / scaled_float.scale_val
            ax1.plot(x_axis_fit_scaled, fit_y,
                     color=colors[2], marker='None', linewidth=1.5,
                     label='fit')

        # Add alternative data plot if available
        if self._alternative_data_type and self._alternative_data_type != 'None' and self.signal_alt_data.shape[1] > 0:
            alt_max_val = np.max(self.signal_alt_data[0])
            alt_scaled_float = ScaledFloat(alt_max_val)
            alt_x_axis_scaled = self.signal_alt_data[0] / alt_scaled_float.scale_val

            # Set appropriate labels for alternative data
            if self._alternative_data_type == 'FFT':
                if self._data_units[0] == 's':
                    inverse_unit = 'Hz'
                elif self._data_units[0] == 'Hz':
                    inverse_unit = 's'
                else:
                    inverse_unit = f"(1/{self._data_units[0]})"
                    
                x_label = f'FT {self._data_labels[0]} ({alt_scaled_float.scale}{inverse_unit})'
                y_label = f'FT({self._data_labels[1]}) (arb. u.)'
                alt_label = 'FT of data trace 1'
            else:
                x_label = f'{self._data_labels[0]} ({alt_scaled_float.scale}{self._data_units[0]})'
                y_label = f'{self._data_labels[1]} ({self._data_units[1]})'
                alt_label = f'{self._alternative_data_type} of data traces'

            ax2.plot(alt_x_axis_scaled, self.signal_alt_data[1],
                     linestyle=':', linewidth=0.5, color=colors[0],
                     label=alt_label)
                     
            if len(self.signal_alt_data) > 2:  # alternating
                ax2.plot(alt_x_axis_scaled, self.signal_alt_data[2],
                         linestyle=':', linewidth=0.5, color=colors[3],
                         label=alt_label.replace('1', '2'))
                         
            ax2.set_xlabel(x_label)
            ax2.set_ylabel(y_label)
            ax2.legend(loc='best')

            # Add fit to alternative data if available
            if self._fit_result_alt:
                alt_fit_x, alt_fit_y = self._fit_result_alt.high_res_best_fit
                alt_x_axis_fit_scaled = alt_fit_x / alt_scaled_float.scale_val
                ax2.plot(alt_x_axis_fit_scaled, alt_fit_y,
                         color=colors[2], marker='None', linewidth=1.5,
                         label='fit')

        # Set main axis labels
        ax1.set_xlabel(f'{self._data_labels[0]} ({counts_prefix}{self._data_units[0]})')
        ax1.set_ylabel(f'{self._data_labels[1]} ({self._data_units[1]})')
        ax1.legend(loc='best')

        # Add state information if available
        if self._current_state != "unknown":
            state_text = f"State: {self._current_state}"
            for key, value in self._state_parameters.items():
                if isinstance(value, (float, np.float64)):
                    state_text += f"\n{key}: {value:.4f}"
                else:
                    state_text += f"\n{key}: {value}"
            
            # Position the text in the upper right
            ax1.text(0.98, 0.98, state_text,
                     transform=ax1.transAxes,
                     verticalalignment='top',
                     horizontalalignment='right',
                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        fig.tight_layout()
        return fig
        
    def export_state_to_file(self, file_path=None):
        """
        Export the current state determination to a file
        
        @param str file_path: Optional file path to save to
        @return str: Path where the state was saved
        """
        try:
            # Determine file path if not provided
            if file_path is None:
                # Generate a default path in the same directory as the current signal data
                if self.current_signal_data_path:
                    base_dir = os.path.dirname(self.current_signal_data_path)
                    base_name = os.path.splitext(os.path.basename(self.current_signal_data_path))[0]
                    file_path = os.path.join(base_dir, f"{base_name}_state.txt")
                else:
                    # Create a timestamp-based filename in the default data dir
                    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    file_path = os.path.join(self.module_default_data_dir, f"quantum_state_{timestamp}.txt")
            
            # Create the state information text
            state_info = f"# Quantum State Determination\n"
            state_info += f"# Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            state_info += f"# State: {self._current_state}\n\n"
            
            # Add parameters
            state_info += "# Parameters:\n"
            for key, value in self._state_parameters.items():
                state_info += f"{key} = {value}\n"
                
            # Add file sources
            state_info += "\n# Source Files:\n"
            if self.current_raw_data_path:
                state_info += f"raw_data_file = {self.current_raw_data_path}\n"
            if self.current_laser_data_path:
                state_info += f"laser_data_file = {self.current_laser_data_path}\n"
            if self.current_signal_data_path:
                state_info += f"signal_data_file = {self.current_signal_data_path}\n"
                
            # Write to file
            with open(file_path, 'w') as f:
                f.write(state_info)
                
            return file_path
            
        except Exception as e:
            self.log.error(f"Error exporting state to file: {str(e)}")
            return None