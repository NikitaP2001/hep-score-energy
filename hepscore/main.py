#!/usr/bin/python
###############################################################################
# Copyright 2019-2020 CERN. See the COPYRIGHT file at the top-level directory
# of this distribution. For licensing information, see the COPYING file at
# the top-level directory of this distribution.
###############################################################################
#
# main.py - HEPscore benchmark execution CLI tool
#

import getopt
import hepscore
from hepscore import HEPscore
import os
import sys
import yaml


def help(progname):

    namel = progname

    print(HEPscore.NAME + " Benchmark Execution - Version " + HEPscore.VER)
    print(namel + " [-s|-d] [-v] [-V] [-y] [-o OUTFILE] [-f CONF] OUTDIR")
    print(namel + " -h")
    print(namel + " -p [-f CONF]")
    print("Option overview:")
    print("-h           Print help information and exit")
    print("-v           Display verbose output, including all component "
          "benchmark scores")
    print("-d           Run benchmark containers in Docker")
    print("-s           Run benchmark containers in Singularity")
    print("-r           Replay output using existing results directory")
    print("-f           Use specified YAML configuration file (instead of "
          "built-in)")
    print("-o           Specify an alternate summary output file location")
    print("-y           Specify output file should be YAML instead of JSON")
    print("-p           Print configuration and exit")
    print("-V           Enable debugging output: implies -v")
    print("-c           Remove the docker image after completion")
    print("-C           Tar up results and remove results directories")
    print("Examples:")
    print("Run the benchmark using Docker, dispaying all component scores:")
    print(namel + " -dv /tmp/hs19")
    print("Run with Singularity, using a non-standard benchmark "
          "configuration:")
    print(namel + " -sf /tmp/hscore/hscore_custom.yaml /tmp/hscore\n")
    print("Additional information: https://gitlab.cern.ch/hep-benchmarks/hep-"
          "score")
    print("Questions/comments: benchmark-suite-wg-devel@cern.ch")


def main():

    hsargs = {}
    replay = False
    printconf_and_exit = False
    outtype = "json"
    conffile = '/'.join(os.path.split(hepscore.__file__)[:-1]) + \
        "/etc/hepscore-default.yaml"
    outfile = ""

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hpvVcCdsyrf:o:')
    except getopt.GetoptError as err:
        print("\nError: " + str(err) + "\n")
        help(sys.argv[0])
        sys.exit(1)

    for opt, arg in opts:
        if opt == '-h':
            help(sys.argv[0])
            sys.exit(0)
        if opt == '-p':
            printconf_and_exit = True
        elif opt == '-v':
            hsargs['level'] = 'VERBOSE'
        elif opt == '-V':
            hsargs['level'] = 'DEBUG'
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
        elif opt == '-s' or opt == '-d':
            if 'container_exec' in hsargs:
                print("\nError: -s and -d are exclusive\n")
                sys.exit(1)
            if opt == '-s':
                hsargs['container_exec'] = "singularity"
            else:
                hsargs['container_exec'] = "docker"

    if len(args) < 1 and not printconf_and_exit:
        help(sys.argv[0])
        sys.exit(1)
    elif len(args) >= 1:
        if replay:
            if not os.path.isdir(args[0]):
                print("\nError: output directory must exist")
                sys.exit(1)
            hsargs['resultsdir'] = args[0]

        else:
            if not os.path.isdir(args[0]):
                os.makedirs(args[0])
                print("Creating output directory {}".format(args[0]))
            outdir = args[0]

    # Read config yaml
    try:
        with open(conffile, 'r') as yam:
            active_config = yaml.full_load(yam)
    except Exception:
        raise

    # Populate active config with cli override
    for k, v in hsargs.items():
        if v != "":
            active_config['hepscore_benchmark']['settings'][k] = v

    hs = HEPscore(active_config, outdir)

    if printconf_and_exit:
        yaml.safe_dump(hs.confobj)
        sys.exit(0)
    else:
        if hs.run(replay) >= 0:
            hs.gen_score()
        hs.write_output(outtype, outfile)


if __name__ == '__main__':
    main()
