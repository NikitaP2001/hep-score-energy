#!/usr/bin/python
###############################################################################
#
# hepscore.py - HEPscore benchmark execution
# Chris Hollowell <hollowec@bnl.gov>
#
#

import getopt
import glob
import json
import os
import string
import subprocess
import sys
import time
import yaml

NAME = "HEPscore"
VER = "0.61"

CONF = """
hepscore_benchmark:
  name: HEPscore19
  version: 0.3
  repetitions: 3  # number of repetitions of the same benchmark
  reference_machine: 'Intel Core i5-4590 @ 3.30GHz - 1 Logical Core'
  method: geometric_mean # or any other algorithm
  registry: gitlab-registry.cern.ch/hep-benchmarks/hep-workloads
  scaling: 10
  benchmarks:
    atlas-sim-bmk:
      version: v1.0
      scorekey: wl-scores
      ref_scores: { sim: 0.0052 }
    cms-reco-bmk:
      version: v1.0
      scorekey: wl-scores
      ref_scores: { reco: 0.1625 }
    lhcb-gen-sim-bmk:
      version: v0.12
      refscore: 7.1811
      scorekey: throughput_score
      subkey: 'GENSIM0 (evts per wall msec, including 1st evt)'
      debug: false
      events:
      threads:
"""


def help():

    global NAME

    namel = NAME.lower() + ".py"

    print(NAME + " Benchmark Execution - Version " + VER)
    print(namel + " {-s|-d} [-v] [-c NCOPIES] [-o OUTFILE] [-f CONFIGFILE] "
          "OUTPUTDIR")
    print(namel + " -h")
    print(namel + " -p")
    print("Option overview:")
    print("-h           Print help information and exit")
    print("-v           Display verbose output, including all component "
          "benchmark scores")
    print("-d           Run benchmark containers in Docker")
    print("-s           Run benchmark containers in Singularity")
    print("-c           Set the sub-benchmark NCOPIES parameter (default: "
          "autodetect)")
    print("-f           Use specified YAML configuration file (instead of "
          "built-in)")
    print("-o           Specify an alternate summary output file location")
    print("-y           Specify output file should be YAML instead of JSON")
    print("-p           Print default (built-in) YAML configuration")
    print("\nExamples:")
    print("Run the benchmark using Docker, dispaying all component scores:")
    print(namel + " -dv /tmp/hs19")
    print("Run with Singularity, using a non-standard benchmark "
          "configuration:")
    print(namel + " -sf /tmp/hscore/hscore_custom.yaml /tmp/hscore\n")
    print("Additional information: https://gitlab.cern.ch/hep-benchmarks/hep-"
          "score")
    print("Questions/comments: benchmark-suite-wg-devel@cern.ch")


def proc_results(benchmark, rpath, verbose, conf):

    results = []
    fail = False
    overall_refscore = 1.0
    bench_conf = conf['benchmarks'][benchmark]
    key = bench_conf['scorekey']
    runs = int(conf['repetitions'])

    if 'refscore' in bench_conf.keys():
        if bench_conf['refscore'] is None:
            overall_refscore = 1.0
        else:
            overall_refscore = float(bench_conf['refscore'])

    if benchmark == "kv-bmk":
        benchmark_glob = "test_"
    else:
        benchmark_glob = benchmark.split('-')[:-1]
        benchmark_glob = '-'.join(benchmark_glob)

    gpaths = glob.glob(rpath + "/" + benchmark_glob + "*/*summary.json")

    i = 0
    bench_conf['report'] = {}
    for gpath in gpaths:
        jfile = open(gpath, mode='r')
        line = jfile.readline()
        jfile.close()

        jscore = json.loads(line)
        bench_conf['report']['run' + str(i)] = jscore

        try:
            if 'ref_scores' not in bench_conf.keys():
                if 'subkey' in bench_conf.keys():
                    subkey = bench_conf['subkey']
                    score = float(jscore[key][subkey]['score'])
                else:
                    score = float(jscore[key]['score'])

                score = score / overall_refscore
            else:
                sub_results = []
                for sub_bmk in bench_conf['ref_scores'].keys():
                    sub_score = float(jscore[key][sub_bmk])
                    sub_score = sub_score / bench_conf['ref_scores'][sub_bmk]
                    sub_results.append(sub_score)
                score = geometric_mean(sub_results)
        except (KeyError, ValueError):
            if not fail:
                print("\nError: score not reported for one or more runs")
                fail = True

        i = i + 1

        if not fail:
            results.append(score)
            if verbose:
                print(" " + str(score))

    if fail:
        return(-1)

    if len(results) != runs:
        print("\nError: missing json score file for one or more runs")
        return(-1)

    final_result = median(results)

    if len(results) > 1 and verbose:
        print(" Median: " + str(final_result))

    return(final_result)


def run_benchmark(benchmark, cm, output, verbose, copies, conf):

    commands = {'docker': "docker run --network=host -v " + output +
                ":/results ",
                'singularity': "singularity run -B " + output +
                ":/results docker://"}

    bench_conf = conf['benchmarks'][benchmark]
    bmark_keys = bench_conf.keys()
    bmk_options = {'debug': '-d', 'threads': '-t', 'events': '-e'}

    if copies != 0:
        options_string = " -c " + str(copies)
    else:
        options_string = ""

    runs = int(conf['repetitions'])
    log = output + "/" + conf['name'] + ".log"

    for option in bmk_options.keys():
        if option in bmark_keys and \
                str(bench_conf[option]) \
                not in ['None', 'False']:
            options_string = options_string + ' ' + bmk_options[option]
            if option != 'debug':
                options_string = options_string + ' ' + \
                    str(bench_conf[option])
    try:
        lfile = open(log, mode='a')
    except Exception:
        print("\nError: failure to open " + log)
        return(-1)

    benchmark_complete = conf['registry'] + '/' + benchmark + \
        ':' + bench_conf['version'] + options_string

    sys.stdout.write("Executing " + str(runs) + " run")
    if runs > 1:
        sys.stdout.write('s')
    sys.stdout.write(" of " + benchmark)

    command_string = commands[cm] + benchmark_complete
    command = command_string.split(' ')

    for i in range(runs):
        if verbose:
            sys.stdout.write('.')
            sys.stdout.flush()

        try:
            cmdf = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
        except Exception:
            print("\nError: failure to execute: " + command_string)
            proc_results(benchmark, output, verbose, conf)
            return(-1)

        line = cmdf.stdout.readline()
        while line:
            lfile.write(line)
            lfile.flush()
            line = cmdf.stdout.readline()

        cmdf.wait()

        if cmdf.returncode != 0:
            print(("\nError: running " + benchmark + " failed.  Exit status " +
                  str(cmdf.returncode) + "\n"))
            proc_results(benchmark, output, verbose, conf)
            return(-1)

    lfile.close()

    print("")

    result = proc_results(benchmark, output, verbose, conf)
    return(result)


def read_conf(cfile):

    global CONF

    print("Using custom configuration: " + cfile)

    try:
        yfile = open(cfile, mode='r')
        CONF = string.join(yfile.readlines(), '\n')
    except Exception:
        print("\nError: cannot open/read from " + cfile + "\n")
        sys.exit(1)


def parse_conf():

    base_keys = ['reference_machine', 'repetitions', 'method', 'benchmarks',
                 'name', 'registry']

    try:
        dat = yaml.safe_load(CONF)
    except Exception:
        print("\nError: problem parsing YAML configuration\n")
        sys.exit(1)

    try:
        for k in base_keys:
            val = dat['hepscore_benchmark'][k]
            if k == 'method':
                if val != 'geometric_mean':
                    print("Configuration error: only 'geometric_mean' method "
                          "is currently supported\n")
                    sys.exit(1)
            if k == 'registry':
                reg_string = dat['hepscore_benchmark']['registry']
                if not reg_string[0].isalpha() or reg_string.find(' ') != -1:
                    print("\nConfiguration error: illegal character in "
                          "registry")
                    sys.exit(1)
            if k == 'repetitions':
                try:
                    int(dat['hepscore_benchmark']['repetitions'])
                except ValueError:
                    print("\nConfiguration error: 'repititions' configuration "
                          "parameter must be an integer\n")
                    sys.exit(1)
    except KeyError:
        print("\nConfiguration error: " + k + " parameter must be specified")
        sys.exit(1)

    if 'scaling' in dat['hepscore_benchmark']:
        try:
            float(dat['hepscore_benchmark']['scaling'])
        except ValueError:
            print("\nConfiguration error: 'scaling' configuration parameter "
                  "must be an float\n")
            sys.exit(1)

    bcount = 0
    for benchmark in dat['hepscore_benchmark']['benchmarks']:
        bmark_conf = dat['hepscore_benchmark']['benchmarks'][benchmark]
        bcount = bcount + 1

        if not benchmark[0].isalpha() or benchmark.find(' ') != -1:
            print("\nConfiguration error: illegal character in " + benchmark)
            sys.exit(1)

        if benchmark.find('-') == -1:
            print("\nConfiguration error: expect at least 1 '-' character in "
                  "benchmark name")
            sys.exit(1)

        bmk_req_options = ['version', 'scorekey']

        for k in bmk_req_options:
            if k not in bmark_conf.keys():
                print("\nConfiguration error: missing required benchmark "
                      "option -" + k)
                sys.exit(1)

        if 'refscore' in bmark_conf.keys():
            if bmark_conf['refscore'] is not None:
                try:
                    float(bmark_conf['refscore'])
                except ValueError:
                    print("\nConfiguration error: refscore is not a float")
                    sys.exit(1)
        if 'ref_scores' in bmark_conf.keys():
            for score in bmark_conf['ref_scores']:
                try:
                    float(bmark_conf['ref_scores'][score])
                except ValueError:
                    print("\nConfiguration error: ref_score " + score +
                          " is not a float")
                    sys.exit(1)

        if set(['refscore', 'ref_scores']).issubset(set(bmark_conf.keys())):
            print("\nConfiguration error: refscore and ref_scores cannot both "
                  "be specified")
            sys.exit(1)

    if bcount == 0:
        print("\nConfiguration error: no benchmarks specified")
        sys.exit(1)

    return(dat['hepscore_benchmark'])


def median(vals):

    if len(vals) == 1:
        return(vals[0])

    vals.sort()
    med_ind = len(vals) / 2
    if len(vals) % 2 == 1:
        return(vals[med_ind])
    else:
        return((vals[med_ind] + vals[med_ind - 1]) / 2.0)


def geometric_mean(results):

    product = 1
    for result in results:
        product = product * result

    return(product ** (1.0 / len(results)))


def main():

    global CONF, NAME

    allowed_methods = {'geometric_mean': geometric_mean}
    outfile = ""
    verbose = False
    cec = ""
    outobj = {}
    copies = 0
    opost = "json"

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hpvdsyf:c:o:')
    except getopt.GetoptError as err:
        print("\nError: " + str(err) + "\n")
        help()
        sys.exit(1)

    for opt, arg in opts:
        if opt == '-h':
            help()
            sys.exit(0)
        if opt == '-p':
            if len(opts) != 1:
                print("\nError: -p must be used without other options\n")
                help()
                sys.exit(1)
            print(yaml.safe_dump(yaml.safe_load(CONF)))
            sys.exit(0)
        elif opt == '-v':
            verbose = True
        elif opt == '-f':
            read_conf(arg)
        elif opt == '-y':
            opost = 'yaml'
        elif opt == '-c':
            try:
                copies = int(arg)
            except ValueError:
                print("\nError: argument to -c must be an integer\n")
                sys.exit(1)
        elif opt == '-o':
            outfile = arg
        elif opt == '-s' or opt == '-d':
            if cec:
                print("\nError: -s and -d are exclusive\n")
                sys.exit(1)
            if opt == '-s':
                cec = "singularity"
            else:
                cec = "docker"

    if not cec:
        print("\nError: must specify run type (Docker or Singularity)\n")
        help()
        sys.exit(1)

    if len(args) < 1:
        help()
        sys.exit(1)
    else:
        output = args[0]
        if not os.path.isdir(output):
            print("\nError: output directory must exist")
            sys.exit(1)

    output = output + '/' + NAME + '_' + time.strftime("%d%b%Y_%H%M%S")
    try:
        os.mkdir(output)
    except Exception:
        print("\nError: failed to create " + output)
        sys.exit(2)

    confobj = parse_conf()

    sysname = ' '.join(os.uname())
    curtime = time.asctime()

    confobj['environment'] = {'system': sysname, 'date': curtime,
                              'container_exec': cec, 'ncopies': copies}

    print(confobj['name'] + " Benchmark")
    print("Version: " + str(confobj['version']))
    if copies > 0:
        print("Sub-benchmark NCOPIES: " + str(copies))
    print("System: " + sysname)
    print("Container Execution: " + cec)
    print("Registry: " + confobj['registry'])
    print("Output: " + output)
    print("Date: " + curtime + "\n")

    results = []
    res = 0
    for benchmark in confobj['benchmarks']:
        res = run_benchmark(benchmark, cec, output, verbose, copies, confobj)
        if res < 0:
            break
        results.append(res)

# Only compute a final score if all sub-benchmarks reported a score
    if res >= 0:
        method = allowed_methods[confobj['method']]
        fres = method(results) * confobj['scaling']

        print("\nFinal result: " + str(fres))
        confobj['final_result'] = fres
    else:
        confobj['ERROR'] = benchmark
        confobj['final_result'] = 'FAIL'

    if not outfile:
        outfile = output + '/' + confobj['name'] + '.' + opost

    if opost == 'yaml':
        outobj['hepscore_benchmark'] = confobj
    else:
        outobj = confobj

    try:
        jfile = open(outfile, mode='w')
        if opost == 'yaml':
            jfile.write(yaml.safe_dump(outobj, encoding='utf-8',
                        allow_unicode=True))
        else:
            jfile.write(json.dumps(outobj))
        jfile.close()
    except Exception:
        print("\nError: Failed to create summary output " + outfile + "\n")
        sys.exit(2)

    if res < 0:
        sys.exit(2)


if __name__ == '__main__':
    main()
