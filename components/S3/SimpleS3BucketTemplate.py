# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '22/12/2016'

from troposphere import Retain, AWS_REGION, AWS_ACCOUNT_ID, AWS_NO_VALUE, GetAtt
from troposphere import Parameter, Sub, Export, Equals, Not, Join, Condition
from troposphere import Template, Ref, Output, FindInMap, If

import troposphere.s3 as s3

import cfnutil

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'S3 storage bucket'
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

#
# Output

#
t.add_output([
    Output(
        'BucketName',
        Description='Bucket name',
        Value=Ref(bucket),
        # Export=Export(Sub('${AWS::StackName}-BucketName'))
    ),
    Output(
        'BucketArn',
        Description='Amazon Resource Name the bucket',
        Value=GetAtt(bucket, 'Arn'),
        # Export=Export(Sub('${AWS::StackName}-BucketArn'))
    ),
    Output(
        'DomainName',
        Description='IPv4 DNS name of the bucket',
        Value=GetAtt(bucket, 'DomainName'),
        # Export=Export(Sub('${AWS::StackName}-DomainName'))
    ),
])

#
# Write
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
