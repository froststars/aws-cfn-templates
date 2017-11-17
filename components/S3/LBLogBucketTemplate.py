# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '22/12/2016'

from troposphere import Retain, AWS_REGION, AWS_ACCOUNT_ID, AWS_NO_VALUE
from troposphere import Parameter, Sub, Export, Equals, Not, Join, Condition
from troposphere import Template, Ref, Output, FindInMap, If, GetAtt

import troposphere.s3 as s3

import cfnutil

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'Loadbalancer log bucket'
)

#
# Parameters
#
param_bucket_name = t.add_parameter(Parameter(
    'BucketName',
    Description='Bucket name',
    Default='',
    Type='String',
    AllowedPattern=r'[-\.a-z0-9]*',
))

#
# Condition
#
t.add_condition(
    'HasBucketName',
    Not(Equals(Ref(param_bucket_name), ''))
)

t.add_condition(
    'ChinaRegionCondition',
    Equals(Ref(AWS_REGION), 'cn-north-1')
)
#
# Mapping
#
t.add_mapping(
    'ElbAccountId',
    cfnutil.load_csv_as_mapping('mapping/elb-account-id.csv',
                                'Region', 'ID',
                                'Elastic Load Balancing Account ID')
)

#
# Resource
#
bucket = t.add_resource(s3.Bucket(
    'Bucket',
    BucketName=If(
        'HasBucketName',
        Ref(param_bucket_name),
        Ref(AWS_NO_VALUE)),
))

bucket_policy = t.add_resource(s3.BucketPolicy(
    'BucketPolicy',
    Bucket=Ref(bucket),
    PolicyDocument={
        'Id': '1',
        'Version': '2012-10-17',
        'Statement': [
            {
                'Sid': '1',
                'Action': [
                    's3:PutObject'
                ],
                'Effect': 'Allow',
                'Resource': Sub(
                    'arn:${PARTITION}:s3:::${BUCKET}/*',
                    PARTITION=If('ChinaRegionCondition', 'aws-cn', 'aws'),
                    BUCKET=Ref(bucket),
                ),
                'Principal': {
                    'AWS': [
                        FindInMap('ElbAccountId', Ref(AWS_REGION), 'ID')
                    ]
                }
            }
        ]
    }
))

#
# Output
#
t.add_output([
    Output(
        'BucketName',
        Description='Bucket name',
        Value=Ref(bucket),
    ),
    Output(
        'BucketArn',
        Description='Amazon Resource Name the bucket',
        Value=GetAtt(bucket, 'Arn'),
    ),
])
#
# Write
#

cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
