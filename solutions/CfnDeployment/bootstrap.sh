#!/usr/bin/env bash

set -e

USAGE="bootstrap.sh [YOUR_PROJECT_NAME]"

if [ $# -lt 1 ]; then
    echo $USAGE
    exit 1
fi;


mkdir $1
mkdir -p $1/solutions/
mkdir -p $1/solutions/CICD/
mkdir -p $1/stacks/

cp CfnCodePipeline.template.yaml $1/solutions/CICD/
cp Main.template.yaml $1/solutions/
cp CICD.yaml $1/stacks/
cp buildspec.yaml $1/


echo "Code Pipeline for $1" >> $1/README.md
echo "{\"Parameters\":{}}" >> $1/config.test.json
echo "{\"Parameters\":{}}" >> $1/config.prod.json

