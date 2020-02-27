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


class TestOutput(unittest.TestCase):

    def extract_values(self, obj, key):
        """Pull all values of specified key from nested JSON."""
        arr = []

        def extract(obj, arr, key):
            """Recursively search for values of key in JSON tree."""
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        extract(v, arr, key)
                    elif k == key:
                        arr.append(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item, arr, key)
            return arr

        results = extract(obj, arr, key)
        return results

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
        hs = hepscore.HEPscore(**hsargs)
        hs.read_and_parse_conf(conffile=self.emptyPath)
        if hs.run(False) >= 0:
            hs.gen_score()
        with self.assertRaises(SystemExit) as cm:
            hs.write_output("json", "")

        self.assertEqual(cm.exception.code, 2)

        bmkRes = os.path.normpath(
            os.path.join(hs.resultsdir, 'HEPscore19.json'))

        keys = ["method", "name", "reference_machine", "registry",
                "repetitions", "scaling", "container_exec",
                "version", "hash", "date", "system", "container_exec",
                "hepscore_ver", "score", "status"]

        o = open(bmkRes)
        out = json.load(o)

        for i in keys:
            self.assertTrue(len(self.extract_values(out, i)) > 0)

    def test_run_bmks(self):

        if not os.path.exists('/tmp/test_run_bmks'):
            os.mkdir('/tmp/test_run_bmks')

        hsargs = {'level': 'DEBUG', 'cec': 'docker',
                  'clean': True, 'outdir': '/tmp/test_run_bmks'}
        hs = hepscore.HEPscore(**hsargs)
        hs.read_and_parse_conf(conffile=self.path)
        if hs.run(False) >= 0:
            hs.gen_score()
        with self.assertRaises(SystemExit) as cm:
            hs.write_output("json", "")

        self.assertEqual(cm.exception.code, 2)

        # bmkRes = os.path.normpath(
        #     os.path.join(hs.resultsdir, 'HEPscore19.json'))

        # keys = ["method", "name", "reference_machine", "registry",
        #         "repetitions", "scaling", "container_exec",
        #         "version", "hash", "date", "system", "container_exec",
        #         "hepscore_ver", "score", "status"]

        # o = open(bmkRes)
        # out = json.load(o)

        # for i in keys:
        #     self.assertTrue(len(self.extract_values(out, i)) > 0)

        # wl_keys =["median", "max", "score", "avg", "min", "log",
        #           "scorekey", "events", "duration", "bmkdata_checksum",
        #           "cvmfs_checksum", "version", "bmk_checksum",
        #           "copies", "threads_per_copy", "events_per_thread",
        #           "start_at", "end_at"]

        # for i in wl_keys:
        #     self.assertTrue(len(self.extract_values(out, i)) > 0)

        # checkeveryindividualbmkjson


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
