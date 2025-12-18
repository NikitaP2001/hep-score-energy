import os, ctypes
import subprocess

class c_perf_event_attr(ctypes.Structure):

    _fields_ = [
        ('type', ctypes.c_uint),
        ('size', ctypes.c_uint),
        ('config', ctypes.c_ulong),
        ('sample_period_union', ctypes.c_ulong),
        ('sample_type', ctypes.c_ulong),
        ('read_format', ctypes.c_ulong),
        ('bitfields', ctypes.c_ulong),
        ('wakeup_events_union', ctypes.c_uint),
        ('bp_type', ctypes.c_uint),
        ('bp_addr_union', ctypes.c_ulong),
        ('bp_len_union', ctypes.c_ulong),
        ('branch_sample_type', ctypes.c_ulong),
        ('sample_regs_user', ctypes.c_ulong),
        ('sample_stack_user', ctypes.c_uint),
        ('clockid', ctypes.c_int),
        ('sample_regs_intr', ctypes.c_ulong),
        ('aux_watermark', ctypes.c_uint),
        ('sample_max_stack', ctypes.c_uint16),
        ('__reserved_2', ctypes.c_uint16),
        ('aux_sample_size', ctypes.c_uint),
        ('__reserved_3', ctypes.c_uint),
    ]

    def __init__(self):
        self.size = 120

class PerfDomainConfig:

    supported_units = { 'Joules' }

    def __init__(self, dname: str):
        try:
            f_eid = open(f"/sys/bus/event_source/devices/power/events/{dname}", "r")
            cfg_str = self.__read_cfg(f_eid)
            if cfg_str == None:
                return
            self._event_id = int(cfg_str, 16)

            f_scale = open(f"/sys/bus/event_source/devices/power/events/{dname}.scale", "r")
            cfg_str = self.__read_cfg(f_scale)
            if cfg_str == None:
                return
            self._scale = float(cfg_str)

            f_unit = open(f"/sys/bus/event_source/devices/power/events/{dname}.unit", "r")
            cfg_str = self.__read_cfg(f_unit)
            if cfg_str == None:
                return

            if cfg_str in self.supported_units:
                self._unit = cfg_str

        except (IOError, IndexError, ValueError) as e:
            pass

    def event_id(self):
        return self._event_id

    def scale(self):
        return self._scale

    def unit(self):
        return self._unit

    def __str__(self):
        result = ''
        if hasattr(self, '_event_id'):
            result = result + f'event_id: {self._event_id} '
        if hasattr(self, '_scale'):
            result = result + f'scale: {self._scale} '
        if hasattr(self, '_unit'):
            result = result + f'unit: {self._unit} '
        return result

    @staticmethod
    def __read_cfg(cfg_file):
        '''
        @throw IOError
        '''
        result = None
        try:
            cfg_str = cfg_file.read()
            if len(cfg_str) != 0:
                cfg_str = cfg_str.split()[0]
                if "=" in cfg_str:
                    cfg_str = cfg_str.split("=")[1]
                result = cfg_str
        except (IndexError, ValueError) as e:
            pass
        return result

    def is_valid(self):
        return hasattr(self, '_event_id') and hasattr(self, '_scale') and hasattr(self, '_unit')  


def pkg_id_path(cpu_num: int):
        return f'/sys/devices/system/cpu/cpu{cpu_num}/topology/physical_package_id'

class PerfEnergyReader:

    __NR_perf_event_open = 298

    domain_names = [
        "energy-cores",
        "energy-gpu",
        "energy-pkg",
        "energy-ram",
        "energy-psys",
    ]

    def __init__(self, debug = 0):
        self.debug = debug
        self.supported = False
        self.__svc_init() 
        self.pkg_dict = self.__init_pkg_dict()
        self.total_consumed = None
        if self.pkg_dict == None:
            if debug:
                print("perf: failed to access cpu topology")
            self.supported = False
            return
        
        self._event_type = self.__read_perf_type()
        if self._event_type == None:
            if self.debug:
                print("perf event rapl is not supported")
            return

        self.__init_perf_config()
        self._use_pkg = False
        self._use_ram = False
        self._use_sys = False
        if not self.__process_config():
            if self.debug:
                print("System perf config is not supporteed by us")
            return
        
        self.supported = self.__check_perf_open()

    def is_supported(self):
        return self.supported
    
    def __check_perf_open(self) -> bool:
        if self.start():
            self.stop()
            return True
        return False

    
    @staticmethod
    def __read_perf_type():
        type = None
        try:
            f_pwt = open("/sys/bus/event_source/devices/power/type", "r")
            type = int(f_pwt.read())
        except (IOError, ValueError) as e:
            pass
        return type

    def __process_config(self) -> bool:
        cfg_psys_valid = self.config_map["energy-psys"].is_valid()
        cfg_pkg_valid = self.config_map["energy-pkg"].is_valid()
        cfg_ram_valid = self.config_map["energy-ram"].is_valid()
        self.config_set = set()
        if cfg_psys_valid:
            self.config_set.add("energy-psys")
        elif cfg_pkg_valid:
            self.config_set.add("energy-pkg")
            if cfg_ram_valid:
                self.config_set.add("energy-ram")
            
        return cfg_psys_valid or cfg_pkg_valid

    def __init_perf_config(self):
        self.config_map = {}
        for dname in self.domain_names:
            perf_cfg = PerfDomainConfig(dname)
            self.config_map[dname] = perf_cfg 
            if self.debug:
                if self.config_map[dname].is_valid():
                    print(f'{dname} config init OK: {perf_cfg}')
                else:
                    print(f'{dname} config init FAIL')

    def __svc_init(self):
        perf_open = ctypes.CDLL(None).syscall
        perf_open.restype = ctypes.c_int
        perf_open.argtypes = ctypes.c_long, ctypes.POINTER(c_perf_event_attr), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
        self.perf_open = perf_open

    @staticmethod
    def __init_pkg_dict():
        '''`
        Maps pkg number to one first cpu which belongs to this pkg
        Return: mentioned map(dict) or None
        '''
        cpu_number = 0
        pkg_dict = {}

        try:
            while os.path.isfile(pkg_id_path(cpu_number)):

                pkg_id = pkg_id_path(cpu_number)
                file = open(pkg_id, "r")
                pkg_num = int(file.read())
                if pkg_num not in pkg_dict:
                    pkg_dict[pkg_num] = cpu_number
                cpu_number += 1

        except IOError as e:
            return None
        return pkg_dict
    
    def start(self) -> bool:
        self.event_fd_map = {}
        for pkg in self.pkg_dict:
            for cfg in self.config_set:
                if self.debug:
                    print(f"opening perf event for {cfg}")
                event_id = self.config_map[cfg].event_id()
                cpu_id = self.pkg_dict[pkg]
                event_fd = self.__perf_event_open(cpu_id, event_id)
                if event_fd < 0:
                    return False
                self.event_fd_map[cfg] = event_fd
        return True


    def stop(self):
        self.total_consumed = 0
        for pkg in self.pkg_dict:
            for cfg in self.config_set:
                if self.debug:
                    print(f"closing perf event for {cfg}")

                fd = self.event_fd_map[cfg]
                energy = self.__read_energy(fd)
                if energy == None:
                    if self.debug:
                        print(f"failed to read energy for event {cfg}")
                    self.total_consumed = None
                    return
                elif self.debug:
                    print(f'energy event {cfg}, pkg {pkg} is {energy}')
                self.total_consumed += energy * self.config_map[cfg].scale()

                self.__perf_event_close(fd)

    def get_energy(self):
        return self.total_consumed
    
    def __read_energy(self, fd: int):
        try:
            return int.from_bytes(os.read(fd, 8), 'little')
        except IOError:
            return None

    def __perf_event_open(self, cpu_id: int, event_id: int):
        svc_num = PerfEnergyReader.__NR_perf_event_open
        attr = c_perf_event_attr()
        attr.type = self._event_type
        attr.config = event_id
        return self.perf_open(svc_num, attr, -1, cpu_id, -1, 0)

    @staticmethod
    def __perf_event_close(fd: int):
        os.close(fd)

    

def main():
    '''
    Example of usage
    '''
    try:
        command = "sleep 1" 
        command = command.split(' ')
        reader = PerfEnergyReader(1)

        if reader.is_supported():
            reader.start()
            ret = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            ret.wait()
            reader.stop()
            print(f'{reader.get_energy():.2f}')

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()