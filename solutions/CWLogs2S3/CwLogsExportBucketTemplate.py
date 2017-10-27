# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '05/06/2017'

from troposphere import Retain, AWS_REGION, AWS_ACCOUNT_ID, AWS_NO_VALUE
from troposphere import Parameter, Sub, Export, Equals, Not, Join, Condition
from troposphere import Template, Ref, Output, FindInMap, If

import troposphere.s3 as s3

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'CloudWatch Logs S3 export bucket'
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
    LifecycleConfiguration=s3.LifecycleConfiguration(Rules=[
        # Add a rule to
        s3.LifecycleRule(
            # Rule attributes
            Id='S3BucketRule1',
            Prefix='',
            Status='Enabled',
            # Applies to current objects
            # ExpirationInDays=3650,
            Transitions=[
                s3.LifecycleRuleTransition(
                    StorageClass='STANDARD_IA',
                    TransitionInDays=365,
                ),
            ],
            # Applies to Non Current objects
            NoncurrentVersionExpirationInDays=365,
            NoncurrentVersionTransitions=[
                s3.NoncurrentVersionTransition(
                    StorageClass='STANDARD_IA',
                    TransitionInDays=30,
                ),
            ],
        ),
    ]),
))

bucket_policy = t.add_resource(s3.BucketPolicy(
    'BucketPolicy',
    Bucket=Ref(bucket),
    PolicyDocument={
        'Version': '2012-10-17',
        'Statement': [
            {
                'Action': 's3:GetBucketAcl',
                'Effect': 'Allow',
                'Resource': Join('', ['arn:aws:s3:::', Ref(bucket)]),
                'Principal': {
                    'Service': Sub('logs.${AWS::Region}.amazonaws.com')}
            },
            {
                'Action': 's3:PutObject',
                'Effect': 'Allow',
                'Resource': Join('',
                                 ['arn:aws:s3:::', Ref(bucket), '/*']),
                'Condition': {'StringEquals': {
                    's3:x-amz-acl': 'bucket-owner-full-control'}},
                'Principal': {
                    'Service': Sub('logs.${AWS::Region}.amazonaws.com')}
            },
        ]}
))

#
# Output
#
t.add_output([
    Output(
        'BucketName',
        Description='S3 bucket',
        Value=Ref(bucket),
        Export=Export(Sub('${AWS::StackName}-BucketName'))
    )
])

#
# Write
#

with open(__file__.replace('Template.py', '.template'), 'w') as f:
    f.write(t.to_json(indent=2))
