#!/usr/bin/env python3
"""
HEPSCORE

Module `hepscore` provides orchestration of containerized HEP workloads
and generation of JSON or YAML summary of the resulting reported scores.

For further information on configuring `hepscore`, see the full
documentation on [gitlab](https://gitlab.cern.ch/hep-benchmarks/hep-score)

Compatibility
-------------
`hepscore` requires Python 3.6 or later, and one of the following:
* Singularity 3.5.3+
* Docker 19.03+

Contributing
------------
`hepscore` [is on  CERN GitLab](https://gitlab.cern.ch/hep-benchmarks/hep-score).
Merge requests and bug reports are welcome.
You can also seek support by contacting benchmark-suite-wg-devel@cern.ch

Copyright
------------
Copyright 2019-2021 CERN. See the COPYRIGHT file at the top-level directory
of this distribution. For licensing information, see the COPYING file at
the top-level directory of this distribution.

"""

from pbr.version import VersionInfo
__all__ = ('__version__',)
__version__ = VersionInfo('hep-score').release_string()
