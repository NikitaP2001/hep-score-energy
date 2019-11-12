#!/bin/bash

BASEDIR=$(readlink -f $(dirname $0))

# This script installs hepscore and runs the mock_hepscore test script
# in order to verify that the produced json is compatible with the ref json
yum install -y yum-plugin-ovl 

echo "[run_bat_tests] Install hepscore"
pip install .


for afile in `ls $BASEDIR/*bat`;
do
    echo -e "\n[run_bat_tests] Running tests in $afile"
    bats $afile
    [[ "$?" != "0" ]] && exit 1
done



