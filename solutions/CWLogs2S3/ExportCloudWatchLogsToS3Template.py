# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '04/06/2017'

from troposphere import Base64, FindInMap, GetAtt, Join, Select, Sub
from troposphere import ImportValue, Export
from troposphere import Condition, And, Equals, If, Not, Or
from troposphere import Template, Parameter, Ref, Tags, Output
from troposphere import AWS_ACCOUNT_ID, AWS_REGION, AWS_STACK_ID, \
    AWS_STACK_NAME, AWS_NO_VALUE
from troposphere import Delete, Retain, Snapshot

from troposphere.policies import CreationPolicy, ResourceSignal, UpdatePolicy, \
    AutoScalingReplacingUpdate, AutoScalingRollingUpdate

import troposphere.cloudformation as cloudformation
import troposphere.iam as iam
import troposphere.awslambda as awslambda
import troposphere.events as events
import troposphere.stepfunctions as stepfunctions

from awacs.aws import Policy, Allow, Deny, Statement, Principal, Everybody
from awacs.aws import Condition, Bool, ArnEquals, StringEquals, IpAddress, Null
from awacs.aws import CurrentTime, EpochTime, MultiFactorAuthAge, Referer, \
    SecureTransport, SourceArn, SourceIp, UserAgent

import awacs.sts
import awacs.cloudformation
import awacs.iam
import awacs.awslambda
import awacs.logs
import awacs.aws

import cfnutil

#
# Template
#

t = Template()
t.add_version('2010-09-09')
t.add_description('Export CloudWatch Logs to S3 on a schedule.')

#
# Interface
#
parameter_groups = [
    {
        'Label': {'default': 'Export Configuration'},
        'Parameters': [
            'LogGroupName',
            'BucketStack',
            'ExportPrefix',
            'ExportStatus',
            'ExportInterval',
        ],
    },

]

t.add_metadata(
    {
        'AWS::CloudFormation::Interface': {

            'ParameterGroups': parameter_groups,
            'ParameterLabels':
                dict(cfnutil.generate_parameter_labels(parameter_groups))
        }
    }
)

#
# Parameters
#

param_loggroup_name = t.add_parameter(Parameter(
    'LogGroupName',
    Type='String',
    Description='Name of the CloudWatch Logs LogGroup to export',
    Default='Logs'
))

param_bucket_stack = t.add_parameter(Parameter(
    'BucketStack',
    Description='Name of a stack exporting s3 bucket name',
    Default='SampleStack',
    Type='String',
    MinLength=1,
    MaxLength=128,
    AllowedPattern='^[a-zA-Z][-a-zA-Z0-9]*$',
    ConstraintDescription='must be a valid stack name.'
))

param_export_prefix = t.add_parameter(Parameter(
    'ExportPrefix',
    Type='String',
    Description='S3 prefix of the export',
    Default='exportedlogs'
))

param_export_status = t.add_parameter(Parameter(
    'ExportStatus',
    Type='String',
    Description='Whether the schedule is enabled',
    AllowedValues=['ENABLED', 'DISABLED'],
    Default='DISABLED'
))

param_export_interval = t.add_parameter(Parameter(
    'ExportInterval',
    Type='String',
    Description='Export interval',
    AllowedValues=['day', 'week'],
    Default='day'
))

#
# Condition
#

t.add_condition(
    'IsDailySchedule',
    Equals(Ref(param_export_interval), 'day'),
)

#
# Resource
#

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
            PolicyName='AllowCreateExportTask',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.logs.CreateExportTask,
                        awacs.logs.DescribeExportTasks,
                    ],
                    Resource=['*']
                )]
            )
        ),

    ]
))

lambda_function = t.add_resource(awslambda.Function(
    'LambdaFunction',
    Description='Extract zip file contents to S3',
    Code=awslambda.Code(
        ZipFile=cfnutil.load_python_lambda('lambdas/cwlogs-export.py')
    ),
    Handler='index.lambda_handler',
    Role=GetAtt(lambda_execution_role, 'Arn'),
    Runtime='python2.7',
    MemorySize='128',
    Timeout='15',
    Environment=awslambda.Environment(
        Variables={
            'EXPORT_INTERVAL': Ref(param_export_interval),
            'EXPORT_LOGGROUP': Ref(param_loggroup_name),
            'EXPORT_DST_BUCKET': ImportValue(
                Sub('${BucketStack}-BucketName')),
            'EXPORT_DST_PREFIX': Ref(param_export_prefix)
        }
    ),
))

states_execution_role = t.add_resource(iam.Role(
    'StatesExecutionRole',
    AssumeRolePolicyDocument=Policy(
        Statement=[Statement(
            Effect=Allow,
            Action=[awacs.sts.AssumeRole],
            Principal=Principal('Service',
                                [Sub('states.${AWS::Region}.amazonaws.com')])
        )]
    ),
    ManagedPolicyArns=[
    ],
    Policies=[
        iam.Policy(
            PolicyName='AllowCreateExportTask',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.awslambda.InvokeFunction,
                    ],
                    Resource=[GetAtt(lambda_function, 'Arn')]
                )]
            )
        ),

    ]
))

states_machine = t.add_resource(stepfunctions.StateMachine(
    'StateMachine',
    RoleArn=GetAtt(states_execution_role, 'Arn'),
    DefinitionString=Sub('''{
        "Comment": "A Retry example of the Amazon States Language using an AWS Lambda Function",
        "StartAt": "CreateExportTask",
        "States": {
            "CreateExportTask": {
                "Type": "Task",
                "Resource": "${EXPORT_LAMBDA_FUNCTION}",
                "Retry": [
                    {
                        "ErrorEquals": [ "States.Timeout" ],
                        "MaxAttempts": 0
                    },
                    {
                        "ErrorEquals": [ "States.ALL" ],
                        "IntervalSeconds": 30,
                        "MaxAttempts": 10,
                        "BackoffRate": 2.0
                    }
                ],
                "End": true
            }
        }
    }''', EXPORT_LAMBDA_FUNCTION=GetAtt(lambda_function, 'Arn'))
))

events_execution_role = t.add_resource(iam.Role(
    'EventsExecutionRole',
    AssumeRolePolicyDocument=Policy(
        Statement=[Statement(
            Effect=Allow,
            Action=[awacs.sts.AssumeRole],
            Principal=Principal('Service',
                                [Sub('events.amazonaws.com')])
        )]
    ),
    ManagedPolicyArns=[
    ],
    Policies=[
        iam.Policy(
            PolicyName='AllowCreateExportTask',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.aws.Action(prefix='states',
                                         action='StartExecution'),
                    ],
                    Resource=[Ref(states_machine)]
                )]
            )
        ),

    ]
))

# XXX Cloudformation doesnot support rules->step functions yet

# events_rule = t.add_resource(events.Rule(
#     'ScheduledRule',
#     ScheduleExpression=If('IsDailySchedule',
#                           'cron(5 0 * * ? *)',
#                           'cron(5 0 ? * 2 *)'),
#     State=Ref(param_export_status),
#     RoleArn=GetAtt(events_execution_role, 'Arn'),
#     Targets=[
#         events.Target(
#             Arn=Ref(states_machine),
#             Id='1',
#         )
#     ]
# ))

#
# Output
#

#
# Write
#
with open(__file__.replace('Template.py', '.template'), 'w') as f:
    f.write(t.to_json(indent=2))
