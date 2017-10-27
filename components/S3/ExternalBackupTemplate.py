# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '09/06/2017'

from troposphere import Retain, AWS_REGION, AWS_ACCOUNT_ID, AWS_NO_VALUE
from troposphere import Parameter, Sub, Export, Equals, Not, Join, Condition
from troposphere import Template, Ref, Output, FindInMap, If, GetAtt

import troposphere.s3 as s3
import troposphere.iam as iam

# import cfnutil

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'External backup storage bucket with upload user'
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

param_versioning = t.add_parameter(Parameter(
    'Versioning',
    Description='The versioning state of an Amazon S3 bucket.',
    Default='Suspended',
    Type='String',
    AllowedValues=['Enabled', 'Suspended']
))

#
# Condition
#
t.add_condition(
    'HasBucketName',
    Not(Equals(Ref(param_bucket_name), ''))
)
t.add_condition(
    'IsChinaRegion',
    Equals(Ref(AWS_REGION), 'cn-north-1')
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
    VersioningConfiguration=s3.VersioningConfiguration(
        Status=Ref(param_versioning)
    ),
    LifecycleConfiguration=s3.LifecycleConfiguration(Rules=[
        s3.LifecycleRule(
            Id='S3BucketRule1',
            Prefix='',
            Status='Enabled',
            Transitions=[
                s3.LifecycleRuleTransition(
                    StorageClass='STANDARD_IA',
                    TransitionInDays=365,
                ),
            ],
            NoncurrentVersionExpirationInDays=90,
            NoncurrentVersionTransitions=[
                s3.NoncurrentVersionTransition(
                    StorageClass='STANDARD_IA',
                    TransitionInDays=30,
                ),
            ],
        ),
    ]
    )
))

user = t.add_resource(iam.User(
    'BackupUser',
    Policies=[
        iam.Policy(
            PolicyName='S3',
            PolicyDocument={
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Action': [
                            's3:ListAllMyBuckets'
                        ],
                        'Resource': Sub('arn:${PARTITION}:s3:::*',
                                        PARTITION=If('IsChinaRegion',
                                                     'aws-cn',
                                                     'aws'),
                                        BUCKET_NAME=Ref(bucket),
                                        ),
                    },
                    {
                        'Effect': 'Allow',
                        'Action': [
                            's3:ListBucket',
                            's3:ListBucketMultipartUploads',
                            's3:GetBucketLocation',
                        ],
                        'Resource': Sub('arn:${PARTITION}:s3:::${BUCKET_NAME}',
                                        PARTITION=If('IsChinaRegion', 'aws-cn',
                                                     'aws'),
                                        BUCKET_NAME=Ref(bucket),
                                        ),
                    },
                    {
                        'Effect': 'Allow',
                        'Action': [
                            's3:GetObject',
                            's3:PutObject',
                            's3:DeleteObject',
                            's3:ListMultipartUploadParts',
                            # 's3:CreateMultipartUpload',
                            's3:AbortMultipartUpload',
                        ],
                        'Resource': Sub(
                            'arn:${PARTITION}:s3:::${BUCKET_NAME}/*',
                            PARTITION=If('IsChinaRegion', 'aws-cn', 'aws'),
                            BUCKET_NAME=Ref(bucket),
                        ),
                    },
                ]
            }
        ),
    ]
))

bucket_policy = t.add_resource(s3.BucketPolicy(
    'BucketPolicy',
    Bucket=Ref(bucket),
    PolicyDocument=
    {
        'Version': '2012-10-17',
        'Statement': [
            # {
            #     'Sid': 'DenyNotBucketOwnerControl',
            #     'Effect': 'Deny',
            #     'Principal': '*',
            #     'Action': [
            #         's3:PutObject',
            #     ],
            #     'Resource': [
            #         Sub('arn:${PARTITION}:s3:::${BUCKET_NAME}/*',
            #             PARTITION=If('IsChinaRegion', 'aws-cn', 'aws'),
            #             BUCKET_NAME=Ref(bucket),
            #             )
            #     ],
            #     'Condition': {
            #         'StringNotEquals': {
            #             's3:x-amz-acl': 'bucket-owner-full-control'
            #         },
            #
            #     }
            # },
            {
                'Sid': 'DenyIncorrectEncryptionHeader',
                'Effect': 'Deny',
                'Principal': '*',
                'Action': [
                    's3:PutObject',
                ],
                'Resource': [
                    Sub('arn:${PARTITION}:s3:::${BUCKET_NAME}/*',
                        PARTITION=If('IsChinaRegion', 'aws-cn', 'aws'),
                        BUCKET_NAME=Ref(bucket),
                        )
                ],
                'Condition': {
                    'StringNotEquals': {
                        's3:x-amz-server-side-encryption': 'AES256'
                    },
                }
            },
            {
                'Sid': 'DenyUnEncryptedObjectUploads',
                'Effect': 'Deny',
                'Principal': '*',
                'Action': [
                    's3:PutObject',
                ],
                'Resource': [
                    Sub('arn:${PARTITION}:s3:::${BUCKET_NAME}/*',
                        PARTITION=If('IsChinaRegion', 'aws-cn', 'aws'),
                        BUCKET_NAME=Ref(bucket),
                        )
                ],
                'Condition': {
                    'Null': {
                        's3:x-amz-server-side-encryption': 'true'
                    },
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
        Description='S3 bucket',
        Value=Ref(bucket),
        # Export=Export(Sub('${AWS::StackName}-BucketName'))
    ),
    Output(
        'BackupUser',
        Description='Backup user',
        Value=Ref(user),
        # Export=Export(Sub('${AWS::StackName}-BucketName'))
    ),

])

#
# Write
#

with open(__file__.replace('Template.py', '.template'), 'w') as f:
    f.write(t.to_json(indent=2))
