#!/usr/bin/env python3

import setuptools
import os

os.environ['SKIP_WRITE_GIT_CHANGELOG'] = "1"
os.environ['SKIP_GENERATE_AUTHORS'] = "1"

setuptools.setup(
    setup_requires=['pbr'],
    pbr=True
    )
