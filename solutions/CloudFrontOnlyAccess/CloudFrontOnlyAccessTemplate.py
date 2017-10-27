# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '8/21/16'

from troposphere import Base64, FindInMap, GetAtt, Join, Select, Sub, \
    ImportValue, Export
from troposphere import Condition, And, Equals, If, Not, Or
from troposphere import Template, Parameter, Ref, Tags, Output
from troposphere import AWS_ACCOUNT_ID, AWS_REGION, AWS_STACK_ID, \
    AWS_STACK_NAME, AWS_NO_VALUE
from troposphere import Delete, Retain, Snapshot

from troposphere.policies import CreationPolicy, ResourceSignal, UpdatePolicy, \
    AutoScalingReplacingUpdate, AutoScalingRollingUpdate

import troposphere.cloudformation as cloudformation
import troposphere.ec2 as ec2
import troposphere.awslambda as awslambda
import troposphere.iam as iam
import troposphere.sns as sns

from awacs.aws import Policy, Allow, Deny, Statement, Principal
import awacs.sts
import awacs.ec2
import awacs.iam
import awacs.sns

import cfnutil

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'Automatically update SecurityGroups to limit access from CloudFront Edges only'
)

#
# Parameters
#
param_regions = t.add_parameter(Parameter(
    'Regions',
    Description='Region to search for SecurityGroups, separated by ","',
    Default='us-east-1',
    Type='String'
))

#
# Resources
#

update_function_execution_role = t.add_resource(iam.Role(
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
            PolicyName='AllowModifySecurityGroup',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.ec2.DescribeSecurityGroups,
                        awacs.ec2.AuthorizeSecurityGroupIngress,
                        awacs.ec2.RevokeSecurityGroupIngress,
                    ],
                    Resource=['*']
                )]
            )
        )
    ]
))

update_security_groups_function = t.add_resource(awslambda.Function(
    'UpdateSecurityGroups',
    Description='Update Beanstalk Environment SecurityGroup',
    # code=awslambda.code(
    # S3Bucket=Sub('aws-lambda-code-${AWS::AccountId}-${AWS::Region}'),
    # S3Key='update_security_groups.py.zip'

    # ),
    Code=awslambda.Code(
        ZipFile=cfnutil.load_python_lambda('lambdas/update_security_groups.py')
    ),
    Environment=awslambda.Environment(
        Variables={'REGIONS': Ref(param_regions)}
    ),
    Handler='index.lambda_handler',
    Role=GetAtt(update_function_execution_role, 'Arn'),
    Runtime='python2.7',
    MemorySize='128',
    Timeout='300',
))

ip_space_changed_topic = 'arn:aws:sns:us-east-1:806199016981:AmazonIpSpaceChanged'

update_function_lambda_permission = t.add_resource(awslambda.Permission(
    'LambdaPermission',
    FunctionName=Ref(update_security_groups_function),
    Action='lambda:InvokeFunction',
    Principal='sns.amazonaws.com',
    SourceArn=ip_space_changed_topic
))

custom_resource_execution_role = t.add_resource(iam.Role(
    'CustomResourceExecutionRole',
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
            PolicyName='AllowModifySecurityGroup',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.sns.ListSubscriptions,
                        awacs.sns.Subscribe,
                        awacs.sns.Unsubscribe,
                    ],
                    Resource=['*']
                )]
            )
        )
    ]
))

custom_resource_lambda_function = t.add_resource(awslambda.Function(
    'CustomResourceFunction',
    Description='Lambda backed custom resource',
    Code=awslambda.Code(
        ZipFile=cfnutil.load_python_lambda('lambdas/sns_custom_resource.py'),
    ),
    Handler='index.lambda_handler',
    Role=GetAtt(custom_resource_execution_role, 'Arn'),
    Runtime='python2.7',
    MemorySize='128',
    Timeout='60',
))


class SNSSubscription(cloudformation.CustomResource):
    resource_type = 'Custom::SNSSubscription'

    props = {
        'ServiceToken': (str, True),
        'TopicArn': (str, True),
        'Protocol': (str, True),
        'Endpoint': (str, True)
    }


sns_subscription = t.add_resource(SNSSubscription(
    'SNSSubscription',
    StackName=Ref(AWS_STACK_NAME),
    ServiceToken=GetAtt(custom_resource_lambda_function, 'Arn'),
    TopicArn=ip_space_changed_topic,
    Protocol='lambda',
    Endpoint=GetAtt(update_security_groups_function, 'Arn'),
))

#
# Output
#

#
# Write template
#

cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
