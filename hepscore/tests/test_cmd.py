import os
import sys
import unittest

from parameterized import parameterized
from hepscore import hepscore

import numpy as np
from scipy import stats

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
        gm = np.round(hepscore.geometric_mean(vinput),3)
        self.assertEqual(gm,
                         np.round(stats.mstats.gmean(vinput),3))
