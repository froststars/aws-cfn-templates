#!/usr/bin/env bash

set -e

USAGE="bootstrap.sh [PARENT_DIR] [YOUR_PROJECT_NAME]"

if [ $# -lt 2 ]; then
    echo $USAGE
    exit 1
fi;

ROOTDIR=$1/$2

mkdir -p $ROOTDIR/solutions/CfnCD/
mkdir -p $ROOTDIR/stacks/

cp SimpleCfnCd.template.yaml $ROOTDIR/solutions/CfnCD/
cp bootstrap/Main.template.yaml $ROOTDIR/solutions/
cp bootstrap/buildspec.yaml $ROOTDIR/
cp bootstrap/config.stag.json $ROOTDIR/
cp bootstrap/config.prod.json $ROOTDIR/
cp bootstrap/CfnCd.config.yaml $ROOTDIR/stacks

echo "# CloudFormation Continuous Delivery with AWS CodePipeline - $2" > ${ROOTDIR}/README.md

