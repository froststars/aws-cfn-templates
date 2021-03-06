# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '14/07/2017'

from troposphere import Sub, Export, Parameter, Join, If, Not, Equals
from troposphere import Template, Ref, Output, GetAtt
from troposphere import AWS_NO_VALUE

import troposphere.s3 as s3
import cfnutil

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'Route53 origin content bucket'
)

#
# Parameters
#
origin_access_identity = t.add_parameter(Parameter(
    'OriginAccessIdentity',
    Description='Id of the Cloudfront Origin Access Identity',
    Type='String',
    AllowedPattern='[A-Z0-9]+',
    ConstraintDescription='must be a valid OAI name'
))

param_cors_origin = t.add_parameter(Parameter(
    'CorsOrigin',
    Description='CORS origin',
    Default='',
    Type='String',
))
#
# Condition
#
t.add_condition(
    'HasCorsOrigin',
    Not(Equals(Ref(param_cors_origin), ''))
)

#
# Resource
#

bucket = t.add_resource(s3.Bucket(
    'Bucket',
    CorsConfiguration=If('HasCorsOrigin',
                         s3.CorsConfiguration(
                             CorsRules=[
                                 s3.CorsRules(
                                     AllowedHeaders=['*'],
                                     AllowedMethods=['GET', 'PUT', 'HEAD',
                                                     'POST', 'DELETE'],
                                     AllowedOrigins=[Ref(param_cors_origin)],
                                 )
                             ]
                         ),
                         Ref(AWS_NO_VALUE))
))

t.add_resource(s3.BucketPolicy(
    'BucketPolicy',
    Bucket=Ref(bucket),
    PolicyDocument={
        'Version': '2012-10-17',
        'Id': 'CdnAccessPolicy',
        'Statement': [
            {
                'Sid': '1',
                'Effect': 'Allow',
                'Principal': {
                    'AWS': Sub(
                        'arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ${OriginAccessIdentity}',
                    )
                },
                'Action': 's3:GetObject',
                'Resource': Join('/', [GetAtt(bucket, 'Arn'), '*'])
            }
        ]
    },
    DependsOn='Bucket'
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
