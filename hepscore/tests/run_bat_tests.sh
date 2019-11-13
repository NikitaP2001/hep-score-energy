#!/bin/bash

BASEDIR=$(readlink -f $(dirname $0))

cd $BASEDIR/../..
echo "[run_bat_tests] Install hepscore"
pip install .


for afile in `ls $BASEDIR/*bat`;
do
    echo -e "\n[run_bat_tests] Running tests in $afile"
    bats $afile
    [[ "$?" != "0" ]] && exit 1
done



