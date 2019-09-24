#!/usr/bin/python
# mock_hepscore.py CONFIGFILE RESULTDIR

from hepscore import hepscore
import sys

hepscore.read_conf(sys.argv[1])
conf = hepscore.parse_conf()

results = []
for benchmark in conf['benchmarks'].keys():
    result = hepscore.proc_results(benchmark, sys.argv[2], True, conf)
    if result<0:
       print "proc_results error"
       sys.exit(1)
    results.append(result)

if 'scaling' in conf.keys():
    scale = float(conf['scaling'])
else:
    scale = 1.0

print "Geometric mean: " + str(hepscore.geometric_mean(results) * scale)

