from hepscore import hepscore
from hepscore import hepscorev2
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


class TestHepScore(unittest.TestCase):

    def test_geometric_mean(self):

        vinput = [1, 2, 3]
        gm = np.round(hepscore.geometric_mean(vinput), 3)
        self.assertEqual(gm,
                         np.round(stats.mstats.gmean(vinput), 3))


class TestConf(unittest.TestCase):

    def setUp(self):
        head, _ = os.path.split(__file__)
        self.path = os.path.normpath(
            os.path.join(head, 'etc/hepscore_conf.yaml'))

    def test_fail_read_conf(self):
        with self.assertRaises(SystemExit) as cm:
            hepscore.read_conf('does_not_exist_file')
            self.assertEqual(cm.exception.code, 1)

    def test_succeed_read_conf(self):
        hepscore.read_conf(self.path)
        with open(self.path) as f:
            test_conf = f.read()
        self.assertEqual(hepscore.get_conf(), test_conf)


class Test_bmk_options(unittest.TestCase):

    def test_bmk_option_good(self):
        conf = {'debug': True, 'copies': 4,
                'events': 3, 'threads': 2,
                'something_else': 123}
        self.assertEqual(
            hepscorev2.check_bmk_options(conf, 1), ' -c 4 -d -e 3 -t 2')

    def test_bmk_option_no_int_value(self):
        conf = {'debug': True, 'copies': 4,
                'events': 3, 'threads': 2.1,
                'something_else': 123}
        self.assertEqual(
            hepscorev2.check_bmk_options(conf, 1), ' -c 4 -d -e 3')

    def test_bmk_option_debug_false(self):
        conf = {'debug': False, 'copies': 4,
                'events': 3, 'threads': 2.1,
                'something_else': 123}
        self.assertEqual(
            hepscorev2.check_bmk_options(conf, 1), ' -c 4 -e 3')

    def test_bmk_option_debug_missing(self):
        conf = {'copies': 4,
                'events': 3, 'threads': 2.1,
                'something_else': 123}
        self.assertEqual(
            hepscorev2.check_bmk_options(conf, 1), ' -c 4 -e 3')

    def test_bmk_option_value_none(self):
        conf = {'debug': False, 'copies': None,
                'events': 3, 'threads': 2.1,
                'something_else': 123}
        self.assertEqual(
            hepscorev2.check_bmk_options(conf, 1), ' -e 3')
