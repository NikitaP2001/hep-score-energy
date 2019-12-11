from hepscore import hepscore
import numpy as np
import os
# from parameterized import parameterized
from scipy import stats
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
