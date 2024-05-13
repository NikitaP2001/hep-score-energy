import os
import time, threading
import subprocess

class PcapEnergyReader:
    MAX_EN_NAME = 'max_energy_range_uj'
    ENERGY_NAME = 'energy_uj'
    PKG_NAME = 'name'
    PCAP_SFS_DIR = "/sys/class/powercap/intel-rapl/intel-rapl:"
    UJ_SCALE = 1000000
    MEASURE_TMOUT = 30

    def __init__(self, debug = 0):
        self.debug = debug
        self.last_result = None
        self.lock = threading.Lock()
        self.pkg_domain_dict = {}

        self.supported = self.__init_pkg_config()

        if len(self.pkg_domain_dict) == 0:
            if self.debug:
                print('No packages found')
            self.supported = False
        elif 'psys' in self.pkg_domain_dict:
            if self.debug:
                print('Using per system domain')
            self.pkg_domain_dict = { 'psys': self.pkg_domain_dict['psys'] }
        else:
            if self.debug:
                print('Using dram+core+uncore domains')
    
    def __init_pkg_config(self) -> bool:
        try:
            pkg = 0
            while os.path.isdir(self.PCAP_SFS_DIR + str(pkg)):
                dir_path = self.PCAP_SFS_DIR + str(pkg)
                name_path = os.path.join(dir_path, self.PKG_NAME)
                with open(name_path) as name_f:
                    pkg_name = name_f.read().split()[0]
                if self.debug:                    
                    print(f'Found pkg {pkg_name} by {dir_path}')

                en_path = os.path.join(dir_path, self.ENERGY_NAME)
                if not os.path.isfile(en_path):
                    if self.debug:
                        print(f' Energy counter not found for {pkg_name}')
                    return False
                # Try single reading, to recognise we failed in non-root case
                with open(en_path) as en_file:
                    en_str_uj = en_file.read()
                    if self.debug:
                        print(f'test energy read OK: {en_str_uj}')
                lim_path = os.path.join(dir_path, self.MAX_EN_NAME)
                if not os.path.isfile(lim_path):
                    if self.debug:
                        print(f'Energy conter limit not found for {pkg_name}')
                    return False
                self.pkg_domain_dict[pkg_name] = dir_path
                pkg += 1
        except IOError as e:
            if self.debug:
                print(f'pkg init fail: {e}')
            return False

        return True


    def is_supported(self):
        return self.supported

    def __read_energy(self, en_path) -> int:
        try:
                with open(en_path) as en_file:
                    energy = int(en_file.read())
                energy /= self.UJ_SCALE
        except IOError as e:
            if self.debug:
                print(f'Energy read fail: {e}')
            return None
        return energy

    def __read(self):
        result = {}
        for pkg in self.pkg_domain_dict: 
            dir_path = self.pkg_domain_dict[pkg]
            en_path = os.path.join(dir_path, self.ENERGY_NAME) 
            d_e = self.__read_energy(en_path)
            if d_e == None:
                return None
            result[pkg] = d_e
        return result

    def __read_limit(self, pkg) -> int:
        
        try:
            dir_path = self.pkg_domain_dict[pkg]
            lim_path = os.path.join(dir_path, self.MAX_EN_NAME)
            with open(lim_path) as lim_file:
                return int(lim_file.read()) / self.UJ_SCALE
        except IOError as e:
            if self.debug:
                print(f'Limit read fail: {e}')
        return None
    
    def __measure_pkg(self, curr) -> int:
        for pkg in self.pkg_domain_dict:
            pkg_last = self.last_result[pkg]
            pkg_curr = curr[pkg]
            if self.debug:
                print(f'pkg {pkg}: curr energy {pkg_curr}')
            if pkg_curr < pkg_last:
                limit = self.__read_limit(pkg)
                if limit == None:
                    return None
                if self.debug:
                    print(f'pkg {pkg}: reach limit {limit}')
                delta = limit - psys_last
                energy = pkg_curr + delta
            else:
                energy = pkg_curr - pkg_last
        return energy

    def __measure(self):
        curr = self.__read()
        if curr == None:
            return None

        since_last_e = self.__measure_pkg(curr)
        if since_last_e == None:
            return None

        if self.debug:
            print(f'Measure: + {since_last_e:.2f} Joules')
        self.total_consumed += since_last_e
        self.last_result = curr

    def __create_timer(self):
        tmout = self.MEASURE_TMOUT
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
    
    def start(self) -> bool:
        self.last_result = self.__read()
        if self.last_result == None:
            return False
        self.total_consumed = 0
        self.timer = self.__create_timer()
        self.timer.start()
        return True 

    def stop(self):
        self.lock.acquire()
        self.timer.cancel()
        self.__measure()
        self.last_result = None
        self.lock.release()
        self.timer.join()  
        return

    def get_energy(self):
        self.lock.acquire()
        if self.total_consumed == None: 
            raise Exception('Run at leat one measurement')
        if self.last_result != None:
            raise Exception('Stop measurement before')
        result = self.total_consumed
        self.lock.release()
        return result
    

def main():
    '''
    Example of usage
    '''
    try:
        command = "sleep 5" 
        command = command.split(' ')
        reader = PcapEnergyReader(1)

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