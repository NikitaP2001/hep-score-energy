# __init__.py

# Copyright 2019-2020 CERN. See the COPYRIGHT file at the top-level directory
# of this distribution. For licensing information, see the COPYING file at
# the top-level directory of this distribution.

from pbr.version import VersionInfo
__all__ = ('__version__',)
__version__ = VersionInfo('hep-score').release_string()
