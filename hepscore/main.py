###############################################################################
# Copyright 2019-2020 CERN. See the COPYRIGHT file at the top-level directory
# of this distribution. For licensing information, see the COPYING file at
# the top-level directory of this distribution.
###############################################################################
#
# main.py - HEPscore benchmark execution CLI tool
#

import getopt
import logging
import os
import sys
import time
import oyaml as yaml
import hepscore

logger = logging.getLogger()
logging.basicConfig(format='%(asctime)s, hepscore:%(funcName)s [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.WARNING)


def help(progname):

    namel = progname

    print(hepscore.HEPscore.NAME + " Benchmark Execution - Version " + hepscore.HEPscore.VER)
    print(namel + " [-s|-d] [-v] [-y] [-o OUTFILE] [-f CONF] OUTDIR")
    print(namel + " -h")
    print(namel + " -V")
    print(namel + " -p [-f CONF]")
    print("Option overview:")
    print("-h           Print help information and exit")
    print("-V           Print version and exit")
    print("-d           Run benchmark containers in Docker")
    print("-s           Run benchmark containers in Singularity")
    print("-S           Run benchmark containers in Singularity, forcing"
          " userns if supported")
    print("-r           Replay output using existing results directory")
    print("-f           Use specified YAML configuration file (instead of "
          "built-in)")
    print("-o           Specify an alternate summary output file location")
    print("-y           Specify output file should be YAML instead of JSON")
    print("-p           Print configuration and exit")
    print("-v           Enable verbose/debugging output")
    print("-c           Remove images after completion")
    print("-C           Clean workload scratch directories after execution")
    print("Examples:")
    print("Run the benchmark using Docker, displaying all component scores:")
    print(namel + " -dv /tmp/hs19")
    print("Run with Singularity, using a non-standard benchmark "
          "configuration:")
    print(namel + " -sf /tmp/hscore/hscore_custom.yaml /tmp/hscore\n")
    print("Additional information: https://gitlab.cern.ch/hep-benchmarks/hep-"
          "score")
    print("Questions/comments: benchmark-suite-wg-devel@cern.ch")


def main():

    logger.setLevel(logging.INFO)

    hsargs = {}
    replay = False
    printconf_and_exit = False
    outtype = "json"
    conffile = '/'.join(os.path.split(hepscore.__file__)[:-1]) + \
        "/etc/hepscore-default.yaml"
    outfile = ""
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hpvVcCdsSyrf:o:')
    except getopt.GetoptError as err:
        logger.error(err)
        help(sys.argv[0])
        sys.exit(1)

    for opt, arg in opts:
        if opt == '-h':
            help(sys.argv[0])
            sys.exit(0)
        if opt == '-p':
            printconf_and_exit = True
        if opt == '-V':
            if len(opts)==1:
                print(str(hepscore.HEPscore.VER))
                sys.exit(0)
            else:
                help(sys.argv[0])
                sys.exit(1)
        elif opt == '-v':
            logger.setLevel(logging.DEBUG)
        elif opt == '-f':
            conffile = arg
        elif opt == '-y':
            outtype = 'yaml'
        elif opt == '-o':
            outfile = arg
        elif opt == '-r':
            replay = True
        elif opt == '-c':
            hsargs['clean'] = True
        elif opt == '-C':
            hsargs['clean_files'] = True
        elif opt in ['-s', '-S', '-d']:
            if 'container_exec' in hsargs:
                logger.error("-s, -d and -S are exclusive")
                sys.exit(1)
            if opt == '-d':
                hsargs['container_exec'] = "docker"
            else:
                hsargs['container_exec'] = "singularity"
                if opt == '-S':
                    hsargs['userns'] = True

    goodlen = 1
    if printconf_and_exit:
        goodlen = 0
    if len(args) != goodlen:
        if not printconf_and_exit:
            logger.error("Must specify OUTDIR.\n")
        help(sys.argv[0])
        sys.exit(1)

    # Read config yaml
    try:
        with open(conffile, 'r') as yam:
            active_config = yaml.safe_load(yam)
    except Exception:
        logger.error("Cannot read/parse YAML configuration file %s", conffile)
        sys.exit(1)

    if printconf_and_exit:
        print(str(yaml.safe_dump(active_config)))
        sys.exit(0)

    # check passed dir
    if replay:
        if not os.path.isdir(args[0]):
            logger.error("Replay mode requires valid directory!")
            sys.exit(1)
        else:
            resultsdir = args[0]
    else:
        resultsdir = os.path.join(
            args[0],
            hepscore.HEPscore.NAME + '_' + time.strftime("%d%b%Y_%H%M%S"))
        try:
            os.makedirs(resultsdir)
        except Exception:
            logger.exception("Failed to create output directory %s. Do you have permissions?",
                             resultsdir)
            sys.exit(1)

    if 'container_exec' in hsargs:
        active_config['hepscore_benchmark']['settings']['container_exec'] \
            = hsargs['container_exec']
        hsargs.pop('container_exec', None)

    if 'options' not in active_config['hepscore_benchmark']:
        active_config['hepscore_benchmark']['options'] = {}

    # Populate active config with cli override
    for k, v in hsargs.items():
        if v != "":
            active_config['hepscore_benchmark']['options'][k] = v

    hs = hepscore.HEPscore(active_config, resultsdir)

    if hs.run(replay) >= 0:
        hs.gen_score()
    hs.write_output(outtype, outfile)


if __name__ == '__main__':
    main()
