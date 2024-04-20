import struct
import os
import time, threading
from cpu_model import CpuModel
# temp import, this should not be done there
import subprocess

class RaplProps:

    __cfg_1 = {
        "pp0_avail": 1,
        "pp1_avail": 0,
        "dram_avail": 1,
        "different_units": 0,
        "psys_avail": 0,
    }
    __cfg_2 = {
        "pp0_avail": 1,
        "pp1_avail": 0,
        "dram_avail": 1,
        "different_units": 1,
        "psys_avail": 0,
    }
    __cfg_3 = {
        "pp0_avail": 0,
        "pp1_avail": 0,
        "dram_avail": 1,
        "different_units": 1,
        "psys_avail": 0,
    }
    __cfg_4 = {
        "pp0_avail": 1,
        "pp1_avail": 1,
        "dram_avail": 0,
        "different_units": 0,
        "psys_avail": 0,
    }
    __cfg_5 = {
        "pp0_avail": 1,
        "pp1_avail": 1,
        "dram_avail": 1,
        "different_units": 0,
        "psys_avail": 0,
    }
    __cfg_6 = {
        "pp0_avail": 1,
        "pp1_avail": 1,
        "dram_avail": 1,
        "different_units": 0,
        "psys_avail": 1,
    }

    cpu_model_settings = {
        CpuModel.CPU_SANDYBRIDGE_EP: __cfg_1,
        CpuModel.CPU_IVYBRIDGE_EP: __cfg_1,

        CpuModel.CPU_HASWELL_EP: __cfg_2,
        CpuModel.CPU_BROADWELL_EP: __cfg_2,
        CpuModel.CPU_SKYLAKE_X: __cfg_2,

        CpuModel.CPU_KNIGHTS_LANDING: __cfg_3,
        CpuModel.CPU_KNIGHTS_MILL: __cfg_3,

        CpuModel.CPU_SANDYBRIDGE: __cfg_4,
        CpuModel.CPU_IVYBRIDGE: __cfg_4,

        CpuModel.CPU_HASWELL: __cfg_5,
        CpuModel.CPU_HASWELL_ULT: __cfg_5,
        CpuModel.CPU_HASWELL_GT3E: __cfg_5, 
        CpuModel.CPU_BROADWELL: __cfg_5, 
        CpuModel.CPU_BROADWELL_GT3E: __cfg_5, 
        CpuModel.CPU_ATOM_GOLDMONT: __cfg_5, 
        CpuModel.CPU_ATOM_GEMINI_LAKE: __cfg_5, 
        CpuModel.CPU_ATOM_DENVERTON: __cfg_5,

        CpuModel.CPU_SKYLAKE: __cfg_6,
        CpuModel.CPU_SKYLAKE_HS: __cfg_6, 
        CpuModel.CPU_KABYLAKE: __cfg_6, 
        CpuModel.CPU_KABYLAKE_MOBILE: __cfg_6,
    }
    
    def __init__(self, model: int, debug = 0):
        try:
            self.debug = debug
            settings = self.__set_props_for_model(model)
            self.pp0_avail = settings["pp0_avail"]
            self.pp1_avail = settings["pp1_avail"]
            self.dram_avail = settings["dram_avail"]
            self.different_units = settings["different_units"]
            self.psys_avail = settings["psys_avail"]
        except KeyError as ex:
            raise KeyError(f"Unable to find config for model: {ex}")

    def is_pp0_avail(self):
        return self.pp0_avail
    
    def is_pp1_avail(self):
        return self.pp1_avail

    def is_dram_avail(self):
        return self.dram_avail

    def is_different_units(self):
        return self.different_units
    
    def is_psys_avail(self):
        return self.psys_avail
    
    def __print_settings(self, settings):
        if not self.debug:
            return
        for key, value in settings.items():
            print(f"\t{key}: {value}") 

    def __set_props_for_model(self, model: int):
        settings = self.cpu_model_settings[model]
        self.__print_settings(settings) 
        return settings
        

class MSRFile:
    """
    A class for opening and working with an MSR file for a specific core(0).
    """
    MSR_RAPL_POWER_UNIT = 0x606

    MSR_PKG_RAPL_POWER_LIMIT = 0x610
    MSR_PKG_ENERGY_STATUS = 0x611
    MSR_PKG_PERF_STATUS = 0x613
    MSR_PKG_POWER_INFO = 0x614

    MSR_PP0_POWER_LIMIT = 0x638
    MSR_PP0_ENERGY_STATUS = 0x639
    MSR_PP0_POLICY = 0x63A
    MSR_PP0_PERF_STATUS = 0x63B

    MSR_PP1_POWER_LIMIT = 0x640
    MSR_PP1_ENERGY_STATUS = 0x641
    MSR_PP1_POLICY = 0x642

    MSR_DRAM_POWER_LIMIT = 0x618
    MSR_DRAM_ENERGY_STATUS = 0x619
    MSR_DRAM_PERF_STATUS = 0x61B
    MSR_DRAM_POWER_INFO = 0x61C

    MSR_PLATFORM_ENERGY_STATUS = 0x64d

    MSR_FIELD_SIZE = 8

    def __init__(self, debug = 0, core_num = 0):
        """
        Opens the MSR file for the specified core 
        """
        self.file_path = f"/dev/cpu/{core_num}/msr"
        self.file = None
        try:
            self.file = open(self.file_path, "rb")
        except (IOError, OSError) as e:
            if debug:
                print(f'msr file: {e}')

    def init_status(self):
        return self.file != None

    def read_msr(self, offset: int):
        """
        Reads a 64-bit msr integer value from at a specified offset.
        Args:
            offset: byte offset of the msr
        Returns:
            A 64-bit unsigned integer msr value
        Raises:
            IOError: If there's an error reading the file.
        """
        try:
            self.file.seek(offset, 0)
            data = os.pread(self.file.fileno(), self.MSR_FIELD_SIZE, offset)
            return struct.unpack('Q', data)[0]
        except IOError as e:
            raise IOError(f"Error reading msr file {e}")

    def __del__(self):
        """
        Closes the MSR file upon object deletion.
        """
        if self.file != None:
            self.file.close()
    
class EnergyReader:

    CPUINFO_PATH = "/proc/cpuinfo"
    VENDOR_ID = "GenuineIntel"
    CPU_FAMILY = 6
    # Energy msr wrap around is around 60 seconds under
    # high cpu consumption, and may be longer (see intel sdm 14.10.3)
    # It is a big question, what minimal timeout will be enough 
    # to guarantee we will have at least one read per wraparound.
    MEASURE_TMOUT = 10
    ENERGY_STATUS_MAX = 0xffffffff

    def __init__(self, debug = 1):
        '''
        Raises:
            ValueError
        '''
        self.supported = False
        self.last_result = None
        self.debug = debug
        self.file = MSRFile(debug = True)
        if not self.file.init_status():
            if self.debug:
                print('Failed to access msr file')
            return
        
        self.cpu_info = self.__detect_cpu()
        if (self.cpu_info == None):
            if self.debug:
                print("Unexpected data met in cpu info")
            return

        if not self.__is_supported():
            if self.debug:
                print("CPU is not supported")
            return

        self.rapl_props = RaplProps(self.cpu_info["model"])
        self.__read_units()
        self.__init_max_energy()
        self.__print_energy_units()
        self.lock = threading.Lock()
        self.supported = True
    
    def __init_max_energy(self):
        self.max_energy_cpu = self.cpu_energy_units * self.ENERGY_STATUS_MAX 
        self.max_energy_dram = self.dram_energy_units * self.ENERGY_STATUS_MAX 
        if self.debug:
            print(f'max E cpu {self.max_energy_cpu}')
            print(f'max E dram {self.max_energy_dram}')

    def is_supported(self):
        return self.supported

    def get_energy(self):
        '''
            Get energy consumed between star and setop, Joules
        '''
        self.lock.acquire()
        if self.total_consumed == None: 
            raise Exception('Run at leat one measurement')
        if self.last_result != None:
            raise Exception('Stop measurement before')
        result = self.total_consumed
        self.lock.release()
        return result
    
    
    def __read_units(self):
        pwr_unit = self.file.read_msr(MSRFile.MSR_RAPL_POWER_UNIT)

        self.power_units = pow(0.5, pwr_unit & 0xf)
        esu_units = (pwr_unit >> 8) & 0x1f
        self.cpu_energy_units = pow(0.5, esu_units)
        tu_units = (pwr_unit >> 16) & 0xf
        self.time_units = pow(0.5, tu_units)
        if self.rapl_props.is_different_units():
            self.dram_energy_units = pow(0.5, 16)
        else:
            self.dram_energy_units = self.cpu_energy_units

    def __print_energy_units(self):
        if not self.debug:
            return
        print(f'DRAM: Using {self.dram_energy_units} {self.cpu_energy_units}')
        print(f'power_units {self.power_units}W')
        print(f'cpu_energy_units {self.cpu_energy_units}J')
        print(f'dram_energy_units {self.dram_energy_units}J')
        print(f'time_units {self.time_units}s')
    
    def __print_energy_result(self, res):
        if not self.debug:
            return
        print('RAPL readings result:')
        for key in res:
            print(key, res[key])

    
    def __read(self):
        pwr_res = {}
        pkg_e = self.file.read_msr(MSRFile.MSR_PKG_ENERGY_STATUS)
        pwr_res['energy-package'] = pkg_e * self.cpu_energy_units

        if self.rapl_props.is_pp0_avail():
            pp0_e = self.file.read_msr(MSRFile.MSR_PP0_ENERGY_STATUS)
            pwr_res['energy-cores'] = pp0_e * self.cpu_energy_units

        if self.rapl_props.is_pp1_avail():
            pp1_e = self.file.read_msr(MSRFile.MSR_PP1_ENERGY_STATUS)
            pwr_res['energy-gpu'] = pp1_e * self.cpu_energy_units

        if self.rapl_props.is_dram_avail():
            dram_e = self.file.read_msr(MSRFile.MSR_DRAM_ENERGY_STATUS)
            pwr_res['energy-dram'] = dram_e * self.dram_energy_units

        if self.rapl_props.is_psys_avail():
            psys_e = self.file.read_msr(MSRFile.MSR_PLATFORM_ENERGY_STATUS)
            pwr_res['energy-psys'] = psys_e * self.cpu_energy_units

        self.__print_energy_result(pwr_res)
        return pwr_res

    def __measure_psys(self, curr):
        psys_last = self.last_result['energy-psys']
        psys_curr = curr['energy-psys']
        # TODO: we must find a value we overflowed on
        if psys_curr < psys_last:
            delta = self.max_energy_cpu - psys_last
            energy = psys_curr + delta
        else:
            energy = psys_curr - psys_last
        return energy
    
    def __measure_pkg(self, curr):
        # TODO: we should sum up each package
        energy = 0
        pkg_last = self.last_result['energy-package']
        dram_last = self.last_result['energy-dram']
        pkg_curr = curr['energy-package']
        dram_curr = curr['energy-dram']

        if self.rapl_props.is_dram_avail():
            if dram_curr < dram_last:
                delta = self.max_energy_dram - dram_last
                energy = dram_last + delta
            else:
                energy = dram_curr - dram_last

        if pkg_curr < pkg_last:
            delta = self.max_energy_cpu - pkg_last
            energy += pkg_curr + delta
        else:
            energy += pkg_curr - pkg_last

        return energy
    
    def __measure(self):
        curr = self.__read()
        if self.rapl_props.is_psys_avail():
            since_last_e = self.__measure_psys(curr)
        else:
            since_last_e = self.__measure_pkg(curr)    

        if self.debug:
            print(f'Measure: + {since_last_e:.2f} Joules')
        self.total_consumed += since_last_e
        self.last_result = curr

    def __create_timer(self):
        tmout = EnergyReader.MEASURE_TMOUT
        return threading.Timer(tmout, self.__tmr_cback)
    
    def __is_run(self):
        return self.last_result != None
    
    def __tmr_cback(self):
        self.lock.acquire()
        self.__measure()
        if self.__is_run():
            self.timer = self.__create_timer()
            self.timer.start()
        self.lock.release()
    
    def start(self):
        self.last_result = self.__read()
        self.total_consumed = 0
        self.timer = self.__create_timer()
        self.timer.start()

    
    def stop(self):
        self.lock.acquire()
        self.timer.cancel()
        self.__measure()
        self.last_result = None
        self.lock.release()
        self.timer.join()  
    
    def __detect_cpu(self):
        """
        Reads CPU information and extracts vendor_id, cpu family, and model.
        Returns:
            A dictionary containing this information or None if an error occurs.
        """
        cpu_info = {}
        try:
            with open(self.CPUINFO_PATH, "r") as file:
                for line in file:
                    lsplit = line.strip().split(":", 1)
                    if len(lsplit) != 2:
                        continue
                    key, value = lsplit
                    key = key.strip()
                    if "vendor_id" == key:
                        cpu_info["vendor_id"] = value.strip()
                    elif "cpu family" == key:
                        cpu_info["cpu_family"] = int(value.strip())
                    elif "model" == key:
                        cpu_info["model"] = int(value.strip())

        except IOError as e:
            raise IOError(f"Error opening MSR file: {e}")
        except ValueError:
            return None
        return cpu_info
    
    def __is_supported(self):
        result = False
        checked = {"vendor_id", "cpu_family", "model"}
        if checked.issubset(self.cpu_info):
            result = True
            vid = self.cpu_info["vendor_id"]
            cpu_f = self.cpu_info["cpu_family"]
            model = CpuModel.get_model_name(self.cpu_info["model"])
            if vid != self.VENDOR_ID:
                result = False
            if cpu_f != self.CPU_FAMILY:
                result = False
            if model == None:
                result = False
        return result

    def __del__(self):
        if self.last_result != None and self.last_result != 0:
            self.stop()

def main():
  
    try:
        e = EnergyReader(1)
        if not e.is_supported():
            print('Method is unsupported. May run with sudo')
            return
        command = "sleep 2" 
        command = command.split(' ')

        e.start()

        ret = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ret.wait()

        e.stop()
        res = e.get_energy()
        print(f'Energy reading: {res:.2f} Joules')

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()