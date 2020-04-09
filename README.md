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

## Downloading  and Installing HEPscore
HEPscore must be installed using pip (https://pypi.org/project/pip/).  

If you want to install as a regular user (suggested):
```# pip install --user git+https://gitlab.cern.ch/hep-benchmarks/hep-score.git@qa-v1.0```
If you have administrator rights on your system and what to install hep-score and all depencies in system Python/bin paths:
```# pip install git+https://gitlab.cern.ch/hep-benchmarks/hep-score.git@qa-v1.0```
The ```hep-score``` script will then be acessible under ```~/.local/bin```.  Alternatively, you can clone the hep-score git repository, and run ```pip install --user .``` or ```pip install .``` in the root of the repo.

## Dependencies
HEPscore currently only functions with Python 2.7 and Python 3.  The pip installation will pull in all dependencies

## Running HEPscore
```
HEPscore Benchmark Execution - Version 1.0.0
hep-score [-s|-d] [-v] [-V] [-y] [-o OUTFILE] [-f CONF] OUTDIR
hep-score -h
hep-score -p [-f CONF]
Option overview:
-h           Print help information and exit
-v           Display verbose output, including all component benchmark scores
-d           Run benchmark containers in Docker
-s           Run benchmark containers in Singularity
-r           Replay output using existing results directory
-f           Use specified YAML configuration file (instead of built-in)
-o           Specify an alternate summary output file location
-y           Specify output file should be YAML instead of JSON
-p           Print configuration and exit
-V           Enable debugging output: implies -v
-c           Remove the docker image after completion
-C           Disable removing excessive files and tar BMK results
Examples:
Run the benchmark using Docker, dispaying all component scores:
hep-score -dv /tmp/hs19
Run with Singularity, using a non-standard benchmark configuration:
hep-score -sf /tmp/hscore/hscore_custom.yaml /tmp/hscore
```

hep-score creates a HEPscore_DATE_TIME named directory under OUTDIR which 
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
The number of copies of the benchmark to run
##### debug
BOOL ; default = false  
Enable debugging output for the benchmark container
#### name (required)
STRING  
The name of the overall benchmark/configuration
#### method (required)
STRING  
The method for combining the sub-benchmark scores into a single score.
Currently only "geometric_mean" is supported
#### reference_machine (required)
STRING  
An test host/configuration where the benchmark container scores have been 
set to 1.  All reported scores are then relative to the performance of
this host
#### registry (required)
STRING  
The Docker registry to pull images from
#### repetitions (required)
INTEGER  
The number of times each benchmark container should be run.  If the
number of runs is greater than one, the median of that container's 
resulting scores is used
#### version (required)
FLOAT  
The version of the overall benchmark/configuration
#### scaling
FLOAT; default = 1.0  
The multi-benchmark score calculated via the "method" parameter is then 
multiplied by this value to compute the final score
#### container_exec
STRING; defaullt = "docker"  
Allows one to specify the default container execution platform: currently
"singularity" or "docker" are supported.  This can be overidden on the
commandline
#### allow_fail
BOOL; default = false  
If multiple runs of a benchmark are requested via the "repetitions" parameter,
allow failures as long as one run complete.  Normally, a single run failure
will fail the entire benchmark, and no score will be reported

|     |     |     |
| --- | --- | --- |
| **master**     |   [![pipeline status](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/master/pipeline.svg)](https://gitlab.cern.ch/hep-benchmarks/hep-score/commits/master)     | ![coverage](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/master/coverage.svg?job=coverage) |
| **qa**     |  [![pipeline status](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/qa/pipeline.svg)](https://gitlab.cern.ch/hep-benchmarks/hep-score/commits/qa)     |  ![coverage](https://gitlab.cern.ch/hep-benchmarks/hep-score/badges/qa/coverage.svg?job=coverage) |

