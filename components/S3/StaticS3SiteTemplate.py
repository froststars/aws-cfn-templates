# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '15/07/2017'

from troposphere import Retain, AWS_REGION, AWS_ACCOUNT_ID, AWS_NO_VALUE
from troposphere import Parameter, Sub, Export, Equals, Not, Join, Condition, \
    Split
from troposphere import Template, Ref, Output, FindInMap, If, GetAtt

import troposphere.s3 as s3

import cfnutil

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'Static s3 site with custom domain name'
)

#
# Parameters
#

param_hosted_domain = t.add_parameter(Parameter(
    'HostedZoneName',
    Type='String',
    Description='Hosted zone name'
))

param_domain_name = t.add_parameter(Parameter(
    'DomainName',
    Type='String',
    Description='Domain name'
))

param_index_doc = t.add_parameter(Parameter(
    'IndexDocument',
    Type='String',
    Default='index.html',
    Description='The name of the index document for the website.'
))

param_error_doc = t.add_parameter(Parameter(
    'ErrorDocument',
    Type='String',
    Default='error.html',
    Description='The name of the error document for the website.'
))

#
# Resource
#

bucket = t.add_resource(s3.Bucket(
    'Bucket',
    BucketName=Join('.', [Ref(param_domain_name), Ref(param_hosted_domain)]),
    WebsiteConfiguration=s3.WebsiteConfiguration(
        IndexDocument=Ref(param_index_doc),
        ErrorDocument=Ref(param_error_doc),
    ),

))

bucket_policy = t.add_resource(s3.BucketPolicy(
    'BucketPolicy',
    Bucket=Ref(bucket),
    PolicyDocument=
    {
        'Version': '2012-10-17',
        'Statement': [{
            'Sid': 'PublicReadGetObject',
            'Effect': 'Allow',
            'Principal': '*',
            'Action': ['s3:GetObject'],
            'Resource': [
                Join('/', [GetAtt(bucket, 'Arn'), '*'])
            ]
        }
        ]
    },
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
    Output(
        'DomainName',
        Description='IPv4 DNS name of the bucket',
        Value=GetAtt(bucket, 'DomainName'),
    ),
    Output(
        'WebsiteURL',
        Description='S3 website endpoint for the bucket',
        Value=GetAtt(bucket, 'WebsiteURL'),
    ),

])

#
# Write
#

cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
