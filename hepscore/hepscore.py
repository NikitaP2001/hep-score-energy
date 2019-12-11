#!/usr/bin/python
###############################################################################
#
# hepscore.py - HEPscore benchmark execution
#

import getopt
import glob
import hashlib
import json
import math
import operator
import os
import oyaml as yaml
import pbr.version
import scipy.stats
import subprocess
import sys
import time


class HEPscore(object):

    NAME = "HEPscore"
    VER = pbr.version.VersionInfo("hep-score").version_string()

    allowed_methods = {'geometric_mean': scipy.stats.gmean}
    conffile = "etc/hepscore_default.yaml"
    level = "INFO"
    outtype = "json"
    confstr = ""
    outdir = ""
    resultsdir = ""
    suboutput = ""
    conffile = ""
    cec = ""

    confobj = {}
    results = []
    score = -1

    def __init__(self, **kwargs):

        unsettable = ['NAME', 'VER', 'confstr']

        for vn in unsettable:
            if vn in kwargs.keys():
                raise ValueError("Not permitted to set variable specified in "
                                 "constructor")

        for var in kwargs.keys():
            if var not in vars(HEPscore):
                raise ValueError("Invalid argument to constructor")

        vars(self).update(kwargs)

    def debug_print(self, dstring, newline):

        if self.level == "DEBUG":
            if newline:
                print("")
            print("DEBUG: " + dstring)

    def _proc_results(self, benchmark):

        results = {}
        fail = False
        bench_conf = self.confobj['benchmarks'][benchmark]
        key = bench_conf['scorekey']
        runs = int(self.confobj['repetitions'])

        if benchmark == "kv-bmk":
            benchmark_glob = "test_"
        else:
            benchmark_glob = benchmark.split('-')[:-1]
            benchmark_glob = '-'.join(benchmark_glob)

        gpaths = glob.glob(self.resultsdir + "/" + benchmark_glob + "*/" +
                           benchmark_glob + "_summary.json")

        self.debug_print("Looking for results in " + str(gpaths), False)
        i = 0
        for gpath in gpaths:
            self.debug_print("Opening file " + gpath, False)

            jfile = open(gpath, mode='r')
            line = jfile.readline()
            jfile.close()

            jscore = json.loads(line)
            runstr = 'run' + str(i)
            if runstr not in bench_conf:
                bench_conf[runstr] = {}
            bench_conf[runstr]['report'] = jscore

            try:

                sub_results = []
                for sub_bmk in bench_conf['ref_scores'].keys():
                    sub_score = float(jscore[key][sub_bmk])
                    sub_score = sub_score / \
                        bench_conf['ref_scores'][sub_bmk]
                    sub_score = round(sub_score, 4)
                    sub_results.append(sub_score)
                    score = scipy.stats.gmean(sub_results)

            except (KeyError, ValueError):
                if not fail:
                    print("\nError: score not reported for one or more runs." +
                          "The retrieved json report contains\n%s" % jscore)
                    fail = True

            if not fail:
                results[i] = round(score, 4)

                if self.level != "INFO":
                    print(" " + str(score))

            i = i + 1

        if len(results) == 0:
            print("\nNo results: fail")
            return(-1)

        if len(results) != runs:
            fail = True
            print("\nError: missing json score file for one or more runs")

        if fail:
            if 'allow_fail' not in self.confobj.keys() or \
                    self.confobj['allow_fail'] is False:
                return(-1)

        final_result, final_run = median_tuple(results)

    #   Insert wl-score from chosen run
        if 'wl-scores' not in self.confobj:
            self.confobj['wl-scores'] = {}
        self.confobj['wl-scores'][benchmark] = {}

        for sub_bmk in bench_conf['ref_scores'].keys():
            if len(results) % 2 != 0:
                runstr = 'run' + str(final_run)
                self.debug_print("Median selected run " + runstr, True)
                self.confobj['wl-scores'][benchmark][sub_bmk] = \
                    bench_conf[runstr]['report']['wl-scores'][sub_bmk]
            else:
                avg_names = ['run' + str(rv) for rv in final_run]
                sum = 0
                for runstr in avg_names:
                    sum = sum + \
                        bench_conf[runstr]['report']['wl-scores'][sub_bmk]
                    self.confobj['wl-scores'][benchmark][sub_bmk] = sum / 2

        if len(results) > 1 and self.level != "INFO":
            print(" Median: " + str(final_result))

        return(final_result)

    def _run_benchmark(self, benchmark, mock):

        commands = {'docker': "docker run --rm --network=host -v " +
                    self.resultsdir + ":/results ",
                    'singularity': "singularity run -B " + self.resultsdir +
                    ":/results docker://"}

        bench_conf = self.confobj['benchmarks'][benchmark]
        bmark_keys = bench_conf.keys()
        bmk_options = {'debug': '-d', 'threads': '-t', 'events': '-e',
                       'copies': '-c'}
        options_string = ""

        runs = int(self.confobj['repetitions'])
        log = self.resultsdir + "/" + self.confobj['name'] + ".log"

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

        benchmark_complete = self.confobj['registry'] + '/' + benchmark +\
            ':' + bench_conf['version'] + options_string

        sys.stdout.write("Executing " + str(runs) + " run")
        if runs > 1:
            sys.stdout.write('s')
        sys.stdout.write(" of " + benchmark + "\n")

        command_string = commands[self.cec] + benchmark_complete
        command = command_string.split(' ')
        sys.stdout.write("Running  %s " % command)

        for i in range(runs):
            if self.level != "INFO":
                sys.stdout.write('.')

            sys.stdout.flush()

            runstr = 'run' + str(i)

            bench_conf[runstr] = {}
            starttime = time.time()
            bench_conf[runstr]['start_at'] = time.ctime(starttime)
            if not mock:
                try:
                    cmdf = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
                except Exception:
                    print("\nError: failure to execute: " + command_string)
                    lfile.close()
                    bench_conf['run' + str(i)]['end_at'] = \
                        bench_conf['run' + str(i)]['start_at']
                    bench_conf['run' + str(i)]['duration'] = 0
                    self._proc_results(benchmark)
                    return(-1)

                line = cmdf.stdout.readline()
                while line:
                    lfile.write(line)
                    lfile.flush()
                    line = cmdf.stdout.readline()

                cmdf.wait()

            endtime = time.time()
            bench_conf[runstr]['end_at'] = time.ctime(endtime)
            bench_conf[runstr]['duration'] = math.floor(endtime) - \
                math.floor(starttime)

            if not mock and cmdf.returncode != 0:
                print("\nError: running " + benchmark + " failed.  Exit "
                      "status " + str(cmdf.returncode) + "\n")

                if 'allow_fail' not in self.confobj.keys() or \
                        self.confobj['allow_fail'] is False:
                    lfile.close()
                    self._proc_results(benchmark)
                    return(-1)

        lfile.close()

        print("")

        result = self._proc_results(benchmark)
        return(result)

    def read_conf(self, conffile=""):

        if conffile:
            self.conffile = conffile

        print("Using custom configuration: " + self.conffile)

        try:
            yfile = open(self.conffile, mode='r')
            self.confstr = yfile.read()
            yfile.close()
        except Exception:
            print("\nError: cannot open/read from " + self.conffile + "\n")
            sys.exit(1)

        return self.confstr

    def print_conf(self):
        print(yaml.safe_dump(self.confobj))

    def read_and_parse_conf(self, conffile=""):
        self.read_conf(conffile)
        self.parse_conf()

    def gen_score(self):

        method = self.allowed_methods[self.confobj['method']]
        fres = method(self.results)
        if 'scaling' in self.confobj.keys():
            fres = fres * self.confobj['scaling']

        fres = round(fres, 4)

        print("\nFinal result: " + str(fres))
        self.confobj['score'] = fres

    def write_output(self, outfile):

        if not outfile:
            outfile = self.resultsdir + '/' + self.confobj['name'] + '.' \
                + self.outtype

        outobj = {}
        if self.outtype == 'yaml':
            outobj['hepscore_benchmark'] = self.confobj
        else:
            outobj = self.confobj

        try:
            jfile = open(self.outfile, mode='w')
            if self.outtype == 'yaml':
                jfile.write(yaml.safe_dump(outobj, encoding='utf-8',
                            allow_unicode=True))
            else:
                jfile.write(json.dumps(outobj))
            jfile.close()
        except Exception:
            print("\nError: Failed to create summary output " + self.outfile +
                  "\n")
            sys.exit(2)

        if len(self.results) == 0 or self.results[-1] < 0:
            sys.exit(2)

    def parse_conf(self, confstr=""):

        if confstr:
            self.confstr = confstr

        base_keys = ['reference_machine', 'repetitions', 'method',
                     'benchmarks', 'name', 'registry']

        try:
            dat = yaml.safe_load(self.confstr)
        except Exception:
            print("\nError: problem parsing YAML configuration\n")
            sys.exit(1)

        try:
            for k in base_keys:
                val = dat['hepscore_benchmark'][k]
                if k == 'method':
                    if val != 'geometric_mean':
                        print("Configuration error: only 'geometric_mean'"
                              "method is currently supported\n")
                        sys.exit(1)
                if k == 'registry':
                    reg_string = dat['hepscore_benchmark']['registry']
                    if not reg_string[0].isalpha() or \
                            reg_string.find(' ') != -1:
                        print("\nConfiguration error: illegal character in "
                              "registry")
                        sys.exit(1)
                if k == 'repetitions':
                    try:
                        int(dat['hepscore_benchmark']['repetitions'])
                    except ValueError:
                        print("\nConfiguration error: 'repititions' "
                              "configuration parameter must be an integer\n")
                        sys.exit(1)
        except KeyError:
            print("\nConfiguration error: " + k + " parameter must be "
                  "specified")
            sys.exit(1)

        if 'scaling' in dat['hepscore_benchmark']:
            try:
                float(dat['hepscore_benchmark']['scaling'])
            except ValueError:
                print("\nConfiguration error: 'scaling' configuration "
                      "parameter must be an float\n")
                sys.exit(1)

        bcount = 0
        for benchmark in dat['hepscore_benchmark']['benchmarks'].keys():
            bmark_conf = dat['hepscore_benchmark']['benchmarks'][benchmark]
            bcount = bcount + 1

            if benchmark[0] == ".":
                print("\nINFO: the config has a commented entry " + benchmark +
                      " : Skipping this benchmark!!!!\n")
                dat['hepscore_benchmark']['benchmarks'].pop(benchmark, None)
                continue

            if not benchmark[0].isalpha() or benchmark.find(' ') != -1:
                print("\nConfiguration error: illegal character in " +
                      benchmark + "\n")
                sys.exit(1)

            if benchmark.find('-') == -1:
                print("\nConfiguration error: expect at least 1 '-' character "
                      "in benchmark name")
                sys.exit(1)

            bmk_req_options = ['version', 'scorekey', 'ref_scores']

            for k in bmk_req_options:
                if k not in bmark_conf.keys():
                    print("\nConfiguration error: missing required benchmark "
                          "option -" + k)
                    sys.exit(1)

            if 'ref_scores' in bmark_conf.keys():
                for score in bmark_conf['ref_scores']:
                    try:
                        float(bmark_conf['ref_scores'][score])
                    except ValueError:
                        print("\nConfiguration error: ref_score " + score +
                              " is not a float")
                        sys.exit(1)

        if bcount == 0:
            print("\nConfiguration error: no benchmarks specified")
            sys.exit(1)

        self.debug_print("The parsed config is:\n" +
                         yaml.safe_dump(dat['hepscore_benchmark']), False)

        self.confobj = dat['hepscore_benchmark']

        return self.confobj

    def run(self, mock=False):

        if self.cec and 'container_exec' in self.confobj:
            print("INFO: Overiding container_exec parameter on the "
                  "commandline\n")
        elif not self.cec:
            if 'container_exec' in self.confobj:
                if self.confobj['container_exec'] == 'singularity' or \
                        self.confobj['container_exec'] == 'docker':
                    self.cec = self.confobj['container_exec']
                else:
                    print("\nError: container_exec config parameter must "
                          "be 'singularity' or 'docker'\n")
                    sys.exit(1)
            else:
                print("\nWarning: Run type not specified on commandline or"
                      " in config - assuming docker\n")
                self.cec = "docker"

        # Creating a hash representation of the configuration object
        # to be included in the final report
        m = hashlib.sha256()
        m.update(json.dumps(self.confobj, sort_keys=True))
        self.confobj['hash'] = m.hexdigest()

        sysname = ' '.join(os.uname())
        curtime = time.asctime()

        self.confobj['environment'] = {'system': sysname, 'date': curtime,
                                       'container_exec': self.cec}

        if self.resultsdir != "" and self.outdir != "":
            return(-1)

        if self.resultsdir == "":
            self.resultsdir = self.outdir + '/' + self.NAME + '_' + \
                time.strftime("%d%b%Y_%H%M%S")

        print(self.confobj['name'] + " Benchmark")
        print("Version Hash: " + self.confobj['hash'])
        print("System: " + sysname)
        print("Container Execution: " + self.cec)
        print("Registry: " + self.confobj['registry'])
        print("Output: " + self.resultsdir)
        print("Date: " + curtime + "\n")

        self.confobj['wl-scores'] = {}
        self.confobj['hepscore_ver'] = self.VER

        if not mock:
            try:
                os.mkdir(self.resultsdir)
            except Exception:
                print("\nError: failed to create " + self.resultsdir)
                sys.exit(2)
        else:
            print("NOTE: Replaying prior results")

        res = 0
        for benchmark in self.confobj['benchmarks']:
            res = self._run_benchmark(benchmark, mock)
            if res < 0:
                break
            self.results.append(res)

        if res < 0:
            self.confobj['ERROR'] = benchmark
            self.confobj['score'] = 'FAIL'

        return res
# End of HEPScore class


def median_tuple(vals):

    sorted_vals = sorted(vals.items(), key=operator.itemgetter(1))

    med_ind = len(sorted_vals) / 2
    if len(sorted_vals) % 2 == 1:
        return(sorted_vals[med_ind][::-1])
    else:
        val1 = sorted_vals[med_ind - 1][1]
        val2 = sorted_vals[med_ind][1]
        return(((val1 + val2) / 2.0), (sorted_vals[med_ind - 1][0],
                                       sorted_vals[med_ind][0]))


def help(progname):

    namel = progname

    print(HEPscore.NAME + " Benchmark Execution - Version " + HEPscore.VER)
    print(namel + " [-s|-d] [-v] [-V] [-y] [-o OUTFILE] [-f CONF] OUTDIR")
    print(namel + " -h")
    print(namel + " -p [-f CONF]")
    print("Option overview:")
    print("-h           Print help information and exit")
    print("-v           Display verbose output, including all component "
          "benchmark scores")
    print("-d           Run benchmark containers in Docker")
    print("-s           Run benchmark containers in Singularity")
    print("-f           Use specified YAML configuration file (instead of "
          "built-in)")
    print("-o           Specify an alternate summary output file location")
    print("-y           Specify output file should be YAML instead of JSON")
    print("-p           Print configuration and exit")
    print("-V           Enable debugging output: implies -v")
    print("Examples:")
    print("Run the benchmark using Docker, dispaying all component scores:")
    print(namel + " -dv /tmp/hs19")
    print("Run with Singularity, using a non-standard benchmark "
          "configuration:")
    print(namel + " -sf /tmp/hscore/hscore_custom.yaml /tmp/hscore\n")
    print("Additional information: https://gitlab.cern.ch/hep-benchmarks/hep-"
          "score")
    print("Questions/comments: benchmark-suite-wg-devel@cern.ch")


def main():

    hsargs = {'outdir': ""}
    replay = False
    printconf_and_exit = False
    outfile = ""

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hpvVdsyrf:o:')
    except getopt.GetoptError as err:
        print("\nError: " + str(err) + "\n")
        help(sys.argv[0])
        sys.exit(1)

    for opt, arg in opts:
        if opt == '-h':
            help(sys.argv[0])
            sys.exit(0)
        if opt == '-p':
            printconf_and_exit = True
        elif opt == '-v':
            hsargs['level'] = 'VERBOSE'
        elif opt == '-V':
            hsargs['level'] = 'DEBUG'
        elif opt == '-f':
            hsargs['conffile'] = arg
        elif opt == '-y':
            hsargs['outtype'] = 'yaml'
        elif opt == '-o':
            outfile = arg
        elif opt == '-r':
            replay = True
        elif opt == '-s' or opt == '-d':
            if 'cec' in hsargs:
                print("\nError: -s and -d are exclusive\n")
                sys.exit(1)
            if opt == '-s':
                hsargs['cec'] = "singularity"
            else:
                hsargs['cec'] = "docker"

    if len(args) < 1 and not printconf_and_exit:
        help(sys.argv[0])
        sys.exit(1)
    elif len(args) >= 1:
        if replay:
            hsargs['resultsdir'] = args[0]
        else:
            hsargs['outdir'] = args[0]

        if not os.path.isdir(args[0]):
            print("\nError: output directory must exist")
            sys.exit(1)

    hs = HEPscore(**hsargs)
    hs.read_and_parse_conf()

    if printconf_and_exit:
        hs.print_conf()
        sys.exit(0)
    else:
        if hs.run(replay) >= 0:
            hs.gen_score()
        hs.write_output(outfile)


if __name__ == '__main__':
    main()
