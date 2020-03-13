#!/usr/bin/python
###############################################################################
#
# main.py - HEPscore benchmark execution CLI tool
#

import getopt
from hepscore import HEPscore
import os
import sys


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
    print("-C           Remove excessive files and tar BMK results")
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

    hsargs = {'outdir': ""}
    replay = False
    printconf_and_exit = False
    outtype = "json"
    conffile = ""
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
            hsargs['clean_files'] = False
        elif opt == '-s' or opt == '-d':
            if 'cec' in hsargs:
                print("\nError: -s and -d are exclusive\n")
                sys.exit(1)
            if opt == '-s':
                hsargs['cec'] = "singularity"
            else:
                hsargs['cec'] = "docker"

    if len(args) < 1 and not printconf_and_exit:
        help(sys.argv[0])
        sys.exit(1)
    elif len(args) >= 1:
        if replay:
            hsargs['resultsdir'] = args[0]
        else:
            hsargs['outdir'] = args[0]

        if not os.path.isdir(args[0]):
            print("\nError: output directory must exist")
            sys.exit(1)

    hs = HEPscore(**hsargs)
    hs.read_and_parse_conf(conffile)

    if printconf_and_exit:
        hs.print_conf()
        sys.exit(0)
    else:
        if hs.run(replay) >= 0:
            hs.gen_score()
        hs.write_output(outtype, outfile)


if __name__ == '__main__':
    main()
