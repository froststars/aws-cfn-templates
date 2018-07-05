import boto3
import json

rds = boto3.client('rds')

paginator = rds.get_paginator('describe_db_engine_versions')

engines = set()
versions = set()
parameter_groups = set()

for i in paginator.paginate():

    for v in i['DBEngineVersions']:
        engines.add(v['Engine'])
        versions.add('-'.join([v['Engine'], v['EngineVersion']]))
        parameter_groups.add(v['DBParameterGroupFamily'])

    with open('rds-versions.json', 'w') as fp:
        json.dump(sorted(versions), fp, indent=2)
    with open('rds-engines.json', 'w') as fp:
        json.dump(sorted(engines), fp, indent=2)
    with open('rds-parameter-groups.json', 'w') as fp:
        json.dump(sorted(parameter_groups), fp, indent=2)
