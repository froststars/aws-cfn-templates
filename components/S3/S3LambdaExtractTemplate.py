# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '24/05/2017'

from troposphere import Base64, FindInMap, GetAtt, Join, Select, Sub
from troposphere import And, Equals, If, Not, Or
from troposphere import Template, Parameter, Ref, Tags, Output, Export
from troposphere import AWS_ACCOUNT_ID, AWS_REGION, AWS_STACK_ID, \
    AWS_STACK_NAME, AWS_NO_VALUE
from troposphere import Delete, Retain, Snapshot
from troposphere.policies import CreationPolicy, ResourceSignal

import troposphere.iam as iam
import troposphere.s3 as s3
import troposphere.awslambda as awslambda

from awacs.aws import Policy, Allow, Deny, Statement, Principal
import awacs.sts
import awacs.s3
import awacs.awslambda
import awacs.iam

import cfnutil
import hashlib

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'Extract compressed files in one bucket into another bucket using s3 '
    'events and lambda function'
)

#
# Parameters
#

# XXX: This is really stupid but nessary, see http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-notificationconfig.html
param_bucket_notification = t.add_parameter(Parameter(
    'BucketNotification',
    Description='Enable bucket notification configuration, set this to disable '
                'when creating the stack then enable and update the stack.  '
                'This is required to break the circular resource dependency of '
                'S3 bucket and lambda permission.',
    Default='01 - Disabled',
    Type='String',
    AllowedValues=['01 - Disabled', '02 - Enabled'],
))

# param_dst_prefix = t.add_parameter(Parameter(
#     'DestinationPrefix',
#     Description='Destination bucket prefix',
#     Default='',
#     Type='String',
# ))

#
# Condition
#
t.add_condition(
    'BucketNotificationEnabled',
    Equals(Ref(param_bucket_notification), '02 - Enabled')
)

#
# Resource
#

function_code = cfnutil.load_python_lambda('lambdas/s3_extract.py')

# HACK: Use hard-coded name here to avoid circular depencency
h = hashlib.md5()
h.update(function_code)
lambda_function_name = 's3-extract-function-%s' % h.hexdigest()

src_bucket = t.add_resource(s3.Bucket(
    'SourceBucket',
    NotificationConfiguration= \
        If('BucketNotificationEnabled',
           s3.NotificationConfiguration(
               LambdaConfigurations=[
                   s3.LambdaConfigurations(
                       Function=Sub(
                           'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:%s' \
                           % lambda_function_name),
                       Event='s3:ObjectCreated:*',
                       Filter=s3.Filter(
                           S3Key=s3.S3Key(
                               Rules=[
                                   s3.Rules(Name='prefix', Value=''),
                                   s3.Rules(Name='suffix', Value='.zip')
                               ]
                           )
                       ),
                   ),
                   s3.LambdaConfigurations(
                       Function=Sub(
                           'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:%s' \
                           % lambda_function_name),
                       Event='s3:ObjectCreated:*',
                       Filter=s3.Filter(
                           S3Key=s3.S3Key(
                               Rules=[
                                   s3.Rules(Name='prefix', Value=''),
                                   s3.Rules(Name='suffix', Value='.gz')
                               ]
                           )
                       ),
                   )
               ]
           ),
           Ref(AWS_NO_VALUE)),
))

dst_bucket = t.add_resource(s3.Bucket(
    'DestinationBucket',
))

lambda_execution_role = t.add_resource(iam.Role(
    'LambdaExecutionRole',
    AssumeRolePolicyDocument=Policy(
        Statement=[Statement(
            Effect=Allow,
            Action=[awacs.sts.AssumeRole],
            Principal=Principal('Service', ['lambda.amazonaws.com'])
        )]
    ),
    ManagedPolicyArns=[
        'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
    ],
    Policies=[
        iam.Policy(
            PolicyName='AllowReadSrcBucket',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.s3.GetObject,
                    ],
                    Resource=[
                        Join('', ['arn:aws:s3:::',
                                  Ref(src_bucket), '/*'])
                    ]
                )]
            )
        ),
        iam.Policy(
            PolicyName='AllowWriteDstBucket',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.s3.PutObject,
                        awacs.s3.ListMultipartUploadParts,
                        awacs.s3.AbortMultipartUpload,
                    ],
                    Resource=[
                        Join('', ['arn:aws:s3:::',
                                  Ref(dst_bucket), '/*'])
                    ]
                )]
            )
        ),

    ]
))

lambda_function = t.add_resource(awslambda.Function(
    'LambdaFunction',
    FunctionName=lambda_function_name,
    Description='Extract zip file contents to S3',
    Code=awslambda.Code(
        ZipFile=function_code
    ),
    Handler='index.lambda_handler',
    Role=GetAtt(lambda_execution_role, 'Arn'),
    Runtime='python2.7',
    MemorySize='512',
    Timeout='120',
    Environment=awslambda.Environment(
        Variables={
            'DST_BUCKET': Ref(dst_bucket),
            # 'DST_PREFIX': Ref(param_dst_prefix)
        }
    ),
))

updater_lambda_permission = t.add_resource(awslambda.Permission(
    'LambdaPermission',
    FunctionName=Ref(lambda_function),
    Action='lambda:InvokeFunction',
    Principal='s3.amazonaws.com',
    SourceAccount=Sub('${AWS::AccountId}'),
    SourceArn=Join('', ['arn:aws:s3:::', Ref(src_bucket)]),
))

#
# Output
#
t.add_output([
    Output(
        'SourceBucketName',
        Description='S3 bucket',
        Value=Ref(src_bucket),
        Export=Export(Sub('${AWS::StackName}-SourceBucketName'))
    ),
    Output(
        'DestinationBucketName',
        Description='S3 bucket',
        Value=Ref(dst_bucket),
        Export=Export(Sub('${AWS::StackName}-DestinationBucketName'))
    )
])

#
# Write
#
with open(__file__.replace('Template.py', '.template'), 'w') as f:
    f.write(t.to_json(indent=2))
