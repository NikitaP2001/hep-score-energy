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
import shutil
import stat
import subprocess
import sys
import tarfile
import time


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


def weighted_geometric_mean(vals, weights=None):

    if weights is None:
        weights = []
        for i in vals:
            weights.append(1.0)

    if len(vals) != len(weights):
        return(0)

    # Ensure we're dealing with floats
    vals = [float(x) for x in vals]
    weights = [float(x) for x in weights]

    total_weight = sum(weights)
    if total_weight == 0:
        return(0)

    weighted_vals = [vals[i] ** weights[i] for i in range(len(vals))]

    total_val = 1
    for val in weighted_vals:
        total_val *= val

    weighted_gmean = total_val ** (1.0 / total_weight)

    return(weighted_gmean)


class HEPscore(object):

    NAME = "HEPscore"
    VER = pbr.version.VersionInfo("hep-score").release_string()

    allowed_methods = {'geometric_mean': weighted_geometric_mean}
    level = "INFO"
    scorekey = 'wl-scores'
    cec = "singularity"
    clean = False
    clean_files = False
    userns = False

    scache = ""
    registry = ""
    results = []
    weights = []
    score = -1

    def __init__(self, config, resultsdir):
        """Set & validate config, enable logging."""
        try:
            self.resultsdir = resultsdir
            self.confobj = config['hepscore_benchmark']
            self.settings = self.confobj['settings']
        except (TypeError, KeyError):
            # log.exception("hepscore expects a dict containing master key"
            #              "'hepscore_benchmark'")
            raise

        if self.confobj.get('options', {}).get('level') in \
                ("VERBOSE", "DEBUG"):
            self.level = self.confobj['options']['level']

        if self.level == "DEBUG":
            logging.basicConfig(level=logging.DEBUG,
                                format='%(asctime)s - %(levelname)s - '
                                '%(funcName)s() - %(message)s ',
                                stream=sys.stdout)
        else:
            logging.basicConfig(level=logging.INFO,
                                format='%(asctime)s - %(levelname)s - '
                                '%(message)s',
                                stream=sys.stdout)

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
                            " in config - assuming " + self.cec)

        if 'clean' in self.confobj.get('options', {}):
            self.clean = self.confobj['options']['clean']
            if self.cec == 'singularity':
                self.scache = resultsdir + '/scache'
        if 'clean_files' in self.confobj.get('options', {}):
            self.clean_files = self.confobj['options']['clean_files']

        if 'userns' in self.confobj.get('options', {}):
            self.userns = self.confobj['options']['userns']

        self.confobj.pop('options', None)
        self.validate_conf()
        self.registry = self._gen_reg_path()

    def _gen_reg_path(self, reg_url=None):

        valid_uris = ['docker', 'shub', 'dir']
        if reg_url is None:
            try:
                reg_url = self.confobj['settings']['registry']
            except KeyError:
                logging.error("Registry undefined")
                sys.exit(1)

        found_valid = False
        for uri in valid_uris:
            if reg_url.find(uri + '://') == 0:
                found_valid = True
                reg_path = reg_url[len(uri) + 3:]
                break

        if not found_valid:
            logging.error("Invalid URI specification in registry path: "
                          + reg_url)
            sys.exit(1)

        if self.cec == 'docker' and uri != 'docker':
            logging.error("Only docker registry URI (docker://) supported for"
                          " Docker runs.")
            sys.exit(1)

        if self.cec == 'docker' or uri == 'dir':
            return(reg_path)
        else:
            return(reg_url)

    def _proc_results(self, benchmark, mock):

        results = {}
        bench_conf = self.confobj['benchmarks'][benchmark]
        runs = int(self.confobj['settings']['repetitions'])

        benchmark_glob = benchmark.split('-')[:-1]
        benchmark_glob = '-'.join(benchmark_glob)

        gpaths = sorted(glob.glob(self.resultsdir + "/" + benchmark_glob
                                  + "/run*/" + benchmark_glob + "*/"
                                  + benchmark_glob + "_summary.json"))
        logging.debug("Looking for results in " + str(gpaths))
        i = 0
        for gpath in gpaths:
            logging.debug("Opening file " + gpath)

            try:
                with open(gpath, mode='r') as jfile:
                    lines = jfile.read()
            except Exception:
                logging.error("Failure reading from %s\n" % gpath)
                continue

            try:
                jscore = ""
                jscore = json.loads(lines)
            except Exception:
                logging.error("Malformed JSON in %s\n" % gpath)
                continue

            json_required_keys = ['app', 'run_info', 'report']
            key_issue = False
            for k in json_required_keys:
                kstr = k
                if k not in jscore.keys():
                    key_issue = True
                elif k == 'report':
                    if type(jscore[k]) != dict or self.scorekey not in \
                            jscore[k].keys():
                        key_issue = True
                        kstr = k + '[' + self.scorekey + ']'
                if key_issue:
                    logging.error("Required key %s not in JSON!" % kstr)

            if key_issue:
                continue

            runstr = 'run' + str(i)
            if runstr not in bench_conf:
                bench_conf[runstr] = {}
            bench_conf[runstr]['report'] = jscore['report']

            if i == 0:
                bench_conf['app'] = jscore['app']
                bench_conf['run_info'] = jscore['run_info']

            sub_results = []
            for sub_bmk in bench_conf['ref_scores'].keys():
                sub_score = float(jscore['report'][self.scorekey][sub_bmk])
                sub_score = sub_score / \
                    bench_conf['ref_scores'][sub_bmk]
                sub_score = round(sub_score, 4)
                sub_results.append(sub_score)
                score = weighted_geometric_mean(sub_results)

            results[i] = round(score, 4)

            if self.level != "INFO":
                logging.info(" " + str(results[i]))

            i = i + 1

        if len(results) == 0:
            logging.warning("No results: fail")
            return(-1)

        if len(results) != runs:
            logging.error("%Expected %d scores, got %d!", runs,
                          len(results))
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

    def _container_rm(self, image):
        if self.clean is False:
            return False

        if self.cec == 'docker':
            logging.info("Deleting Docker image %s", image)
            command = "docker rmi -f " + image
            logging.debug(command)
            command = command.split(' ')
            ret = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            ret.wait()
        if self.cec == 'singularity' and self.scache != "":
            if os.path.abspath(self.scache) != '/' and \
                    self.scache.find(self.resultsdir) == 0:
                logging.info("Removing temporary singularity cache %s",
                             self.scache)
                shutil.rmtree(self.scache)

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
        if self.cec == "singularity" and self.userns is True:
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
            logging.error("Error fetching " + self.cec + " version")

        try:
            line = cmdf.stdout.readline()
            line = line.decode('utf-8')

            while line:
                version = line
                if version[-1] == "\n":
                    version = version[:-1]
                line = cmdf.stdout.readline()

            return version
        except Exception:
            return "error"

    def _run_benchmark(self, benchmark, mock):

        bench_conf = self.confobj['benchmarks'][benchmark]
        options_string = ""
        output_logs = ['']
        bmark_keys = ''
        bmark_registry = self.registry
        bmark_reg_url = self.confobj['settings']['registry']

        runs = int(self.confobj['settings']['repetitions'])
        log = self.resultsdir + "/" + self.confobj['settings']['name'] + ".log"

        if 'retries' in self.confobj['settings']:
            retries = int(self.confobj['settings']['retries'])
        else:
            retries = 0
        successful_runs = 0

        tmp = "Executing " + str(runs) + " run"
        if runs > 1:
            tmp += 's'
        logging.info(tmp + " of " + benchmark)

        if 'args' in bench_conf.keys():
            bmark_keys = bench_conf['args'].keys()

        # Allow registry overrides in the benchmark configuration
        if 'registry' in bench_conf.keys():
            bmark_reg_url = bench_conf['registry']
            bmark_registry = self._gen_reg_path(bench_conf['registry'])
            logging.info("Overriding registry for this container: "
                         + bmark_reg_url)

        if self.clean_files is True:
            options_string = " -m all"

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

        if self.cec == 'singularity' and self.scache != "":
            logging.info("Creating singularity cache %s", self.scache)
            try:
                os.makedirs(self.scache)
            except Exception:
                logging.error("Failed to create Singularity cache dir " +
                              self.scache)
            os.environ['SINGULARITY_CACHEDIR'] = self.scache

        for i in range(runs + retries):
            if successful_runs == runs:
                break

            runDir = self.resultsdir + "/" + benchmark[:-4] + "/run" + str(i)
            logsFile = runDir + "/" + self.cec + "_logs"

            if self.confobj['settings']['replay'] is False:
                os.makedirs(runDir)
                if self.cec == 'docker':
                    os.chmod(runDir, stat.S_ISVTX | stat.S_IRWXU |
                             stat.S_IRWXG | stat.S_IRWXO)

            commands = {'docker': "docker run --rm --network=host -v "
                        + runDir + ":/results ",
                        'singularity': "singularity run -C -B " + runDir
                        + ":/results -B " + "/tmp:/tmp "
                        + self._get_usernamespace_flag()}

            command_string = commands[self.cec] + benchmark_complete
            command = command_string.split(' ')

            runstr = 'run' + str(i)

            logging.info("Starting " + runstr)
            logging.debug("Running  %s " % command)

            bench_conf[runstr] = {}
            starttime = time.time()
            bench_conf[runstr]['start_at'] = time.ctime(starttime)
            if not mock:
                try:
                    cmdf = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
                except Exception:
                    if self.cec == 'docker':
                        os.chmod(runDir, stat.S_IRWXU | stat.S_IRGRP |
                                 stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

                    logging.error("failure to execute: " + command_string)
                    lfile.close()
                    bench_conf['run' + str(i)]['end_at'] = \
                        bench_conf['run' + str(i)]['start_at']
                    bench_conf['run' + str(i)]['duration'] = 0
                    self._proc_results(benchmark, mock)
                    if i == (runs + retries - 1):
                        self._container_rm(benchmark_name)
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

                if self.cec == 'docker':
                    os.chmod(runDir, stat.S_IRWXU | stat.S_IRGRP |
                             stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

                self._check_rc(cmdf.returncode)
                if cmdf.returncode > 0:
                    logging.error(self.cec + " output logs:")
                    for line in list(reversed(output_logs))[-10:]:
                        print(line)
                else:
                    successful_runs += 1

                try:
                    with open(logsFile, 'w') as f:
                        for line in reversed(output_logs):
                            f.write('%s' % line)
                except Exception:
                    logging.warning("Failed to write logs to file. ")

                if i == (runs + retries - 1) or successful_runs == runs:
                    self._container_rm(benchmark_name)
            else:
                time.sleep(1)

            endtime = time.time()
            bench_conf[runstr]['end_at'] = time.ctime(endtime)
            bench_conf[runstr]['duration'] = math.floor(endtime) - \
                math.floor(starttime)

            if not mock and cmdf.returncode != 0:
                logging.error("running " + benchmark + " failed.  Exit "
                              "status " + str(cmdf.returncode) + "\n")

                if 'retries' not in self.confobj['settings'].keys() or \
                        self.confobj['settings']['retries'] <= 0:
                    lfile.close()
                    self._proc_results(benchmark, mock)
                    return(-1)

        lfile.close()

        print("")

        result = self._proc_results(benchmark, mock)
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
        fres = method(self.results, self.weights)
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
                self.confobj['settings']['name'] + '.' + outtype

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

        hep_settings = ['settings', 'benchmarks']
        rsf = {'settings': ['method', 'repetitions', 'name', 'registry',
                            'reference_machine'],
               'benchmarks': []}

        for k in hep_settings:
            if k not in self.confobj:
                logging.error("Configuration: {} section must be"
                              " defined".format(k))
                sys.exit(1)

            for f in rsf[k]:
                if f not in self.confobj[k]:
                    logging.error("Configuration: " + f + " must be "
                                  "specified in " + k)
                    sys.exit(1)

            if k == 'settings':
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
                    if j == 'method':
                        val = self.confobj[k][j]
                        if val != 'geometric_mean':
                            logging.error("Configuration: only "
                                          "'geometric_mean' method is"
                                          " currently supported")
                            sys.exit(1)
                    if j == 'repetitions' or j == 'retries':
                        val = self.confobj[k][j]
                        if not type(val) is int or val < 0:
                            logging.error("Configuration: '%s' "
                                          "configuration parameter must "
                                          "be a positive integer", j)
                            sys.exit(1)
                    if j == 'scaling':
                        try:
                            float(self.confobj[k][j])
                        except ValueError:
                            logging.error("Configuration: 'scaling' "
                                          "configuration parameter must be a "
                                          "float")
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

            if 'weight' in bmark_conf.keys():
                try:
                    float(bmark_conf['weight'])
                except ValueError:
                    logging.error("Configuration: invalid 'weight' specified:"
                                  "'" + bmark_conf['weight'] + "'."
                                  "  Must be a float")

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

        # check rundir is empty
        if os.listdir(self.resultsdir) and not mock:
            logging.error("Results directory is not empty!")
            sys.exit(2)

        # Creating a hash representation of the configuration object
        # to be included in the final report
        m = hashlib.sha256()
        hashable_conf = {k: v for k, v in self.confobj.items() if
                         k not in 'options'}
        m.update(json.dumps(hashable_conf, sort_keys=True).encode('utf-8'))
        self.confobj['app_info'] = {}
        self.confobj['app_info']['config_hash'] = m.hexdigest()

        sysname = ' '.join(os.uname())
        curtime = time.asctime()

        ver = self.get_version()
        exec_ver = self.cec + "_version"

        self.confobj['environment'] = {'system': sysname, 'date': curtime,
                                       exec_ver: ver}

        print(self.confobj['settings']['name'] + " Benchmark")
        print("Config Hash:          " +
              self.confobj['app_info']['config_hash'])
        print("System:               " + sysname)
        print("Container Execution:  " + self.cec)
        print("Registry:             " + self.confobj['settings']['registry'])
        print("Output:               " + self.resultsdir)
        print("Date:                 " + curtime + "\n")

        self.confobj['wl-scores'] = {}
        self.confobj['app_info']['hepscore_ver'] = self.VER

        if mock is True:
            logging.info("NOTE: Replaying prior results")

        res = 0
        have_failure = False
        for benchmark in self.confobj['benchmarks']:
            res = self._run_benchmark(benchmark, mock)
            if res < 0:
                have_failure = True
                # set error to first benchmark encountered
                if 'error' not in self.confobj.keys():
                    self.confobj['error'] = benchmark
                if 'continue_fail' not in \
                        self.confobj['settings'].keys() \
                        or self.confobj['settings']['continue_fail'] is False:
                    break
            self.results.append(res)
            bench_conf = self.confobj['benchmarks'][benchmark]
            if 'weight' in bench_conf:
                self.weights.append(bench_conf['weight'])
            else:
                self.weights.append(1.0)
                bench_conf['weight'] = 1.0

        if have_failure:
            logging.error("BENCHMARK FAILURE")
            self.confobj['score'] = -1
            self.confobj['status'] = 'failed'
            return(-1)

        return res
# End of HEPscore class
