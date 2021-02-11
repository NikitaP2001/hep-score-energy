# HEPscore

## Table of Contents

1. [About](#about)  
2. [HEPscore20 Benchmark](#hepscore20-benchmark)  
3. [Downloading and Installing HEPscore](#downloading-and-installing-hepscore)  
4. [Dependencies](#dependencies)  
5. [Configuring HEPscore](#configuring-hepscore)  
    1. [Parameters](#parameters)  

## About

The HEPscore application orchestrates the execution of user-configurable
benchmark suites based on individual benchmark containers.  It runs the
specified benchmark containers in sequence, collects their results, and
computes a final overall score.  HEPscore is specifically designed for
use with containers from the [HEP Workloads project](
https://gitlab.cern.ch/hep-benchmarks/hep-workloads).
However, any benchmark containers stored in a Docker/Singularity
registry, or filesystem directory, which conform to the HEP Workloads'
naming conventions and output JSON schema, are potentially usable.
Both Singularity and Docker are supported for container execution.  By
default, if no configuration is passed to HEPscore, the "HEPscore20"
benchmark is run.

## HEPscore20 Benchmark

HEPscore20 is a benchmark based on containerized HEP workloads that
the HEPiX Benchmarking Working Group is targeting to eventually replace
HEPSPEC06 as the standard HEPiX/WLCG benchmark.  It is currently in a beta
development state, and consists of the following workloads from the
[HEP Workloads project](
https://gitlab.cern.ch/hep-benchmarks/hep-workloads):  
atlas-gen-bmk
atlas-sim-bmk
cms-gen-sim-bmk  
cms-digi-bmk  
cms-reco-bmk  
lhcb-gen-sim-bmk  
You can view the YAML HEPscore configuration for HEPscore20 by
executing ```hep-score -p```.

The benchmark will take 5+ hours to execute on modern hardware.

**NOTE**: ~20 GB of free disk space in your Singularity or Docker
cache area, and 320 MB/core of free space (e.g. 20 GB on 64 core host)
in the specified OUTDIR output directory is necessary to run the
HEPscore20 benchmark.  

If you are running low on space in your Singularity cache area (typically
located in ~/.singularity/cache), you can specify an alternate cache
location by setting the Singularity SINGULARITY_CACHEDIR environment
variable appropriately (see the Singularity documentation for
further information).

It is also possible to run the benchmark containers out of the
"unpacked.cern.ch" CVMFS repo instead of the CERN gitlab Docker registry,
by passing ```hep-score``` the
[hepscore-cvmfs.yaml](https://gitlab.cern.ch/hep-benchmarks/hep-score/-/raw/master/hepscore/etc/hepscore-cvmfs.yaml)
file shipped in the application's etc/ directory.  When running the
benchmark using the unpacked images in CVMFS, the Singularity cache area
is not utilized.

## Downloading  and Installing HEPscore

HEPscore must be installed using pip (<https://pypi.org/project/pip/>).  

To install as a regular user (suggested):  
```$ pip install --user git+https://gitlab.cern.ch/hep-benchmarks/hep-score.git```  
The ```hep-score``` script will then be accessible under ```~/.local/bin```.  

If you have administrator rights on your system and would like to install
hep-score and all dependencies in system Python/bin paths:  
```# pip install git+https://gitlab.cern.ch/hep-benchmarks/hep-score.git```

Alternatively, you can clone the hep-score git repository, and run the pip
installation out of the root directory of the repo:

```sh
$ git clone https://gitlab.cern.ch/hep-benchmarks/hep-score.git
$ cd hep-score
$ pip install --user .
```

**NOTE**: on RHEL/CentOS/Scientific Linux 7 hosts, where python 3 is not
the default python installation, it may be necessary to use ```pip3``` to
install instead of ```pip```.

## Dependencies

HEPscore requires a **Python 3.6+** installation.  The pip installation will pull
in all dependencies.  HEPscore should be used with **Singularity 3.5.3 and newer**, or
**Docker 1.13 and newer**.  There are some known issues when using HEPscore
with earlier Singularity and Docker releases.

## Running HEPscore

```sh
usage: hep-score [-h] [-m [{singularity,docker}]] [-S] [-c] [-C]
                 [-f [CONFFILE]] [-r] [-o [OUTFILE]] [-y] [-p] [-V] [-v]
                 [OUTDIR]

positional arguments:
  OUTDIR                Base output directory.

optional arguments:
  -h, --help            show this help message and exit
  -m [{singularity,docker}], --container_exec [{singularity,docker}]
                        specify container platform for benchmark execution
                        (singularity [default], or docker).
  -S, --userns          enable user namespace for Singularity, if supported.
  -c, --clean           clean residual container images from system after run.
  -C, --clean_files     clean residual files & directories after execution.
                        Tar results.
  -f [CONFFILE], --conffile [CONFFILE]
                        custom config yaml to use instead of default.
  -r, --replay          replay output using existing results directory OUTDIR.
  -o [OUTFILE], --outfile [OUTFILE]
                        specify custom output filename. Default:
                        HEPscore20.json.
  -y, --yaml            YAML output instead of JSON.
  -p, --print           print configuration and exit.
  -V, --version         show program version number and exit
  -v, --verbose         enables verbose mode. Display debug messages.


Examples:
Run benchmarks via Docker, and display verbose information:
$ hep-score -v -m docker /tmp/rundir

Run using Singularity (default) with a custom benchmark configuration:
$ hep-score -f /tmp/my-custom-bmk.yml /tmp/hsresults
```

Singularity will be used as the container engine for the run, unless Docker
is specified on the hep-score commmandline (```-m docker```), or in the
benchmark configuration.

hep-score creates a HEPscore_DATE_TIME named directory under OUTDIR which
is used as the working directory for the sub-benchmark containers.  A detailed
log of the run of the application is also written to this directory:
BENCHMARK_NAME.log, where BENCHMARK_NAME is taken from the "name" parameter in
the YAML configuration ("HEPscore20.log" by default).

The final computed score will be printed to stdout ("Final score: XYZ"), and
also stored in a summary output JSON (or YAML, if ```-y``` is specified) file
under OUTDIR (unless an alternative location is specified with ```-o```).  This
file also contains all of the summary JSON output data from each sub-benchmark.

## Configuring HEPscore

An example hepscore YAML configuration is below:

```yaml
hepscore_benchmark:
  benchmarks:
    cms-reco-bmk:
      ref_scores:
        reco: 2.196
      version: v1.2
      args:
        # threads
        -t: 4
        # events
        -e: 50
      weight: 3.0
    lhcb-gen-sim-bmk:
      ref_scores:
        gen-sim: 90.29
      version: v0.15
      args:
        # threads
        -t: 1
        # events
        -e: 5
      weight: 1.0
  app_info:
    name: TestBenchmark
    reference_machine: "CPU Intel(R) Xeon(R) CPU E5-2630 v3 @ 2.40GHz"
    registry: docker://gitlab-registry.cern.ch/hep-benchmarks/hep-workloads
  settings:
    method: geometric_mean
    repetitions: 3
    scaling: 355
    container_exec: singularity
```

All configuration parameters must be under the "hepscore_benchmark" key.

### Parameters

#### benchmarks (required)

DICTIONARY  
Specifies a list of benchmark containers to run, with associated settings:
see below

##### BENCHMARK_NAME (required)

DICTIONARY; where BENCHMARK_NAME is variable  
BENCHMARK_NAME denotes the name of the benchmark container to run.  See
per-benchmark settings below

###### ref_scores (required)

DICTIONARY  
List of sub-scores to collect from the benchmark container output
JSON, with reference scores from the specified "reference_machine".  Each
sub-score is divided by its reference score, and the geometric mean is
taken from the results to compute a final score for the benchmark
container

###### version (required)

STRING  
The version of the benchmark container to execute

###### args

DICTIONARY; default set by container  
Set options to pass to the benchmark container.  Typically, ```-e``` to
set events, ```-t``` for threads, ```-c``` for copies, and ```-d``` for
debug

###### weight

FLOAT; default 1.0  
Sets the weight for the benchmark container when calculating the overall
score

###### registry

STRING; defaults to the primary registry specified in "app_info"  
Allows for overriding the registry to use for this container.  See
"registry", under "app_info" below, for more information

#### app_info (required)

DICTIONARY  
Defines overall benchmark application information below  

##### name (required)

STRING  
The name of the overall benchmark/configuration

##### reference_machine (required)

STRING  
Specifies host/configuration where the benchmark container scores have
been normalized to 1.0.  All reported scores are then relative to the
performance of this host

##### registry (required)

STRING  
The registry to run containers from.  Multiple URIs are permitted:
```docker://``` to specify a Docker registry, ```dir://``` (Singularity
only) to specify a local directory containing unpacked images or image
files, or ```shub://``` (Singularity only) to specify a Singularity
registry

#### settings (required)

DICTIONARY  
Defines various settings for the overall benchmark application  

##### method (required)

STRING  
The method for combining the sub-benchmark scores into a single score.
Currently only "geometric_mean" is supported.  This is actually a
weighted geometric mean, with weights taken from 'weight' configuration
parameter for each benchmark.

##### repetitions (required)

INTEGER  
The number of times each benchmark container should be run.  If the
number of runs is greater than one, the median of that container's
resulting scores is used

###### scaling  

FLOAT; default = 1.0  
The multi-benchmark score calculated via the "method" parameter is
multiplied by this value to compute the final score

##### container_exec

STRING; defaullt = "singularity"  
Allows one to specify the default container execution platform:
"singularity" and "docker" are supported.  This can be overridden on the
commandline

##### retries

INTEGER; default = 0
Specifies how many times to retry a given workload if it fails.

##### continue_fail

BOOL; default = false  
Defines whether hep-score should continue attempting to run other
sub-benchmarks, if a sub-benchmark fails and does not produce a
resulting score.  If true, and this condition occurs, an overall/final
score will *not* be reported by the application, but runs of other
sub-benchmarks will continue.  This parameter is primarily useful for
testing and debugging purposes

|     |     |     |
| --- | --- | --- |
| **qa-v1.0**     |  [![pipeline status](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/qa-v1.0/pipeline.svg)](https://gitlab.cern.ch/hep-benchmarks/hep-score/commits/qa-v1.0)     | ![code quality](https://gitlab.cern.ch/hep-benchmarks/hep-score/-/jobs/artifacts/qa-v1.0/raw/public/badges/pep8.svg?job=pep8) |
