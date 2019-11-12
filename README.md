# HEPscore 

The HEPscore application orchestrates the execution of user-configurable
benchmark suites based on individual benchmark containers.  It runs the
specified individual benchmark containers in sequence, collects their 
results, and computes a final overall score.  HEPscore is specifically 
designed for use with containers from the [HEP Workloads project](
https://gitlab.cern.ch/hep-benchmarks/hep-workloads).
However, any benchmark containers stored in a Docker registry which
conform to the HEP Workloads' naming conventions and output JSON schema,
are potentially usable.  Both Docker and Singularity are supported for 
container execution.  By default, if no configuration is passed to HEPscore, 
the "HEPscore19" benchmark is run.

## HEPscore19 Benchmark
HEPscore19 is a benchmark based on containerized HEP workloads that 
the HEPiX Benchmarking Working Group is targeting to eventually replace 
HEPSPEC06 as the standard HEPiX/WLCG benchmark.  It is currently in a beta 
development state, and consists of the following workloads:  
atlas-gen-bmk  
atlas-sim-bmk  
cms-gen-sim-bmk  
cms-digi-bmk  
cms-reco-bmk  
lhcb-gen-sim-bmk  
You can view the YAML HEPscore configuration for HEPscore19 by
executing ```hepscore.py -p```.

## Downloading HEPscore
Using a curl, wget or browser:  
https://gitlab.cern.ch/hep-benchmarks/hep-score/raw/master/hepscore/hepscore.py?inline=false

or

Clone the entire project:  
```git clone https://gitlab.cern.ch/hep-benchmarks/hep-score.git```  
The "hepscore.py" script is then available under the "hepscore" directory.  If
you optionally run ```pip install .``` in the root of the project, the entire
module will be installed as ```hep-score```.

## Installing Dependencies
HEPscore currently only functions with Python 2 (Python 3 support
is in development).  The following non-standard library modules must a
also be installed/available:  PyYAML  
If you clone the git repository, it's possible to install the dependencies
by changing your working directory to the root of the project, and running: 
```pip install .```

## Running HEPscore
```hepscore.py [-s|-d] [-v] [-V] [-y] [-o OUTFILE] [-f CONF] OUTDIR
hepscore.py -h
hepscore.py -p [-f CONF]
Option overview:
-h           Print help information and exit
-v           Display verbose output, including all component benchmark scores
-d           Run benchmark containers in Docker
-s           Run benchmark containers in Singularity
-f           Use specified YAML configuration file (instead of built-in)
-o           Specify an alternate summary output file location
-y           Specify output file should be YAML instead of JSON
-p           Print configuration and exit
-V           Enable debugging output: implies -v
Examples:
Run the builtin benchmark using Docker, displaying all component scores:
hepscore.py -v /tmp/hs19
Run with Singularity, using a non-standard benchmark configuration:
hepscore.py -sf /tmp/hscore/hscore_custom.yaml /tmp/hscore
```

hepscore.py creates a HEPscore_DATE_TIME named directory under OUTDIR which 
is used as the working directory for the sub-benchmark containers.  A detailed 
log of the run of the application is also written to this directory: 
BENCHMARK_NAME.log, where BENCHMARK_NAME is taken from the "name" parameter in 
the YAML configuration ("HEPscore19.log" by default).   

The final computed score will be printed to stdout ("Final score: XYZ"), and 
also stored in a summary output JSON (or YAML, if ```-y``` is specified) file 
under OUTDIR.  This file also contains all of the summary JSON output data from
each sub-benchmark.

## Configuring HEPscore
An example hepscore YAML configuration is below:
```
hepscore_benchmark:
  benchmarks:
    atlas-kv-bmk:
      ref_scores: {sim: 1.139}
      scorekey: wl-scores
      version: ci1.1
      events: 2
      threads: 1
      debug: true
    cms-reco-bmk:
      ref_scores: {reco: 0.1625}
      scorekey: wl-scores
      version: v1.0
  method: geometric_mean
  name: HEPscoreTEST1
  reference_machine: Intel Core i5-4590 @ 3.30GHz - 1 Logical Core
  registry: gitlab-registry.cern.ch/hep-benchmarks/hep-workloads
  repetitions: 3
  scaling: 10
  version: 0.31
```

All configuration parameters must be under the "hepscore_benchmark" key.

### Parameters:
#### benchmarks (required)
DICTIONARY  
List of benchmark containers to run, with associated settings: see below
##### ref_scores (required)
DICTIONARY  
List of sub-scores to collect from the benchmark container output 
JSON, with reference scores from the specified "reference_machine".  Each
sub-score is divided by its reference score, and the geometric mean is 
taken of the results to compute a final score for the benchmark
container
##### scorekey (required)
STRING  
Indicate the JSON key used to hold the benchmark container score.  This
should generally be "wl-scores"
##### version (required)
STRING
The version of the benchmark container in the Docker registry to execute
##### events
INTEGER ; default set by container  
Set the number of events to process
##### threads
INTEGER ; default set by container - saturates host  
Set the number of threads that the benchmark container will execute
##### copies
INTEGER; default set by container - saturates host  
##### debug
BOOL ; default = false  
Enable debugging output for the benchmark container
#### name (required)
STRING  
The name of the overall benchmark/configuration
#### method (required)
STRING  
The method for combining the sub-benchmark scores into a single score.
Currently only "geometric_mean" is supported.
#### reference_machine (required)
STRING  
An test host/configuration where the benchmark container scores have been 
set to 1.  All reported scores are then relative to the performance of
this host.
#### registry (required)
STRING  
The Docker registry to pull images from
#### repetitions (required)
INTEGER  
The number of times each benchmark container should be run.  If the
number of runs is greater than one, the median of that container's 
resulting scores is used.
#### version (required)
FLOAT  
The version of the overal benchmark/configuration
#### scaling
FLOAT; default = 1.0  
The multi-benchmark score calculated via the "method" parameter is then 
multiplied by this value to compute the final score
#### container_exec
STRING; defaullt = "docker"  
Allows one to specify the default container execution platform: currently
"singularity" or "docker" are supported.  This can be overidden on the
commandline.
#### allow_fail
BOOL; default = false  
If multiple runs of a benchmark are requested via the "repetitions" parameter,
allow failures as long as one run complete.  Normally, a single run failure
will fail the entire benchmark, and no score will be reported.

|     |     |     |
| --- | --- | --- |
| **master**     |   [![pipeline status](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/master/pipeline.svg)](https://gitlab.cern.ch/hep-benchmarks/hep-score/commits/master)     | ![coverage](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/master/coverage.svg?job=coverage) |
| **qa**     |  [![pipeline status](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/qa/pipeline.svg)](https://gitlab.cern.ch/hep-benchmarks/hep-score/commits/qa)     |  ![coverage](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/qa/coverage.svg?job=coverage) |

