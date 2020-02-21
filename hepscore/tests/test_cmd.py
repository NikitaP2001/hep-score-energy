from hepscore import hepscore
import json
import os
# from parameterized import parameterized
import sys
import unittest

# Import mock compatible with Python2 and Python3
try:
    import mock
except ImportError:
    from unittest import mock


class TestArguments(unittest.TestCase):

    def test_c_option_fails(self):
        with mock.patch.object(sys, 'argv', ["-v", "-c"]):
            with self.assertRaises(SystemExit) as cm:
                hepscore.main()
                self.assertEqual(cm.exception.code, 1)

    def test_h_option(self):
        with mock.patch.object(sys, 'argv', ["hepscore", "-h"]):
            with self.assertRaises(SystemExit) as cm:
                hepscore.main()
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
            os.path.join(head, 'etc/hepscore_conf.yaml'))
        self.emptyPath = os.path.normpath(
            os.path.join(head, 'etc/hepscore_empty_conf.yaml'))
        self.resPath = os.path.normpath(
            os.path.join(head, 'data/expected_output.json'))

    def test_run_empty_cfg(self):
        count = 0

        hsargs = {'level': 'DEBUG', 'cec': 'docker',
                  'clean': True, 'outdir': '/tmp'}
        hs = hepscore.HEPscore(**hsargs)
        hs.read_and_parse_conf(conffile=self.emptyPath)
        if hs.run(False) >= 0:
            hs.gen_score()
        with self.assertRaises(SystemExit) as cm:
            hs.write_output("json", "")
            self.assertEqual(cm.exception.code, 2)

        bmkRes = os.path.normpath(
            os.path.join(hs.resultsdir, 'HEPscore19.json'))

        with open(self.resPath) as eo:
            expected_output = json.load(eo)
            with open(bmkRes) as ao:
                actual_output = json.load(ao)
                for key in actual_output.keys():
                    if key not in expected_output.keys():
                        print("Actual output error: Key \"" +
                              key + "\" not in expected output")
                        count += 1
                for key in expected_output.keys():
                    if key not in actual_output.keys():
                        print("Expected output error: Key \"" +
                              key + "\" not in actual output")
                        count += 1
        if count > 0:
            print("Test resulted in " + str(count) + " errors")

        self.assertEqual(count, 0, "Error count should be 0")


if __name__ == '__main__':
    unittest.main()
