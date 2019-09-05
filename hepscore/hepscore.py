#!/usr/bin/python
###############################################################################
#
# hepscore.py - HEPscore benchmark execution
# Chris Hollowell <hollowec@bnl.gov>
#
#

import sys
import getopt
import string
import os
import subprocess
import time
import json
import glob
import yaml

NAME = "HEPscore"

CONF = """
hepscore_benchmark:
  name: HEPscore19
  version: 0.3
  repetitions: 3  # number of repetitions of the same benchmark
  reference_machine: 'Intel Core i5-4590 @ 3.30GHz - 1 Logical Core'
  method: geometric_mean # or any other algorithm
  registry: gitlab-registry.cern.ch/hep-benchmarks/hep-workloads
  benchmarks:
    atlas-sim-bmk:
      version: v0.18
      scorekey: CPU_score
      refscore: 0.0052
    cms-reco-bmk:
      version: v0.11
      scorekey: throughput_score
      refscore: 0.1625
      normalization: 10.0
    lhcb-gen-sim:
      version: v0.5
      refscore: 7.1811
      scorekey: througput_score
      debug: false
      events:
      threads:
"""


def help():

    global NAME

    namel = NAME.lower()

    print NAME + " Benchmark Execution"
    print namel + " {-s|-d} [-v] [-f CONFIGFILE] OUTPUTDIR"
    print namel + " -h"
    print namel + " -p"
    print "Option overview:"
    print "-h           Print help information and exit"
    print("-v           Display verbose output, including all component "
          "benchmark scores")
    print "-d           Run benchmark containers in Docker"
    print "-s           Run benchmark containers in Singularity"
    print("-f           Use specified YAML configuration file (instead of "
          "built-in)")
    print "-p           Print default (built-in) YAML configuration"
    print "\nExamples"
    print "--------"
    print "Run the benchmark using Docker, dispaying all component scores:"
    print namel + " -dv /tmp/hs19"
    print "Run with Singularity, using a non-standard benchmark configuration:"
    print namel + " -sf /tmp/hscore/hscore_custom.yaml /tmp/hscore\n"
    print("Additional information: https://gitlab.cern.ch/hep-benchmarks/hep-"
          "score")
    print "Questions/comments: benchmark-suite-wg-devel@cern.ch"


def proc_results(benchmark, key, subkey, rpath, runs, verbose):

    average_score = 0
    results = []

    if benchmark == "kv-bmk":
        benchmark_glob = "test_"
    else:
        try:
            benchmark_glob = benchmark.split('-')[:-1]
        except:
            print "\nError: expect at least 1 '-' character in benchmark name"
            sys.exit(2)

        benchmark_glob = '-'.join(benchmark_glob)

    gpaths = glob.glob(rpath + "/" + benchmark_glob + "*/*summary.json")

    for gpath in gpaths:
        jfile = open(gpath, mode='r')
        line = jfile.readline()
        jfile.close()

        jscore = json.loads(line)

        try:
            if subkey is None:
                score = float(jscore[key]['score'])
            else:
                print subkey
                score = float(jscore[key][subkey]['score'])
        except (KeyError, ValueError):
            print "\nError: score not reported"
            sys.exit(2)

        if verbose:
            print " " + str(score)
        try:
            float(score)
        except ValueError:
            print "\nError: invalid score for one or more runs"
            sys.exit(2)
        results.append(score)

    if len(results) != runs:
        print "\nError: missing json score file for one or more runs"
        sys.exit(2)

    final_result = median(results)

    if len(results) > 1 and verbose:
        print " Median: " + str(final_result)

    return(final_result)


def run_benchmark(benchmark, cm, output, verbose, conf):

    commands = {'docker': "docker run --network=host -v " + output +
                ":/results ",
                'singularity': "singularity run -B " + output +
                ":/results docker://"}

    score_modifiers = {'normalization': 1.0, 'refscore': 1.0}

    req_options = ['version', 'scorekey']
    bmk_options = {'debug': '-d', 'threads': '-t', 'events': '-e'}
    options_string = ""

    runs = int(conf['repetitions'])
    log = output + "/" + conf['name'] + ".log"

    for modifier in score_modifiers.keys():
        if modifier in conf['benchmarks'][benchmark]:
            if conf['benchmarks'][benchmark][modifier] is not None:
                try:
                    score_modifiers[modifier] = \
                        float(conf['benchmarks'][benchmark][modifier])
                except Key:
                    print("\nError: configuration error, non-float value for "
                          + modifier)
                    sys.exit(2)

    for key in req_options:
        if key not in conf['benchmarks'][benchmark]:
            print("\nError: configuration error, missing required benchmark "
                  "option -" + key)
            sys.exit(2)

    scorekey = conf['benchmarks'][benchmark]['scorekey']
    try:
        subkey = conf['benchmarks'][benchmark]['subkey']
    except KeyError:
        subkey = None

    for option in bmk_options.keys():
        if option in conf['benchmarks'][benchmark].keys() and \
                str(conf['benchmarks'][benchmark][option]) \
                not in ['None', 'False']:
            options_string = options_string + ' ' + bmk_options[option]
            if option != 'debug':
                options_string = options_string + ' ' + \
                    str(conf['benchmarks'][benchmark][option])
    try:
        lfile = open(log, mode='a')
    except:
        print "\nError: failure to open " + log

    benchmark_complete = conf['registry'] + '/' + benchmark + \
        ':' + conf['benchmarks'][benchmark]['version'] + options_string

    sys.stdout.write("Executing " + str(runs) + " run")
    if runs > 1:
        sys.stdout.write('s')
    sys.stdout.write(" of " + benchmark)

    command = commands[cm] + benchmark_complete

    for i in range(runs):
        if verbose:
            sys.stdout.write('.')
            sys.stdout.flush()

        try:
            cmdf = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, shell=True)
        except:
            print "\nError: failure to execute: " + command
            sys.exit(2)

        line = cmdf.stdout.readline()
        while line:
            lfile.write(line)
            lfile.flush()
            line = cmdf.stdout.readline()

        cmdf.wait()

        if cmdf.returncode != 0:
            print("\nError: running " + benchmark + " failed.  Exit status " +
                  str(cmdf.returncode) + "\n")
            sys.exit(2)

    lfile.close()

    print

    result = proc_results(benchmark, scorekey, subkey, output,
                          runs, verbose) / score_modifiers['refscore']
    return(result * score_modifiers['normalization'])


def read_conf(cfile):

    global CONF

    print "Using custom configuration: " + cfile

    try:
        yfile = open(cfile, mode='r')
        CONF = string.join((yfile.readlines()), '\n')
    except:
        print "\nError: cannot open/read from " + cfile + "\n"
        sys.exit(1)


def parse_conf():

    base_keys = ['reference_machine', 'repetitions', 'method', 'benchmarks',
                 'name', 'registry']

    try:
        dat = yaml.safe_load(CONF)
    except:
        print "\nError: problem parsing YAML configuration\n"
        sys.exit(1)

    rkeys = dat.keys()

    try:
        for k in base_keys:
            val = dat['hepscore_benchmark'][k]
            if k == 'method':
                if val != 'geometric_mean':
                    print("Configuration error: only 'geometric_mean' method "
                          "is currently supported\n")
                    sys.exit(1)
            if k == 'repeititions':
                try:
                    val = int(confobj['hepscore_benchmark']['repetitions'])
                except ValueError:
                    print("Error: 'repititions' configuration parameter must "
                          "be an integer\n")
    except KeyError:
        print "\nError: invalid HEP benchmark YAML configuration\n"
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

    verbose = False
    cms = ""

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hpvdsf:')
    except getopt.GetoptError as err:
        print "\nError: " + str(err) + "\n"
        help()
        sys.exit(1)

    for opt, arg in opts:
        if opt == '-h':
            help()
            sys.exit(0)
        if opt == '-p':
            if len(opts) != 1:
                print "\nError: -p must be used without other options\n"
                help()
                sys.exit(1)
            print yaml.dump(yaml.load(CONF))
            sys.exit(0)
        elif opt == '-v':
            verbose = True
        elif opt == '-f':
            read_conf(arg)
        elif opt == '-s' or opt == '-d':
            if cms != '':
                print "\nError: -s and -d are exclusive\n"
                sys.exit(1)
            if opt == '-s':
                cms = "singularity"
            else:
                cms = "docker"

    if cms == "":
        print "\nError: must specify run type (Docker or Singularity)\n"
        help()
        sys.exit(1)

    if len(args) < 1:
        help()
        sys.exit(1)
    else:
        output = args[0]
        if not os.path.isdir(output):
            print "\nError: output directory must exist"
            sys.exit(1)

    output = output + '/' + NAME + '_' + time.strftime("%d%b%Y_%H%M%S")
    try:
        os.mkdir(output)
    except:
        print "\nError: failed to create " + output
        sys.exit(2)

    confobj = parse_conf()

    print confobj['name'] + " Benchmark"
    print "Version: " + str(confobj['version'])
    print "System: " + ' '.join(os.uname())
    print "Container Execution: " + cms
    print "Registry: " + confobj['registry']
    print "Output: " + output
    print "Date: " + time.asctime()
    print

    results = []
    for benchmark in confobj['benchmarks']:
        results.append(run_benchmark(benchmark, cms, output, verbose, confobj))

    method_string = str(confobj['method']) + '(results)'

    print "\nFinal result: " + str(eval(method_string))


if __name__ == '__main__':
    main()
