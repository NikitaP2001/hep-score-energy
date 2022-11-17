#!/usr/bin/env python3
"""
hepscore.py - HEPscore benchmark execution

Copyright 2019-2021 CERN. See the COPYRIGHT file at the top-level directory
of this distribution. For licensing information, see the COPYING file at
the top-level directory of this distribution.
"""


import glob
import hashlib
import json
import logging
import math
import multiprocessing
import operator
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import yaml
from hepscore import __version__

logger = logging.getLogger(__name__)


def median_tuple(vals):
    """Return median of vals

    Args:
        vals (dict): A dict of benchmark scores

    Returns:
        2-tuple (result final, result run): [description]
    """
    sorted_vals = sorted(vals.items(), key=operator.itemgetter(1))

    med_ind = int(len(sorted_vals) / 2)
    if len(sorted_vals) % 2 == 1:
        return sorted_vals[med_ind][::-1]
    val1 = sorted_vals[med_ind - 1][1]
    val2 = sorted_vals[med_ind][1]
    return ((val1 + val2) / 2.0), (sorted_vals[med_ind - 1][0], sorted_vals[med_ind][0])


def weighted_geometric_mean(vals, weights=None):
    """Return geometric mean of floats, with optional weighting

    Args:
        vals (list[float]): List of float(scores)
        weights (list[float], optional): [description]. Defaults to None.

    Returns:
        float: the weighted geometric mean
    """

    if weights is None:
        weights = []
        for i in vals:
            weights.append(1.0)

    if len(vals) != len(weights):
        return 0

    # Ensure we're dealing with floats
    vals = [float(x) for x in vals]
    weights = [float(x) for x in weights]

    total_weight = sum(weights)
    if total_weight == 0:
        return 0

    weighted_vals = [vals[i] ** weights[i] for i in range(len(vals))]

    total_val = 1
    for val in weighted_vals:
        total_val *= val

    weighted_gmean = total_val ** (1.0 / total_weight)

    return weighted_gmean


class HEPscore():
    """HEPscore class."""
    allowed_methods = {'geometric_mean': weighted_geometric_mean}
    scorekey = 'wl-scores'
    cec = "singularity"
    engine = ""
    clean = False
    clean_files = False
    userns = False
    addarch = False

    scache = ""
    registry = ""
    confobj = {}
    results = []
    weights = []
    score = -1

    def __init__(self, config, resultsdir):
        """HEPSCORE: a HEP benchmark SCORE generator.

        This class orchestrates HEP benchmarks (as docker or singularity images).
        The results are collected, calculated, and parsed into JSON or YAML reports.
        See [the documentation on GitLab](https://gitlab.cern.ch/hep-benchmarks/hep-score)
        for more information.

        Contact:
            https://wlcg-discourse.web.cern.ch/c/hep-benchmarks

        Args:
            config (dict): Nested dict object with benchmark and parsing configurations
            resultsdir (str): Path to output results
        """
        self.resultsdir = os.path.abspath(resultsdir)
        self.confobj = config['hepscore_benchmark']
        self.settings = self.confobj['settings']

        if 'container_exec' in self.settings:
            if self.settings['container_exec'] in (
                    "singularity", "docker"):
                self.cec = self.settings['container_exec']
            else:
                logger.error("%s not understood. Stopping", self.settings['container_exec'])
                sys.exit(1)
        else:
            logger.warning("Container not specified on commandline or in config - assuming %s",
                           self.cec)

        if 'addarch' in self.settings:
            self.addarch = self.settings['addarch']

        if 'clean' in self.confobj.get('options', {}):
            self.clean = self.confobj['options']['clean']
            if self.cec == 'singularity':
                # Set absolut path location for scache
                self.scache = os.path.abspath(self.resultsdir + '/scache')
        if 'clean_files' in self.confobj.get('options', {}):
            self.clean_files = self.confobj['options']['clean_files']

        if 'userns' in self.confobj.get('options', {}):
            self.userns = self.confobj['options']['userns']

        self.confobj.pop('options', None)
        self.validate_conf()
        self.registry = self._gen_reg_path()

    def _gen_reg_path(self, reg_url=None):
        uri = None
        reg_path = None
        valid_uris = ['docker', 'shub', 'dir', 'oras', 'https']
        if reg_url is None:
            try:
                reg_url = self.confobj['settings']['registry']
            except KeyError:
                logger.error("Registry undefined")
                sys.exit(1)

        found_valid = False
        for uri in valid_uris:
            if reg_url.find(uri + '://') == 0:
                found_valid = True
                reg_path = reg_url[len(uri) + 3:]
                break

        if not found_valid:
            logger.error("Invalid URI specification in registry path: %s", reg_url)
            sys.exit(1)

        if self.cec == 'docker' and uri != 'docker':
            logger.error("Only docker registry URI (docker://) supported for Docker runs.")
            sys.exit(1)
        return reg_path if (self.cec == 'docker' or uri == 'dir') else reg_url

    def _proc_results(self, benchmark):

        results = {}
        bench_conf = self.confobj['benchmarks'][benchmark]
        runs = int(self.confobj['settings']['repetitions'])

        if 'results_file' in bench_conf:
            benchmark_summary = bench_conf['results_file']
        else:
            benchmark_summary = benchmark + '_summary.json'

        gpaths = sorted(glob.glob(self.resultsdir + "/" + benchmark + "/run*/" + benchmark_summary))
        logger.debug("Looking for results in %s", gpaths)
        i = -1
        for gpath in gpaths:
            i += 1
            logger.debug("Opening file %s", gpath)

            try:
                with open(gpath, mode='r') as jfile:
                    lines = jfile.read()
                    jscore = json.loads(lines)
            except OSError:
                logger.error("Failure reading from %s", gpath)
                continue
            except json.JSONDecodeError as loc:
                logger.error("Malformed JSON: %s", loc.msg)
                continue

            json_required_keys = ['app', 'run_info', 'report']
            key_issue = False
            for k in json_required_keys:
                kstr = k
                if k not in jscore.keys():
                    key_issue = True
                elif k == 'report':
                    if (not isinstance(jscore[k], dict)) or self.scorekey not in jscore[k].keys():
                        key_issue = True
                        kstr = k + '[' + self.scorekey + ']'
                if key_issue:
                    logger.error("Required key '%s' not in JSON!", kstr)

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
                if sub_bmk not in jscore['report'][self.scorekey]:
                    logger.error("Sub-score not reported for %s in %s!",
                                 sub_bmk, runstr)
                    key_issue = True
                    continue
                sub_score = float(jscore['report'][self.scorekey][sub_bmk])
                sub_score = sub_score / bench_conf['ref_scores'][sub_bmk]
                sub_score = round(sub_score, 4)
                sub_results.append(sub_score)

            if key_issue:
                continue

            score = weighted_geometric_mean(sub_results)

            results[i] = round(score, 4)
            logger.debug(results[i])

        if len(results) == 0:
            logger.warning("No results: fail")
            return -1

        if len(results) != runs:
            logger.error("Expected %d scores, got %d!", runs, len(results))
            return -1

        final_result, final_run = median_tuple(results)

        # Insert wl-score from chosen run
        if 'wl-scores' not in self.confobj:
            self.confobj['wl-scores'] = {}
        self.confobj['wl-scores'][benchmark] = {}

        for sub_bmk in bench_conf['ref_scores'].keys():
            if len(results) % 2 != 0:
                runstr = 'run' + str(final_run)
                logger.debug("Median selected run %s", runstr)
                self.confobj['wl-scores'][benchmark][sub_bmk] = \
                    bench_conf[runstr]['report']['wl-scores'][sub_bmk]
            else:
                avg_names = ['run' + str(rv) for rv in final_run]
                sum_score = 0
                for runstr in avg_names:
                    sum_score += bench_conf[runstr]['report']['wl-scores'][sub_bmk]
                    self.confobj['wl-scores'][benchmark][sub_bmk] = sum_score / 2

            self.confobj['wl-scores'][benchmark][sub_bmk + '_ref'] = \
                bench_conf['ref_scores'][sub_bmk]

        bench_conf.pop('ref_scores', None)

        if len(results) > 1:
            logger.debug(" Median: %s", final_result)

        return final_result

    def _container_rm(self, image):
        if self.clean is False:
            return False

        try:
            if self.cec == 'docker':
                logger.info("Deleting Docker image %s", image)
                command = "docker rmi -f " + image
                logger.debug(command)
                command = command.split(' ')
                ret = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                ret.wait()
            elif self.cec == 'singularity' and self.scache != "":
                if os.path.abspath(self.scache) != '/' and \
                        self.scache.endswith("/scache") and \
                        self.scache.find(self.resultsdir) == 0:
                    logger.info("Removing temporary singularity cache %s", self.scache)
                    shutil.rmtree(self.scache)
                else:
                    logger.error("Invalid cache path specified - skipping cleanup")
                    return False
        except subprocess.SubprocessError:
            logger.error("Failed to clean docker images!")
            return False
        except shutil.Error:
            logger.error("Failed to cleanup singularity cache at %s", self.scache)
            return False

        return True

    def check_userns(self):
        """Checks for user namespace support for Singularity.

        Returns:
            bool: singularity namespace support
        """
        proc_muns = "/proc/sys/user/max_user_namespaces"
        dockerenv = "/.dockerenv"
        podmanenv = "/run/.containerenv"

        if os.path.isfile(dockerenv) or os.path.isfile(podmanenv):
            logger.debug("%s running inside of Docker. Not enabling user namespaces.",
                         self.__class__)
            return False

        try:
            with open(proc_muns, mode='r') as userns_file:
                max_usrns = int(userns_file.read())
            return bool(max_usrns)
        except OSError:
            logger.debug("Cannot open/read from %s, assuming user namespace support disabled",
                         proc_muns)
            return False

    def _get_usernamespace_flag(self):
        """User namespace flag needed to support nested singularity."""
        if self.cec == "singularity" and self.userns is True:
            if self.check_userns():
                logger.debug("System supports user namespaces, enabling in singularity call")
                return "-u "
        return ""

    def check_unsquash(self):
        """Check if --unsquash is supported"""
        if self.cec != "docker" and 'apptainer_version' in self.confobj['environment']:
            hcmd = "singularity run --help".split()
            hout = subprocess.Popen(hcmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in hout.stdout.readlines():
                if '--unsquash' in line.decode('utf-8'):
                    return True

            return False

    def _get_unsquash_flag(self):
        """If we're running in apptainer that supports it, pass --unsquash"""
        if self.check_userns() and self.check_unsquash():
            logger.debug("Enabling --unsquash flag in singularity call")
            return "--unsquash "
        else:
            return ""

    def get_version(self):
        """Report version of containment choice.

        Returns:
            str: Version as reported by containment (eg `singularity --version`)
        """
        commands = {'docker': "docker --version",
                    'singularity': "singularity --version"}
        command = commands[self.cec].split(' ')

        try:
            cmdf = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            engimpl = self.cec
            for line in cmdf.stdout.readlines():
                dline = line.decode('utf-8')
                dline_ver = re.sub(r'^[^0-9]*', '', dline)
                if len(dline_ver) > 0 and dline_ver[0].isdigit():
                    if self.cec == 'singularity':
                            if 'apptainer' in dline:
                                engimpl = 'apptainer'
                    elif self.cec == 'docker':
                        helpout = subprocess.Popen(['docker', '--help'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        for hline in helpout.stdout.readlines():
                            if 'podman' in hline.decode('utf-8'):
                                engimpl = 'podman'
                                break
                    return [engimpl, str(dline_ver.strip('\n'))]

        except subprocess.SubprocessError:
            logger.error("Error fetching %s version", self.cec)
        except OSError:
            logger.error("Could not locate %s on the system. Please check your path!", self.cec)
        return ['unknown', '0.0']

    def _run_benchmark(self, benchmark, mock):

        bench_conf = self.confobj['benchmarks'][benchmark]
        options_string = " -W"
        output_logs = ['']
        bmark_keys = ''
        bmark_registry = self.registry
        bmark_reg_url = self.confobj['settings']['registry']
        result = 0
        gpu_flag = ""
        cmdf = None

        runs = int(self.confobj['settings']['repetitions'])
        log = self.resultsdir + "/" + self.confobj['settings']['name'] + ".log"

        if 'retries' in self.confobj['settings']:
            retries = int(self.confobj['settings']['retries'])
        else:
            retries = 0
        successful_runs = 0
        retry_count = 0

        bcver = bench_conf['version']
        if self.addarch and self.cec == "singularity":
            bcver = bcver + "_" + self.confobj['environment']['arch']

        tmp = "Executing " + str(runs) + " run"
        if runs > 1:
            tmp += 's'
        logger.info("%s of %s", tmp, benchmark + " [" + bcver + "]")

        if 'args' in bench_conf.keys():
            bmark_keys = bench_conf['args'].keys()

        # Allow registry overrides in the benchmark configuration
        if 'registry' in bench_conf.keys():
            bmark_reg_url = bench_conf['registry']
            bmark_registry = self._gen_reg_path(bench_conf['registry'])
            logger.info("Overriding registry for this container: %s", bmark_reg_url)

        if self.clean_files is True:
            options_string += " --mop all"

        if 'gpu' in bench_conf and bench_conf['gpu'] is True:
            if self.cec == 'singularity':
                gpu_flag = "--nv "
            else:
                gpu_flag = "--gpus all "

        for option in bmark_keys:
            bad_args = ["mop", "resultsdir", "--mop", "--resultsdir", "-m", "-w", "-W"]
            option_arg = str(bench_conf['args'][option])

            if re.match(r'^[a-zA-Z0-9\-_]*$', option) is None or \
                    option in bad_args or \
                    re.match(r'^[a-zA-Z0-9\-_]*$', option_arg) is None:
                logger.error("Ignoring invalid option in YAML configuration: %s %s",
                             option, option_arg)
                continue
            if option_arg not in ['None', 'False']:
                if option[0] != '-':
                    options_string = options_string + ' ' + '--' + option
                else:
                    options_string = options_string + ' ' + option
                if option_arg != 'True':
                    options_string = options_string + ' ' + option_arg

        try:
            lfile = open(log, mode='a')
        except OSError:
            logger.error("failure to open %s", log)
            return -1

        benchmark_name = bmark_registry + '/' + benchmark + ':' + bcver
        benchmark_complete = benchmark_name + options_string
        self.confobj['settings']['replay'] = mock

        if self.cec == 'singularity' and self.scache != "":
            logger.info("Creating singularity cache %s", self.scache)
            try:
                os.makedirs(self.scache)
                os.environ['SINGULARITY_CACHEDIR'] = self.scache
            except OSError:
                logger.error("Failed to create Singularity cache dir %s", self.scache)

        for i in range(runs + retries):
            if successful_runs == runs:
                break

            run_dir = self.resultsdir + "/" + benchmark + "/run" + str(i)
            log_filepath = run_dir + "/" + self.cec + "_logs"

            if self.confobj['settings']['replay'] is False:
                os.makedirs(run_dir)
                if self.cec == 'docker':
                    os.chmod(run_dir, stat.S_ISVTX | stat.S_IRWXU |
                             stat.S_IRWXG | stat.S_IRWXO)

            commands = {'docker': "docker run --rm --network=host -v " + run_dir
                                  + ":/results " + gpu_flag,
                        'singularity': "singularity run -i -c -e -B " + run_dir
                                       + ":/results -B /tmp "
                                       + self._get_unsquash_flag()
                                       + self._get_usernamespace_flag() + gpu_flag}

            command_string = commands[self.cec] + benchmark_complete
            command = command_string.split(' ')

            runstr = 'run' + str(i)

            logger.info("Starting %s", runstr)
            logger.debug("Running  %s", command)

            bench_conf[runstr] = {}
            starttime = time.time()
            bench_conf[runstr]['start_at'] = time.ctime(starttime)

            if not mock:
                try:
                    cmdf = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
                except (subprocess.SubprocessError, OSError):
                    if self.cec == 'docker':
                        os.chmod(run_dir, stat.S_IRWXU | stat.S_IRGRP |
                                 stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

                    logger.error("failure to execute: %s", command_string)
                    bench_conf['run' + str(i)]['end_at'] = bench_conf['run' + str(i)]['start_at']
                    bench_conf['run' + str(i)]['duration'] = 0
                    retry_count += 1
                    if retries <= 0 or retry_count > retries:
                        result = -1
                        break
                    logger.error("Retrying...")
                    continue

                line = cmdf.stdout.readline()
                while line:
                    output_logs.insert(0, line)
                    try:
                        lfile.write(line.decode('utf-8'))
                    except UnicodeEncodeError:
                        # Ignore decode errors, for example from special characters
                        pass
                    lfile.flush()
                    line = cmdf.stdout.readline()
                    if line[-25:] == "no space left on device.\n":
                        logger.error("Docker: No space left on device.")

                cmdf.wait()

                if self.cec == 'docker':
                    os.chmod(run_dir, stat.S_IRWXU | stat.S_IRGRP |
                             stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

                self._check_return_code(cmdf.returncode)
                if cmdf.returncode > 0:
                    logger.error("%s output logs:", self.cec)
                    for line in list(reversed(output_logs))[-10:]:
                        logger.error(line)
                else:
                    successful_runs += 1

                try:
                    with open(log_filepath, 'w') as log_file:
                        for line in reversed(output_logs):
                            log_file.write('%s' % line)
                except OSError:
                    logger.warning("Failed to write logs to file!")

            else:
                time.sleep(1)
                successful_runs += 1

            endtime = time.time()
            bench_conf[runstr]['end_at'] = time.ctime(endtime)
            bench_conf[runstr]['duration'] = math.floor(endtime) - math.floor(starttime)

            if not mock and cmdf.returncode != 0:
                logger.error("running %s failed.  Exit status %s", benchmark, cmdf.returncode)

                retry_count += 1
                if retries <= 0 or retry_count > retries:
                    result = -1
                    break
                logger.warning("Retrying...")

        lfile.close()
        self._container_rm(benchmark_name)
        logger.info("")

        proc_result = self._proc_results(benchmark)
        return proc_result if result != -1 else result

    def _check_return_code(self, return_code):
        if return_code == 137 and self.cec == 'docker':
            logger.error("%s returned code 137: OOM-kill or intervention", self.cec)
        elif return_code != 0:
            logger.error("%s returned code %s", self.cec, return_code)
        else:
            logger.debug("%s terminated without errors", self.cec)

    def gen_score(self):
        """Generates output score into HEPscore.confobj based on method defined in config."""
        method = self.allowed_methods[self.confobj['settings']['method']]
        fres = method(self.results, self.weights)
        if 'scaling' in self.confobj['settings'].keys():
            fres = fres * self.confobj['settings']['scaling']

        fres = round(fres, 4)

        logger.info("Final result: %s", fres)

        if math.isnan(fres):
            logger.debug("Final result is not valid")
            self.confobj['score'] = -1
            self.confobj['status'] = 'failed'
        else:
            self.confobj['score'] = float(fres)
            self.confobj['status'] = 'success'

    def write_output(self, outtype, outfile=None):
        """Writes summary results in selected `outtype` to `outfile`.

        Args:
            outtype (str): Output format. Either JSON(default) or YAML. Can be defined in
            constructor dict.
            outfile (str): Filename with extension to write to.

        Raises:
            ValueError: If `outtype` does not match filename supplied by `outfile`
        """

        if not outfile:
            outfile = self.resultsdir + '/' + self.confobj['settings']['name'] + '.' + outtype

        # check outfile is same type as outtype
        if outtype != outfile[-4:]:
            logging.warning("%s output requested, but %s does not match!", outtype, outfile)

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
                jfile.write(yaml.safe_dump(outobj, sort_keys=False))
            else:
                jfile.write(json.dumps(outobj))
            jfile.close()
        except OSError:
            logging.error("Failed to create summary output %s", outfile)
            sys.exit(2)
        except (TypeError, yaml.representer.RepresenterError):
            logging.error("Invalid output object")
            sys.exit(2)

        if len(self.results) == 0 or self.results[-1] < 0:
            logger.error("Results = %s.", self.results)
            sys.exit(2)

    def validate_conf(self):
        """Parses constructor configuration dict for valid values.

        Returns:
            dict: a valid dict (constructor dict if valid)
        """
        hep_settings = ['settings', 'benchmarks']
        required_keys = {'settings': ['method',
                                      'repetitions',
                                      'name',
                                      'registry',
                                      'reference_machine'],
                         'benchmarks': []}
        reg_string = None

        for key in hep_settings:
            if key not in self.confobj:
                logger.error("Configuration: %s section must be defined", key)
                sys.exit(1)

            for value in required_keys[key]:
                if value not in self.confobj[key]:
                    logger.error("Configuration: %s must be specified in %s", value, key)
                    sys.exit(1)

            if key == 'settings':
                for subkey in self.confobj[key]:
                    if subkey == 'registry':
                        reg_string = \
                            self.confobj[key][subkey]
                        if not reg_string[0].isalpha() or \
                                re.match(r'^[a-zA-Z0-9:/\-_\.~]*$', reg_string) is None:
                            logger.error("Configuration: illegal character in registry")
                            sys.exit(1)
                    if subkey == 'method':
                        val = self.confobj[key][subkey]
                        if val != 'geometric_mean':
                            logger.error("Configuration: only 'geometric_mean' method is "
                                         "currently supported")
                            sys.exit(1)
                    if subkey in ('repetitions', 'retries'):
                        val = self.confobj[key][subkey]
                        if (not isinstance(val, int)) or val < 0:
                            logger.error("Configuration: '%s' configuration parameter must "
                                         "be a positive integer", subkey)
                            sys.exit(1)
                    if subkey == 'addarch':
                        try:
                            bool(self.confobj[key][subkey])
                        except ValueError:
                            logger.error("Configuration: 'addarch' configuration parameter "
                                         "must be a bool")
                            sys.exit(1)
                    if subkey == 'scaling':
                        try:
                            float(self.confobj[key][subkey])
                        except ValueError:
                            logger.error("Configuration: 'scaling' configuration parameter "
                                         "must be a float")
                            sys.exit(1)

        bcount = 0
        for benchmark in list(self.confobj['benchmarks']):
            bmark_conf = self.confobj['benchmarks'][benchmark]
            bcount = bcount + 1

            if benchmark[0] == ".":
                logger.info("%s is commented out: Skipping this benchmark!", benchmark)
                self.confobj['benchmarks'].pop(benchmark, None)
                continue

            if re.match(r'^[a-zA-Z0-9\-_]*$', benchmark) is None:
                logger.error("Configuration: illegal character in benchmark name %s", benchmark)
                sys.exit(1)

            bmk_req_options = ['version']

            for key in bmk_req_options:
                if key not in bmark_conf.keys():
                    logger.error("Configuration: missing required benchmark option for %s - %s",
                                 benchmark, key)
                    sys.exit(1)

            if 'weight' in bmark_conf.keys():
                try:
                    float(bmark_conf['weight'])
                except ValueError:
                    logger.error("Configuration: invalid 'weight' specified: %s Must be a float",
                                 bmark_conf['weight'])

            if 'ref_scores' in bmark_conf.keys():
                for score in bmark_conf['ref_scores']:
                    try:
                        float(bmark_conf['ref_scores'][score])
                    except ValueError:
                        logger.error("Configuration: ref_score %s is not a float for %s",
                                     score, benchmark)
                        sys.exit(1)
            else:
                logger.error("Configuration: ref_scores missing for %s", benchmark)
                sys.exit(1)

            for pbkey in ['registry', 'results_file']:
                if pbkey in bmark_conf.keys():
                    if not bmark_conf[pbkey][0].isalpha() or \
                            re.match(r'^[a-zA-Z0-9:/\-_\.~]*$', bmark_conf[pbkey]) is None:
                        logger.error("Configuration: illegal character in %s - %s", pbkey,
                                     bmark_conf[pbkey])
                        sys.exit(1)

        if bcount == 0:
            logger.error("Configuration: no benchmarks specified")
            sys.exit(1)

        logger.debug("The parsed config is: %s", yaml.safe_dump(self.confobj, sort_keys=False))

        return self.confobj

    def run(self, mock=False):
        """Run the benchmarks defined in the constructor config dict.

        Args:
            mock (bool, optional): Skips the run call to the benchmarks, used for testing.
                                   Default: False.

        Returns:
            int: 0 on success, -1 on error
        """

        # check rundir is empty
        if os.listdir(self.resultsdir) and not mock:
            logger.error("Results directory is not empty!")
            sys.exit(2)

        # Creating a hash representation of the configuration object
        # to be included in the final report
        conf_hash = hashlib.sha256()
        hashable_conf = {k: v for k, v in self.confobj.items() if k not in 'options'}
        conf_hash.update(json.dumps(hashable_conf, sort_keys=True).encode('utf-8'))
        self.confobj['app_info'] = {}
        self.confobj['app_info']['config_hash'] = conf_hash.hexdigest()

        sysinfo = os.uname()
        sysname = ' '.join(sysinfo)
        curtime = time.asctime()

        impl,ver = self.get_version()
        exec_ver = impl + "_version"

        self.confobj['environment'] = {'system': sysname, 'arch': sysinfo.machine,
                                       'start_at': curtime, exec_ver: ver}

        logger.info("%s Benchmark", self.confobj['settings']['name'])
        logger.info("Config Hash:         %s", self.confobj['app_info']['config_hash'])
        logger.info("HEPscore version:    %s", __version__)
        logger.info("System:              %s", sysname)
        logger.info("Container Execution: %s", self.cec)
        logger.info("Registry:            %s", self.confobj['settings']['registry'])
        logger.info("Output:              %s", self.resultsdir)
        logger.info("Date:                %s\n", curtime)

        self.confobj['wl-scores'] = {}
        self.confobj['app_info']['hepscore_ver'] = __version__

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
                if 'continue_fail' not in self.confobj['settings'].keys() or \
                        self.confobj['settings']['continue_fail'] is False:
                    break
            self.results.append(res)
            bench_conf = self.confobj['benchmarks'][benchmark]
            if 'weight' in bench_conf:
                self.weights.append(bench_conf['weight'])
            else:
                self.weights.append(1.0)
                bench_conf['weight'] = 1.0

        self.confobj['environment']['end_at'] = time.asctime()

        if have_failure:
            logger.error("BENCHMARK FAILURE")
            self.confobj['score'] = -1
            self.confobj['status'] = 'failed'
            return -1

        return 0
# End of HEPscore class
