#!/bin/bash

# Copyright 2019-2021 CERN. See the COPYRIGHT file at the top-level directory
# of this distribution. For licensing information, see the COPYING file at
# the top-level directory of this distribution.

BASEDIR=$(readlink -f $(dirname $0))

cd $BASEDIR/../..
echo "[run_bat_tests] Install hepscore"
yum -y install python3 python3-pip
pip3 install .

for afile in `ls $BASEDIR/*bat`;
do
    echo -e "\n[run_bat_tests] Running tests in $afile"
    bats $afile
    [[ "$?" != "0" ]] && exit 1
done

exit 0
