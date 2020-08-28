#!/usr/bin/env python3
###############################################################################
# Copyright 2019-2020 CERN. See the COPYRIGHT file at the top-level directory
# of this distribution. For licensing information, see the COPYING file at
# the top-level directory of this distribution.
###############################################################################
#
# hepscore.py - HEPscore benchmark execution
#

import glob
import hashlib
import json
import logging
import math
import multiprocessing
import operator
import os
import oyaml as yaml
import pbr.version
import re
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
    level = "INFO"
    scorekey = 'wl-scores'
    cec = "docker"
    clean = False
    clean_files = False

    results = []
    score = -1

    def __init__(self, config, outdir=None):
        """Set & validate config, enable logging."""
        try:
            self.outdir = outdir
            self.confobj = config['hepscore_benchmark']
            self.settings = self.confobj['settings']
            if 'container_exec' in self.settings:
                if self.settings['container_exec'] in (
                        "singularity", "docker"):
                    self.cec = self.settings['container_exec']
                else:
                    logging.error(self.settings['container_exec']
                                  + "not understood. Stopping")
                    sys.exit(1)
            else:
                logging.warning("Run type not specified on commandline or"
                                " in config - assuming docker")
        except (TypeError, KeyError):
            # log.exception("hepscore expects a dict containing master key"
            #              "'hepscore_benchmark'")
            raise

        if self.confobj.get('options', {}).get('level') in \
                ("VERBOSE", "DEBUG"):
            logging.basicConfig(level=logging.DEBUG,
                                format='%(asctime)s - %(levelname)s - '
                                '%(funcName)s() - %(message)s ',
                                stream=sys.stdout)
        else:
            logging.basicConfig(level=logging.INFO,
                                format='%(asctime)s - %(levelname)s - '
                                '%(message)s',
                                stream=sys.stdout)

        if 'clean' in self.confobj.get('options', {}):
            self.clean = self.confobj['options']['clean']
        if 'clean_files' in self.confobj.get('options', {}):
            self.clean_files = self.confobj['options']['clean_files']

        # hepscore creates some subdirectories in 'outdir'
        # unless told otherwise via passed 'resultsdir'
        if 'resultsdir' not in self.confobj.get('options', {}):
            if self.outdir is None:
                logging.error("No outdir or results dir specified.")
                sys.exit(1)
            self.resultsdir = os.path.join(
                self.outdir,
                self.NAME + '_' + time.strftime("%d%b%Y_%H%M%S"))
        else:
            self.resultsdir = self.confobj['options']['resultsdir']

        self.confobj.pop('options', None)
        self.validate_conf()

    def _set_run_metadata(self, bench_conf, jscore, benchmark):
        bench_conf['app'] = jscore['app']
        bench_conf['run_info'] = {}

        bench_conf['run_info']['copies'] = jscore['copies']
        bench_conf['run_info']['threads_per_copy'] = jscore['threads_per_copy']
        bench_conf['run_info']['events_per_thread'] = \
            jscore['events_per_thread']

        return bench_conf

    def _del_run_metadata(self, jscore):
        jscore.pop('app', None)
        jscore.pop('copies', None)
        jscore.pop('threads_per_copy', None)
        jscore.pop('events_per_thread', None)

        return jscore

    def _proc_results(self, benchmark):

        results = {}
        fail = False
        bench_conf = self.confobj['benchmarks'][benchmark]
        key = 'wl-scores'
        runs = int(self.confobj['settings']['repetitions'])

        if benchmark == "kv-bmk":
            benchmark_glob = "test_"
        else:
            benchmark_glob = benchmark.split('-')[:-1]
            benchmark_glob = '-'.join(benchmark_glob)

        gpaths = sorted(glob.glob(self.resultsdir + "/" + benchmark_glob
                                  + "/run*/" + benchmark_glob + "*/"
                                  + benchmark_glob + "_summary.json"))
        logging.debug("Looking for results in " + str(gpaths))
        i = 0
        for gpath in gpaths:
            logging.debug("Opening file " + gpath)

            jfile = open(gpath, mode='r')
            line = jfile.readline()
            jfile.close()

            try:
                jscore = ""
                jscore = json.loads(line)
                runstr = 'run' + str(i)
                if runstr not in bench_conf:
                    bench_conf[runstr] = {}
                bench_conf[runstr]['report'] = jscore

                if i == 0:
                    bench_conf = self._set_run_metadata(bench_conf,
                                                        jscore, benchmark)

                jscore = self._del_run_metadata(jscore)

                bench_conf[runstr]['report'] = jscore

                sub_results = []
                for sub_bmk in bench_conf['ref_scores'].keys():
                    sub_score = float(jscore[key][sub_bmk])
                    sub_score = sub_score / \
                        bench_conf['ref_scores'][sub_bmk]
                    sub_score = round(sub_score, 4)
                    sub_results.append(sub_score)
                    score = scipy.stats.gmean(sub_results)

            except (Exception):
                if not fail:
                    logging.error("score not reported for one or more runs.")
                    if jscore != "":
                        logging.error("The retrieved json report contains\n%s"
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
            self._cleanup_fs(benchmark_glob)
        except Exception:
            logging.warning("Failed to clean up container scratch working "
                            "directory")

        if fail:
            if 'allow_fail' not in self.confobj.keys() or \
                    self.confobj['settings']['allow_fail'] is False:
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

            self.confobj['wl-scores'][benchmark][sub_bmk + '_ref'] = \
                bench_conf['ref_scores'][sub_bmk]

        bench_conf.pop('ref_scores', None)

        if len(results) > 1 and self.level != "INFO":
            logging.info(" Median: " + str(final_result))

        return(final_result)

    def _docker_rm(self, image):
        if self.clean and self.cec == 'docker':
            logging.info("Deleting Docker image %s", image)
            command = "docker rmi -f " + image
            logging.debug(command)
            command = command.split(' ')
            ret = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            ret.wait()

    def root_filter(self, f):
        if re.match(r'.*\.root$', f.name):
            logging.debug("Skipping " + f.name)
            return None
        else:
            return f

    def _cleanup_fs(self, benchmark):
        if self.clean_files:
            if self.cec == 'docker' and os.getuid() != 0:
                logging.info("Running as non-root with docker: skipping "
                             "container scratchdir cleanup")
                return False

            wp = self.resultsdir + "/" + benchmark
            if benchmark == '' or benchmark.find('/') != -1 or \
                    os.path.abspath(wp) == '/' or wp == '' or \
                    wp.find('..') != -1:
                logging.info("Invalid path: skipping container scratchdir "
                             "cleanup")
                return False

            for rundir in os.listdir(wp):
                rundir_path = os.path.join(wp, rundir)
                if re.match('^run[0-9]*', rundir) and \
                        os.path.islink(rundir_path) is False:
                    for resdir in os.listdir(rundir_path):
                        resdir_path = os.path.join(rundir_path, resdir)
                        if re.match("^" + benchmark + ".*", resdir) and \
                                os.path.islink(resdir_path) is False and \
                                os.path.isdir(resdir_path) is True:
                            with tarfile.open(resdir_path
                                              + "_benchmark.tar", "w") as tar:
                                logging.info("Tarring up " + resdir_path)
                                tar.add(resdir_path,
                                        arcname=os.path.basename(resdir_path),
                                        filter=self.root_filter)
                                if os.path.abspath(resdir_path) != '/' and \
                                        resdir_path.find(self.resultsdir) == 0:
                                    logging.info("Removing result directory "
                                                 + resdir_path)
                                    shutil.rmtree(resdir_path)
                                else:
                                    logging.info("Invalid path: skipping "
                                                 "container scratchdir "
                                                 "removal")
                                    return False
                                tar.close()

            return True

        return False

    def check_userns(self):
        proc_muns = "/proc/sys/user/max_user_namespaces"
        dockerenv = "/.dockerenv"

        try:
            cg = open(dockerenv, mode='r')
            cg.close()
            logging.debug(self.NAME + " running inside of Docker.  "
                          "Not enabling user namespaces.")
            return False
        except Exception:
            logging.debug(self.NAME + " not running inside Docker.")

        try:
            mf = open(proc_muns, mode='r')
            max_usrns = int(mf.read())
        except Exception:
            if self.level != 'INFO':
                logging.info("Cannot open/read from %s, assuming user "
                             "namespace support disabled", proc_muns)
            return False

        mf.close()
        if max_usrns > 0:
            return True
        else:
            return False

    # User namespace flag needed to support nested singularity
    def _get_usernamespace_flag(self):
        if self.cec == "singularity":
            if self.check_userns():
                if self.level != 'INFO':
                    logging.info("System supports user namespaces, enabling in"
                                 " singularity call")
                return("-u ")

        return("")

    def get_version(self):

        commands = {'docker': "docker --version",
                    'singularity': "singularity --version"}

        try:
            command = commands[self.cec].split(' ')
            cmdf = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
        except Exception:
            logging.error("Error fetching" + self.cec + "version")

        try:
            line = cmdf.stdout.readline()

            while line:
                version = line
                if version[-1] == "\n":
                    version = version[:-1]
                line = cmdf.stdout.readline()

            return version.encode('utf-8')
        except Exception:
            return "error"

    def _run_benchmark(self, benchmark, mock):

        bench_conf = self.confobj['benchmarks'][benchmark]
        options_string = ""
        output_logs = ['']
        bmark_keys = ''
        bmark_registry = self.confobj['app_info']['registry']

        runs = int(self.confobj['settings']['repetitions'])
        log = self.resultsdir + "/" + self.confobj['app_info']['name'] + ".log"

        tmp = "Executing " + str(runs) + " run"
        if runs > 1:
            tmp += 's'
        logging.info(tmp + " of " + benchmark)

        if 'args' in bench_conf.keys():
            bmark_keys = bench_conf['args'].keys()

        # Allow registry overrides in the benchmark configuration
        if 'registry' in bench_conf.keys():
            bmark_registry = bench_conf['registry']
            logging.info("Overriding registry for this container: "
                         + bmark_registry)

        for option in bmark_keys:
            if len(option) != 2 or option[0] != '-' or \
                    option[1].isalnum() is False or \
                    str(bench_conf['args'][option]).isalnum() is False:
                logging.error("Ignoring invalid option in YAML configuration '"
                              + option + " " + bench_conf['args'][option])
                continue
            if str(bench_conf['args'][option]) not in ['None', 'False']:
                options_string = options_string + ' ' + option
                if str(bench_conf['args'][option]) != 'True':
                    options_string = options_string + ' ' + \
                        str(bench_conf['args'][option])

        try:
            lfile = open(log, mode='a')
        except Exception:
            logging.error("failure to open " + log)
            return(-1)

        benchmark_name = bmark_registry + '/' + benchmark + ':' + \
            bench_conf['version']
        benchmark_complete = benchmark_name + options_string

        self.confobj['settings']['replay'] = mock

        for i in range(runs):
            runDir = self.resultsdir + "/" + benchmark[:-4] + "/run" + str(i)
            logsFile = runDir + "/" + self.cec + "_logs"

            if self.confobj['settings']['replay'] is False:
                os.makedirs(runDir)

            commands = {'docker': "docker run --rm --network=host -v "
                        + runDir + ":/results ",
                        'singularity': "singularity run -C -B " + runDir
                        + ":/results -B " + "/tmp:/tmp "
                        + self._get_usernamespace_flag() + "docker://"}

            command_string = commands[self.cec] + benchmark_complete
            command = command_string.split(' ')

            runstr = 'run' + str(i)

            logging.info("Starting " + runstr)
            logging.debug("Running  %s " % command)

            bench_conf[runstr] = {}
            starttime = time.time()
            bench_conf[runstr]['start_at'] = time.ctime(starttime)
            if not mock:
                if self.cec == 'singularity':
                    os.environ['SINGULARITYENV_PYTHONNOUSERSITE'] = "1"
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
                        self._docker_rm(benchmark_name)
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
                self._check_rc(cmdf.returncode)

                if cmdf.returncode > 0:
                    logging.error(self.cec + " output logs:")
                    for line in list(reversed(output_logs))[-10:]:
                        print(line)
                try:
                    with open(logsFile, 'w') as f:
                        for line in reversed(output_logs):
                            f.write('%s' % line)
                except Exception:
                    logging.warning("Failed to write logs to file. ")

                if i == (runs - 1):
                    self._docker_rm(benchmark_name)
            else:
                time.sleep(1)

            endtime = time.time()
            bench_conf[runstr]['end_at'] = time.ctime(endtime)
            bench_conf[runstr]['duration'] = math.floor(endtime) - \
                math.floor(starttime)

            if not mock and cmdf.returncode != 0:
                logging.error("running " + benchmark + " failed.  Exit "
                              "status " + str(cmdf.returncode) + "\n")

                if 'allow_fail' not in self.confobj['settings'].keys() or \
                        self.confobj['settings']['allow_fail'] is False:
                    lfile.close()
                    self._proc_results(benchmark)
                    return(-1)

        lfile.close()

        print("")

        result = self._proc_results(benchmark)
        return(result)

    def _check_rc(self, rc):
        if rc == 137 and self.cec == 'docker':
            logging.error(self.cec + " returned code 137: OOM-kill or"
                          " intervention")
        elif rc != 0:
            logging.error(self.cec + " returned code " + str(rc))
        else:
            logging.debug(self.cec + " terminated without errors")

    def gen_score(self):

        method = self.allowed_methods[self.confobj['settings']['method']]
        fres = method(self.results)
        if 'scaling' in self.confobj['settings'].keys():
            fres = fres * self.confobj['settings']['scaling']

        fres = round(fres, 4)

        logging.info("Final result: " + str(fres))

        if fres != fres:
            logging.debug("Final result is not valid")
            self.confobj['score_per_core'] = -1
            self.confobj['score'] = -1
            self.confobj['status'] = 'failed'
        else:
            self.confobj['score'] = float(fres)
            self.confobj['status'] = 'success'
            try:
                spc = float(fres) / float(multiprocessing.cpu_count())
                self.confobj['score_per_core'] = round(spc, 3)
            except Exception:
                self.confobj['score_per_core'] = -1
                logging.warning('Could not determine core count')

    def write_output(self, outtype, outfile):

        if not outfile:
            outfile = self.resultsdir + '/' + \
                self.confobj['app_info']['name'] + '.' + outtype

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
            logging.error("Failed to create summary output " + outfile)
            sys.exit(2)

        if len(self.results) == 0 or self.results[-1] < 0:
            sys.exit(2)

    def validate_conf(self):

        hep_settings = ['settings', 'app_info', 'benchmarks']

        for k in hep_settings:
            if k not in self.confobj:
                logging.error("Configuration: {} section must be"
                              " defined".format(k))
                sys.exit(1)
            try:
                if k == 'settings':
                    for j in self.confobj[k]:
                        if j == 'method':
                            val = self.confobj[k][j]
                            if val != 'geometric_mean':
                                logging.error("Configuration: only "
                                              "'geometric_mean' method is"
                                              " currently supported")
                                sys.exit(1)
                        if j == 'repetitions':
                            val = self.confobj[k][j]
                            if not type(val) is int:
                                logging.error("Configuration: 'repititions' "
                                              "configuration parameter must "
                                              "be an integer")
                                sys.exit(1)
                if k == 'app_info':
                    for j in self.confobj[k]:
                        if j == 'registry':
                            reg_string = \
                                self.confobj[k][j]
                            if not reg_string[0].isalpha() or \
                                    re.match(r'^[a-zA-Z0-9:/\-_\.~]*$',
                                             reg_string) is None:
                                logging.error("Configuration: illegal "
                                              "character in registry")
                                sys.exit(1)
            except KeyError:
                logging.error("Configuration: " + k + " parameter must be "
                              "specified")
                sys.exit(1)

        if 'scaling' in self.confobj['settings']:
            try:
                float(self.confobj['settings']['scaling'])
            except ValueError:
                logging.error("Configuration: 'scaling' configuration "
                              "parameter must be an float")
                sys.exit(1)

        bcount = 0
        for benchmark in list(self.confobj['benchmarks']):
            bmark_conf = self.confobj['benchmarks'][benchmark]
            bcount = bcount + 1

            if benchmark[0] == ".":
                logging.info("the config has a commented entry " + benchmark
                             + " : Skipping this benchmark!")
                self.confobj['benchmarks'].pop(benchmark, None)
                continue

            if re.match(r'^[a-zA-Z0-9\-_]*$', benchmark) is None:
                logging.error("Configuration: illegal character in benchmark"
                              + "name " + benchmark)
                sys.exit(1)

            if benchmark.find('-') == -1:
                logging.error("Configuration: expect at least 1 '-' character "
                              "in benchmark name " + benchmark)
                sys.exit(1)

            bmk_req_options = ['version']

            for k in bmk_req_options:
                if k not in bmark_conf.keys():
                    logging.error("Configuration: missing required benchmark "
                                  "option for " + benchmark + " - " + k)
                    sys.exit(1)

            if 'ref_scores' in bmark_conf.keys():
                for score in bmark_conf['ref_scores']:
                    try:
                        float(bmark_conf['ref_scores'][score])
                    except ValueError:
                        logging.error("Configuration: ref_score " + score
                                      + " is not a float for " + benchmark)
                        sys.exit(1)
            else:
                logging.error("Configuration: ref_scores missing for "
                              + benchmark)
                sys.exit(1)

            if 'registry' in bmark_conf.keys():
                if not reg_string[0].isalpha() or \
                        re.match(r'^[a-zA-Z0-9:/\-_\.~]*$',
                                 reg_string) is None:
                    logging.error("Configuration: illegal "
                                  "character in registry")
                    sys.exit(1)

        if bcount == 0:
            logging.error("Configuration: no benchmarks specified")
            sys.exit(1)

        logging.debug("The parsed config is: {}".format(
                      yaml.safe_dump(self.confobj)))

        return self.confobj

    def run(self, mock=False):

        # Creating a hash representation of the configuration object
        # to be included in the final report
        m = hashlib.sha256()
        hashable_conf = {k: v for k, v in self.confobj.items() if
                         k not in 'options'}
        m.update(json.dumps(hashable_conf, sort_keys=True).encode('utf-8'))
        self.confobj['app_info']['hash'] = m.hexdigest()

        sysname = ' '.join(os.uname())
        curtime = time.asctime()

        ver = self.get_version()
        exec_ver = self.cec + "_version"

        self.confobj['environment'] = {'system': sysname, 'date': curtime,
                                       exec_ver: ver}

        print(self.confobj['app_info']['name'] + " Benchmark")
        print("Config Hash:          " + self.confobj['app_info']['hash'])
        print("System:               " + sysname)
        print("Container Execution:  " + self.cec)
        print("Registry:             " + self.confobj['app_info']['registry'])
        print("Output:               " + self.resultsdir)
        print("Date:                 " + curtime + "\n")

        self.confobj['wl-scores'] = {}
        self.confobj['app_info']['hepscore_ver'] = self.VER

        if not mock:
            # python2 workaround, exists_ok flag not yet implemented
            if os.path.exists(self.resultsdir):
                logging.warning("Found existing results directory")
            else:
                try:
                    os.makedirs(self.resultsdir)
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
            self.confobj['error'] = benchmark
            self.confobj['score'] = -1
            self.confobj['status'] = 'failed'

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
