# Copyright 2019-2020 CERN. See the COPYRIGHT file at the top-level directory
# of this distribution. For licensing information, see the COPYING file at
# the top-level directory of this distribution.

from dictdiffer import diff
import hepscore
import hepscore.main
import json
import logging
import os
import oyaml as yaml
# from parameterized import parameterized
import sys
import unittest


# Import mock compatible with Python2 and Python3
try:
    from mock import mock
    from mock import patch
except ImportError:
    from unittest.mock import mock
    from unittest.mock import patch


class TestArguments(unittest.TestCase):

    def test_c_option_fails(self):
        with mock.patch.object(sys, 'argv', ["-v", "-c"]):
            with self.assertRaises(SystemExit) as cm:
                hepscore.main.main()
                self.assertEqual(cm.exception.code, 1)

    def test_h_option(self):
        with mock.patch.object(sys, 'argv', ["hepscore", "-h"]):
            with self.assertRaises(SystemExit) as cm:
                hepscore.main.main()
        self.assertEqual(cm.exception.code, 0)


class Test_Constructor(unittest.TestCase):

    def test_fail_no_conf(self):
        with self.assertRaises(TypeError):
            hepscore.HEPscore()

    def test_fail_read_conf(self):
        with self.assertRaises(KeyError):
            hepscore.HEPscore(dict())

    @patch.object(hepscore.HEPscore, 'validate_conf')
    def test_succeed_read_set_defaults(self, mock_validate):
        standard = {'hepscore_benchmark': {'settings': {}}}
        test_config = standard.copy()

        hs = hepscore.HEPscore(test_config, "/tmp")

        self.assertEqual(hs.cec, "docker")
        self.assertEqual(hs.outdir, "/tmp")
        self.assertIn('/tmp/HEPscore_', hs.resultsdir)
        self.assertEqual(hs.confobj, standard['hepscore_benchmark'])

    @patch.object(hepscore.HEPscore, 'validate_conf')
    def test_succeed_override_defaults(self, mock_validate):
        standard = {'hepscore_benchmark':
                    {'settings':
                        {'container_exec': "singularity",
                         'resultsdir': "/tmp1"}}}
        test_config = standard.copy()

        hs = hepscore.HEPscore(test_config, "/tmp")

        self.assertEqual(hs.cec, "singularity")
        self.assertEqual(hs.outdir, "/tmp")
        self.assertEqual(hs.settings['resultsdir'], "/tmp1")
        self.assertEqual(hs.confobj, standard['hepscore_benchmark'])


class TestRun(unittest.TestCase):

    def setUp(self):
        head, _ = os.path.split(__file__)
        self.path = os.path.normpath(
            os.path.join(head, 'etc/hepscore_conf_bmsreco_only.yaml'))
        self.emptyPath = os.path.normpath(
            os.path.join(head, 'etc/hepscore_empty_conf.yaml'))
        self.resPath = os.path.normpath(head)

    def test_run_empty_cfg(self):

        if not os.path.exists('/tmp/test_run_empty_cfg'):
            os.mkdir('/tmp/test_run_empty_cfg')

        with open(self.emptyPath, 'r') as yam:
            test_config = yaml.full_load(yam)

        hs = hepscore.HEPscore(test_config, "/tmp/test_run_empty_cfg")
        if hs.run(False) >= 0:
            hs.gen_score()
        with self.assertRaises(SystemExit) as cm:
            hs.write_output("json", "")
            self.assertEqual(cm.exception.code, 2)


class testOutput(unittest.TestCase):

    def test_parse_results(self):
        benchmarks = ["atlas-gen-bmk", "cms-digi-bmk", "cms-gen-sim-bmk",
                      "cms-reco-bmk", "lhcb-gen-sim-bmk"]

        head, _ = os.path.split(__file__)

        resDir = os.path.join(head, "data/HEPscore_ci_allWLs")

        conf = os.path.normpath(os.path.join(head, "etc/hepscore_conf.yaml"))

        with open(conf, 'r') as yam:
            test_config = yaml.full_load(yam)

        test_config['hepscore_benchmark']['settings']['level'] = 'DEBUG'
        test_config['hepscore_benchmark']['settings']['clean'] = True
        test_config['hepscore_benchmark']['settings']['clean_files'] = False
        test_config['hepscore_benchmark']['settings']['resultsdir'] = resDir

        outtype = "json"
        outfile = ""

        hs = hepscore.HEPscore(test_config)

        ignored_keys = ['app_info.hash', 'environment', 'settings.replay',
                        'app_info.hepscore_ver', 'score_per_core']

        for benchmark in benchmarks:
            ignored_keys.append("benchmarks." + benchmark + ".run0")
            ignored_keys.append("benchmarks." + benchmark + ".run1")
            ignored_keys.append("benchmarks." + benchmark + ".run2")

        hs.run(True)
        hs.gen_score()
        hs.write_output(outtype, outfile)

        expected_res = json.load(open(resDir +
                                      "/hepscore_result_expected_output.json"))
        actual_res = json.load(open(resDir + "/HEPscore19.json"))

        result = list(diff(expected_res, actual_res, ignore=set(ignored_keys)))

        for entry in result:
            if len(entry[2]) == 1:
                print('\n\t %s :\n\t\t %s\t%s' % entry)
            else:
                print('\n\t %s :\n\t\t %s\n\t\t\t%s\n\t\t\t%s' %
                      (entry[0], entry[1], entry[2][0], entry[2][1]))

        self.assertEqual(len(result), 0)

        os.remove(resDir + "/HEPscore19.json")

    def test_parse_corrupt_results(self):
        head, _ = os.path.split(__file__)

        resDir = os.path.join(head, "data/HEPscore_ci_empty_score")

        conf = os.path.normpath(
            os.path.join(head, "etc/hepscore_conf.yaml"))

        with open(conf, 'r') as yam:
            test_config = yaml.full_load(yam)

        test_config['hepscore_benchmark']['settings']['level'] = 'DEBUG'
        test_config['hepscore_benchmark']['settings']['clean'] = True
        test_config['hepscore_benchmark']['settings']['resultsdir'] = resDir

        outtype = "json"
        outfile = ""

        hs = hepscore.HEPscore(test_config)

        if hs.run(True) >= 0:
            hs.gen_score()
        hs.write_output(outtype, outfile)

        actual_res = json.load(open(resDir + "/HEPscore19.json"))

        self.assertEqual(actual_res['score'], -1)
        self.assertEqual(actual_res['status'], "failed")

        os.remove(resDir + "/HEPscore19.json")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - '
                        '%(funcName)s() - %(message)s',
                        stream=sys.stdout)
    unittest.main()


# Config:
# - Get conf from yaml, validate V
#
# WL Runner:
# - Run in sequence the list of WL's in config, store results
#
# Report:
# - Access WL Jsons
# - Validate WL results
# - Compute geom mean
# - Summarise WL Exit status
# - Build HEP-score json report
