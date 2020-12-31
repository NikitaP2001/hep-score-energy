#!/usr/bin/env bats

[ -z "$CI_JOB_ID" ] && CI_JOB_ID="ci_job_id"
[ -z "$CI_PROJECT_DIR" ] && CI_PROJECT_DIR=`pwd`


export TESTDIR=$BATS_TEST_DIRNAME
export HEPSCORECONF=${TESTDIR}/etc/hepscore_conf_ci.yaml
export WLDIR=$TESTDIR/data/HEPscore_ci/

@test "Test YAML configuration dump" {
    echo  ${HEPSCORECONF} $WDIR
    run hep-score -p -f ${HEPSCORECONF} 
    echo -e "$output"
    [ "$status" -eq 0 ]
}


@test "Test parsing of existing atlas-kv-bmk results" {
    run hep-score -r -f $HEPSCORECONF $WLDIR
    echo -e "$output"
    [ "$status" -eq 0 ]

}


function run_atlas-kv-bmk {
	 export WDIR=/tmp/HEPSCORE/$CI_JOB_ID
	 if [ ! -e $WDIR ]; then	
   	    mkdir -p $WDIR
	 fi
	 hep-score -v -d -f $TESTDIR/etc/hepscore_conf_ci.yaml $WDIR
}

@test "Test run of hep-score with configuration for atlas-kv-bmk" {
    run run_atlas-kv-bmk
    echo -e "$output"
    [ "$status" -eq 0 ]
}
