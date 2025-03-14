"""
Energy measurement module for HEPscore.
This handles various energy measurement backends and provides a unified interface.
"""

import logging
from hepscore.perf_power import PerfEnergyReader
from hepscore.msr_power import MsrEnergyReader
from hepscore.pcap_power import PcapEnergyReader

logger = logging.getLogger(__name__)

class EnergyMeasurement:
    """Class to handle energy measurements from various sources."""
    
    def __init__(self, debug=0, preferred_method=None, force_enabled=None):
        """Initialize energy measurement with available backends.
        
        Args:
            debug (int): Debug level (0=none, 1=basic, higher=more)
            preferred_method (str, optional): Preferred measurement method ('perf', 'pcap', 'msr')
            force_enabled (bool, optional): Force enable/disable energy measurement
        """
        self.debug = debug
        self.reader = None
        self.supported = False
        # Handle force_enabled parameter
        if force_enabled is not None:
            self.supported = force_enabled
            if not force_enabled:
                logger.info("Energy measurement forcibly disabled")
                return
        
        self._initialize_readers(preferred_method)
    
    def _initialize_readers(self, preferred_method=None):
        """Try to initialize readers in order of preference.
        
        Args:
            preferred_method (str, optional): Preferred measurement method ('perf', 'pcap', 'msr')
        """
        methods = {"perf": PerfEnergyReader, "pcap": PcapEnergyReader, "msr": MsrEnergyReader}
        
        # Build the order to try based on preference
        if preferred_method and preferred_method in methods:
            # Put preferred method first, then others in default order
            order = [preferred_method]
            for method in ["perf", "pcap", "msr"]:
                if method != preferred_method:
                    order.append(method)
        else:
            order = ["perf", "pcap", "msr"]
        
        # Try readers in order
        for method in order:
            reader_class = methods[method]
            reader = reader_class(self.debug)
            if reader.is_supported():
                self.reader = reader
                self.supported = True
                logger.debug(f"Using {method.upper()} energy reader")
                return
            else:
                logger.debug(f"{method.upper()} reader not supported")
        
        # If we get here, no reader was supported
        if preferred_method:
            logger.warning(f"Preferred energy reader '{preferred_method}' not available")
        
        logger.warning("No available method for power capturing (try with root privileges)")
    
    def is_supported(self):
        """Check if energy measurement is supported.
        
        Returns:
            bool: True if energy measurement is available
        """
        return self.supported
    
    def start(self):
        """Start energy measurement.
        
        Returns:
            bool: True if measurement started successfully
        """
        if not self.supported:
            return False
            
        try:
            result = self.reader.start()
            logger.debug('Energy measurement start')
            # Handle readers that don't return anything from start()
            return True if result is None else result
        except Exception as e:
            logger.error(f"Failed to start energy measurement: {e}")
            self.supported = False
            return False
    
    def stop(self):
        """Stop energy measurement.
        
        Returns:
            bool: True if measurement stopped successfully
        """
        if not self.supported:
            return False
            
        try:
            self.reader.stop()
            logger.debug('Energy measurement was stopped')
            return True
        except Exception as e:
            logger.error(f"Failed to stop energy measurement: {e}")
            self.supported = False
            return False
    
    def get_energy(self):
        """Get measured energy in Joules.
        
        Returns:
            float: Energy consumption in Joules or None if not available
        """
        if not self.supported:
            return None
            
        try:
            energy = self.reader.get_energy()
            logger.debug(f'Read energy {energy} Joules')
            return energy 
        except Exception as e:
            logger.error(f"Failed to read energy measurement: {e}")
            self.supported = False
            return None