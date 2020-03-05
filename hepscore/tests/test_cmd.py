from dictdiffer import diff
import hepscore
import hepscore.main
import json
import os
# from parameterized import parameterized
import shutil
import sys
import unittest

# Import mock compatible with Python2 and Python3
try:
    import mock
except ImportError:
    from unittest.mock import mock


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


class TestConf(unittest.TestCase):

    def setUp(self):
        head, _ = os.path.split(__file__)
        self.path = os.path.normpath(
            os.path.join(head, 'etc/hepscore_conf.yaml'))

    def test_fail_read_conf(self):
        with self.assertRaises(SystemExit) as cm:
            hs = hepscore.HEPscore(conffile="")
            hs.read_conf('does_not_exist')
            self.assertEqual(cm.exception.code, 1)

    def test_succeed_read_conf(self):
        hs = hepscore.HEPscore()
        hs.read_conf(conffile=self.path)
        with open(self.path) as f:
            test_conf = f.read()
        self.assertEqual(hs.confstr, test_conf)


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

        hsargs = {'level': 'DEBUG', 'cec': 'docker',
                  'clean': True, 'outdir': '/tmp/test_run_empty_cfg'}

        heps = hepscore.HEPscore(**hsargs)
        heps.read_and_parse_conf(conffile=self.emptyPath)
        if heps.run(False) >= 0:
            heps.gen_score()
        with self.assertRaises(SystemExit) as cm:
            heps.write_output("json", "")
            self.assertEqual(cm.exception.code, 2)


class testOutput(unittest.TestCase):

    def test_parse_results(self):
        benchmarks = ["atlas-gen-bmk", "atlas-sim-bmk", "cms-digi-bmk",
                      "cms-gen-sim-bmk", "cms-reco-bmk"]

        head, _ = os.path.split(__file__)

        resDir = os.path.join(head + "/data/HEPscore_ci_allWLs")

        conf = os.path.normpath(
            os.path.join(head, "data/HEPscore_ci_allWLs/hepscore_conf.yaml"))

        hsargs = {'level': 'DEBUG', 'cec': 'docker',
                  'clean': True,
                  'resultsdir': resDir}

        outtype = "json"
        outfile = ""

        hs = hepscore.HEPscore(**hsargs)
        hs.read_and_parse_conf(conffile=conf)

        ignored_keys = ['hash', 'environment']

        for benchmark in benchmarks:
            hs.results.append(hs._proc_results(benchmark))
            ignored_keys.append("benchmarks." + benchmark + ".run0")
            ignored_keys.append("benchmarks." + benchmark + ".run1")
            ignored_keys.append("benchmarks." + benchmark + ".run2")

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


if __name__ == '__main__':
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
