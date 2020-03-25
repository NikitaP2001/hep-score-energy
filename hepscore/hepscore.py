#!/usr/bin/python
###############################################################################
#
# hepscore.py - HEPscore benchmark execution
#

import glob
import hashlib
import json
import logging
import math
import operator
import os
import oyaml as yaml
import pbr.version
import scipy.stats
import shutil
import subprocess
import sys
import tarfile
import time


class HEPscore(object):

    NAME = "HEPscore"
    VER = pbr.version.VersionInfo("hep-score").release_string()

    allowed_methods = {'geometric_mean': scipy.stats.gmean}
    conffile = '/'.join(os.path.split(__file__)[:-1]) + \
        "/etc/hepscore-default.yaml"
    level = "INFO"
    confstr = ""
    outdir = ""
    resultsdir = ""
    cec = ""
    clean = False
    clean_files = True

    confobj = {}
    results = []
    score = -1

    def __init__(self, **kwargs):

        unsettable = ['NAME', 'VER', 'confstr', 'confobj', 'results', 'score']

        for vn in unsettable:
            if vn in kwargs.keys():
                raise ValueError("Not permitted to set variable specified in "
                                 "constructor")

        for var in kwargs.keys():
            if var not in vars(HEPscore):
                raise ValueError("Invalid argument to constructor")

        vars(self).update(kwargs)

        if self.level is 'DEBUG':
            logging.basicConfig(level=logging.DEBUG,
                                format='%(asctime)s - %(levelname)s - '
                                '%(funcName)s() - %(message)s ',
                                stream=sys.stdout)
        else:
            logging.basicConfig(level=logging.INFO,
                                format='%(asctime)s - %(levelname)s - '
                                '%(message)s',
                                stream=sys.stdout)

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

        gpaths = sorted(glob.glob(self.resultsdir + "/" + benchmark_glob +
                                  "/run*/" + benchmark_glob + "*/" +
                                  benchmark_glob + "_summary.json"))
        logging.debug("Looking for results in " + str(gpaths))
        i = 0
        for gpath in gpaths:
            logging.debug("Opening file " + gpath)

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
                    logging.error("score not reported for one or more runs." +
                                  "The retrieved json report contains\n%s"
                                  % jscore)
                    fail = True

            if not fail:
                results[i] = round(score, 4)

                if self.level != "INFO":
                    logging.info(" " + str(results[i]))

            i = i + 1

        if len(results) == 0:
            logging.warning("No results: fail")
            return(-1)

        if len(results) != runs:
            fail = True
            logging.error("missing json score file for one or more runs")

        try:
            self.cleanup_fs(benchmark_glob)
        except Exception:
            logging.warning("Failed to clean up FS. Are you root?")

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
                logging.debug("Median selected run " + runstr)
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
            logging.info(" Median: " + str(final_result))

        return(final_result)

    def docker_rm(self, image):
        if self.clean and self.confobj['container_exec'] == 'docker':
            logging.info("Deleting Docker image %s", image)
            command = "docker rmi -f " + image
            logging.debug(command)
            command = command.split(' ')
            ret = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            ret.wait()

    def cleanup_fs(self, benchmark):
        if self.clean_files:
            path = self.resultsdir + "/" + benchmark + \
                "/run*/" + benchmark + "*"
            rootFiles = glob.glob(path + "/**/*.root")

            logging.debug("cleaning files: ")
            for filePath in rootFiles:
                if self.level == 'DEBUG':
                    print(filePath)
                try:
                    os.remove(filePath)
                except Exception:
                    logging.warning("Error trying to remove excessive"
                                    " root file: " + filePath)

            dirPaths = glob.glob(path)
            for dirPath in dirPaths:
                with tarfile.open(dirPath + "_benchmark.tar.gz", "w:gz") \
                        as tar:
                    tar.add(dirPath, arcname=os.path.basename(dirPath))
                shutil.rmtree(dirPath)

    def check_userns(self):
        proc_muns = "/proc/sys/user/max_user_namespaces"

        try:
            mf = open(proc_muns, mode='r')
            max_usrns = int(mf.read())
        except Exception:
            logging.info("Cannot open/read from %s, assuming user namespace"
                         "support disabled", proc_muns)
            return False

        mf.close()
        if max_usrns > 0:
            return True
        else:
            return False

    # User namespace flag needed to support nested singularity
    def get_usernamespace_flag(self):
        if self.cec == "singularity":
            if self.check_userns():
                logging.info("System supports user namespaces, enabling in "
                             "singularity call")
                return("-u ")

        return("")

    def _run_benchmark(self, benchmark, mock):

        bench_conf = self.confobj['benchmarks'][benchmark]
        bmark_keys = bench_conf.keys()
        bmk_options = {'debug': '-d', 'threads': '-t', 'events': '-e',
                       'copies': '-c'}
        options_string = ""
        output_logs = ['']

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
            logging.error("failure to open " + log)
            return(-1)

        benchmark_name = self.confobj['registry'] + '/' + benchmark +\
            ':' + bench_conf['version']
        benchmark_complete = benchmark_name + options_string

        tmp = "Executing " + str(runs) + " run"
        if runs > 1:
            tmp += 's'
        logging.info(tmp + " of " + benchmark)

        self.confobj['replay'] = mock

        for i in range(runs):
            runDir = self.resultsdir + "/" + benchmark[:-4] + "/run" + str(i)
            logsFile = runDir + "/" + self.cec + "_logs"

            if self.confobj['replay'] is False:
                os.makedirs(runDir)

            commands = {'docker': "docker run --rm --network=host -v " +
                        runDir + ":/results ",
                        'singularity': "singularity run -B " + runDir +
                        ":/results " + self.get_usernamespace_flag() +
                        "docker://"}

            command_string = commands[self.cec] + benchmark_complete
            command = command_string.split(' ')
            logging.debug("Running  %s " % command)

            runstr = 'run' + str(i)

            logging.debug("Starting " + runstr)

            bench_conf[runstr] = {}
            starttime = time.time()
            bench_conf[runstr]['start_at'] = time.ctime(starttime)
            if not mock:
                try:
                    cmdf = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
                except Exception:
                    logging.error("failure to execute: " + command_string)
                    lfile.close()
                    bench_conf['run' + str(i)]['end_at'] = \
                        bench_conf['run' + str(i)]['start_at']
                    bench_conf['run' + str(i)]['duration'] = 0
                    self._proc_results(benchmark)
                    if i == (runs - 1):
                        self.docker_rm(benchmark_name)
                    return(-1)

                line = cmdf.stdout.readline()
                while line:
                    output_logs.insert(0, line)
                    lfile.write(line.decode('utf-8'))
                    lfile.flush()
                    line = cmdf.stdout.readline()
                    if line[-25:] == "no space left on device.\n":
                        logging.error("Docker: No space left on device.")

                cmdf.wait()
                self.check_rc(cmdf.returncode)

                if cmdf.returncode > 0:
                    logging.error(self.cec + " output logs:")
                    for line in list(reversed(output_logs))[-10:]:
                        print(line)
                try:
                    with open(logsFile, 'w') as f:
                        for line in reversed(output_logs):
                            f.write('%s' % line)
                except Exception:
                    logging.warning("Failed to write logs to file. "
                                    "Are you root?")

                if i == (runs - 1):
                    self.docker_rm(benchmark_name)

            endtime = time.time()
            bench_conf[runstr]['end_at'] = time.ctime(endtime)
            bench_conf[runstr]['duration'] = math.floor(endtime) - \
                math.floor(starttime)

            if not mock and cmdf.returncode != 0:
                logging.error("running " + benchmark + " failed.  Exit "
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

    def check_rc(self, rc):
        if rc == 137 and self.cec == 'docker':
            logging.error(self.cec + " returned code 137: OOM-kill or"
                          " intervention")
        elif rc != 0:
            logging.error(self.cec + " returned code " + str(rc))
        else:
            logging.debug(self.cec + " terminated without errors")

    def read_conf(self, conffile=""):

        if conffile:
            self.conffile = conffile
            logging.info("Using custom configuration: " + self.conffile)

        try:
            yfile = open(self.conffile, mode='r')
            self.confstr = yfile.read()
            yfile.close()
        except Exception:
            logging.error("cannot open/read from " + self.conffile + "\n")
            sys.exit(1)

        return self.confstr

    def print_conf(self):
        full_conf = {'hepscore_benchmark': self.confobj}
        print(yaml.safe_dump(full_conf))

    def read_and_parse_conf(self, conffile=""):
        self.read_conf(conffile)
        self.parse_conf()

    def gen_score(self):

        method = self.allowed_methods[self.confobj['method']]
        fres = method(self.results)
        if 'scaling' in self.confobj.keys():
            fres = fres * self.confobj['scaling']

        fres = round(fres, 4)

        logging.info("Final result: " + str(fres))

        if fres != fres:
            logging.debug("Final result is not valid")
            self.confobj['score'] = -1
            self.confobj['status'] = 'FAILED'
        else:
            self.confobj['score'] = float(fres)
            self.confobj['status'] = 'SUCCESS'

    def write_output(self, outtype, outfile):

        if not outfile:
            outfile = self.resultsdir + '/' + self.confobj['name'] + '.' \
                + outtype

        outobj = {}
        if outtype == 'yaml':
            outobj['hepscore_benchmark'] = self.confobj
        elif outtype == 'json':
            outobj = self.confobj
        else:
            raise ValueError("outtype must be 'json' or 'yaml'")

        try:
            jfile = open(outfile, mode='w')
            if outtype == 'yaml':
                jfile.write(yaml.safe_dump(outobj, encoding='utf-8',
                            allow_unicode=True).decode('utf-8'))
            else:
                jfile.write(json.dumps(outobj))
            jfile.close()
        except Exception:
            logging.error("Failed to create summary output " + outfile +
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
            logging.error("problem parsing YAML configuration\n")
            sys.exit(1)

        try:
            for k in base_keys:
                val = dat['hepscore_benchmark'][k]
                if k == 'method':
                    if val != 'geometric_mean':
                        logging.error("Configuration: only 'geometric_mean'"
                                      "method is currently supported\n")
                        sys.exit(1)
                if k == 'registry':
                    reg_string = dat['hepscore_benchmark']['registry']
                    if not reg_string[0].isalpha() or \
                            reg_string.find(' ') != -1:
                        logging.error("Configuration: illegal character in "
                                      "registry")
                        sys.exit(1)
                if k == 'repetitions':
                    try:
                        int(dat['hepscore_benchmark']['repetitions'])
                    except ValueError:
                        logging.error("Configuration: 'repititions' "
                                      "configuration parameter must be"
                                      " an integer\n")
                        sys.exit(1)
        except KeyError:
            logging.error("Configuration: " + k + " parameter must be "
                          "specified")
            sys.exit(1)

        if 'scaling' in dat['hepscore_benchmark']:
            try:
                float(dat['hepscore_benchmark']['scaling'])
            except ValueError:
                logging.error("Configuration: 'scaling' configuration "
                              "parameter must be an float\n")
                sys.exit(1)

        bcount = 0
        for benchmark in dat['hepscore_benchmark']['benchmarks'].keys():
            bmark_conf = dat['hepscore_benchmark']['benchmarks'][benchmark]
            bcount = bcount + 1

            if benchmark[0] == ".":
                logging.info("the config has a commented entry " + benchmark +
                             " : Skipping this benchmark!!!!\n")
                dat['hepscore_benchmark']['benchmarks'].pop(benchmark, None)
                continue

            if not benchmark[0].isalpha() or benchmark.find(' ') != -1:
                logging.error("Configuration: illegal character in " +
                              benchmark + "\n")
                sys.exit(1)

            if benchmark.find('-') == -1:
                logging.error("Configuration: expect at least 1 '-' character "
                              "in benchmark name")
                sys.exit(1)

            bmk_req_options = ['version', 'scorekey', 'ref_scores']

            for k in bmk_req_options:
                if k not in bmark_conf.keys():
                    logging.error("Configuration: missing required benchmark "
                                  "option -" + k)
                    sys.exit(1)

            if 'ref_scores' in bmark_conf.keys():
                for score in bmark_conf['ref_scores']:
                    try:
                        float(bmark_conf['ref_scores'][score])
                    except ValueError:
                        logging.error("Configuration: ref_score " + score +
                                      " is not a float")
                        sys.exit(1)

        if bcount == 0:
            logging.error("Configuration: no benchmarks specified")
            sys.exit(1)

        logging.debug("The parsed config is:\n" +
                      yaml.safe_dump(dat['hepscore_benchmark']))

        self.confobj = dat['hepscore_benchmark']

        return self.confobj

    def run(self, mock=False):

        if self.cec and 'container_exec' in self.confobj:
            logging.info("Overiding container_exec parameter on the "
                         "commandline\n")
        elif not self.cec:
            if 'container_exec' in self.confobj:
                if self.confobj['container_exec'] == 'singularity' or \
                        self.confobj['container_exec'] == 'docker':
                    self.cec = self.confobj['container_exec']
                else:
                    logging.error("container_exec config parameter must "
                                  "be 'singularity' or 'docker'\n")
                    sys.exit(1)
            else:
                logging.warning("Run type not specified on commandline or"
                                " in config - assuming docker\n")
                self.cec = "docker"

        # Creating a hash representation of the configuration object
        # to be included in the final report
        m = hashlib.sha256()
        m.update(json.dumps(self.confobj, sort_keys=True).encode('utf-8'))
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
        print("Version Hash:         " + self.confobj['hash'])
        print("System:               " + sysname)
        print("Container Execution:  " + self.cec)
        print("Registry:             " + self.confobj['registry'])
        print("Output:               " + self.resultsdir)
        print("Date:                 " + curtime + "\n")

        self.confobj['wl-scores'] = {}
        self.confobj['hepscore_ver'] = self.VER

        if not mock:
            try:
                os.mkdir(self.resultsdir)
            except Exception:
                logging.error("failed to create " + self.resultsdir)
                sys.exit(2)
        else:
            logging.info("NOTE: Replaying prior results")

        res = 0
        for benchmark in self.confobj['benchmarks']:
            res = self._run_benchmark(benchmark, mock)
            if res < 0:
                break
            self.results.append(res)

        if res < 0:
            self.confobj['ERROR'] = benchmark
            self.confobj['score'] = -1
            self.confobj['status'] = 'FAILED'

        return res
# End of HEPscore class


def median_tuple(vals):

    sorted_vals = sorted(vals.items(), key=operator.itemgetter(1))

    med_ind = int(len(sorted_vals) / 2)
    if len(sorted_vals) % 2 == 1:
        return(sorted_vals[med_ind][::-1])
    else:
        val1 = sorted_vals[med_ind - 1][1]
        val2 = sorted_vals[med_ind][1]
        return(((val1 + val2) / 2.0), (sorted_vals[med_ind - 1][0],
                                       sorted_vals[med_ind][0]))
