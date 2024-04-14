import re
import os
regex_perf_joules = r'(\d[\d\s,\.]*)\s*Joules'

def read_energy_result(result: str):
    with open(result) as res_file:
        for line in res_file:
            if "Joules" in line:
                parts = line.split("Joules")
                str_joules = re.sub(r'\s+', '', parts[0])
                str_joules = str_joules.replace(",", ".").replace(" ", "")
                return float(str_joules)
    return None

fpath = '/home/nikita_piatyhorskyi/src/hep/hep-score/testdir/HEPscore_18Feb2024_173048/atlas-kv-bmk/run0/perf_result'
res = read_energy_result(fpath)
print(res)
