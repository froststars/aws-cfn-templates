# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '07/07/2017'

from troposphere import Template, Parameter, Output, Retain
from troposphere import GetAtt, Export, Equals, Ref, If, AWS_NO_VALUE, Not, Sub

from troposphere import ec2
from troposphere import logs
from troposphere import iam

from awacs.aws import Policy, Allow, Deny, Statement, Principal, Everybody
from awacs.aws import Condition, Bool, ArnEquals, StringEquals, IpAddress, Null
from awacs.aws import CurrentTime, EpochTime, MultiFactorAuthAge, Referer, \
    SecureTransport, SourceArn, SourceIp, UserAgent
import awacs.sts
import awacs.cloudformation
import awacs.iam
import awacs.ec2
import awacs.logs

import cfnutil

#
# Template
#
t = Template()
t.add_version()
t.add_description(
    'VPC flow logging'
)

#
# Parameters
#

param_retention = t.add_parameter(Parameter(
    'RetentionDays',
    Type='Number',
    Description='The number of days log events are kept in CloudWatch Logs.',
    AllowedValues=[-1, 1, 3, 5, 7, 14, 30, 60, 90, 120, 150,
                   180, 365, 400, 545, 731, 1827, 3653],
    Default='-1'
))

param_resource_id = t.add_parameter(Parameter(
    'ResourceId',
    Description='The ID of the subnet, network interface, or VPC for which '
                'you want to create a flow log.',
    Type='String',
))

param_resource_type = t.add_parameter(Parameter(
    'ResourceType',
    Description='The type of resource that you specified in the ResourceId '
                'parameter',
    Type='String',
    Default='VPC',
    AllowedValues=['VPC', 'Subnet', 'NetworkInterface'],
))

param_traffic_type = t.add_parameter(Parameter(
    'TrafficType',
    Description='The type of traffic to log.',
    Type='String',
    Default='ALL',
    AllowedValues=['ACCEPT', 'REJECT', 'ALL'],
))

#
# Don't expire condition
#
t.add_condition(
    'NotExpireCondition',
    Equals(Ref(param_retention), -1)
)

#
# Resources
#

log_group = t.add_resource(logs.LogGroup(
    'LogGroup',
    RetentionInDays=If('NotExpireCondition',
                       Ref(AWS_NO_VALUE),
                       Ref(param_retention))
))

log_delivery_role = t.add_resource(iam.Role(
    'LogDeliveryRole',
    AssumeRolePolicyDocument=Policy(
        Statement=[Statement(
            Effect=Allow,
            Action=[awacs.sts.AssumeRole],
            Principal=Principal('Service', ['vpc-flow-logs.amazonaws.com'])
        )]
    ),
    Policies=[
        iam.Policy(
            PolicyName='AllowReadSrcBucket',
            PolicyDocument=Policy(
                Version='2012-10-17',
                Statement=[Statement(
                    Effect=Allow,
                    Action=[
                        awacs.logs.CreateLogGroup,
                        awacs.logs.CreateLogStream,
                        awacs.logs.PutLogEvents,
                        awacs.logs.DescribeLogGroups,
                        awacs.logs.DescribeLogStreams
                    ],
                    Resource=[
                        GetAtt(log_group, 'Arn')
                    ]
                )]
            )
        ),
    ]
))

vpc_flow_log = t.add_resource(ec2.FlowLog(
    'FlowLog',
    DeliverLogsPermissionArn=GetAtt(log_delivery_role, 'Arn'),
    LogGroupName=Ref(log_group),
    ResourceId=Ref(param_resource_id),
    ResourceType=Ref(param_resource_type),
    TrafficType=Ref(param_traffic_type),
))

#
# Output
#
t.add_output([
    Output(
        'LogGroupName',
        Description='Name of the log group.',
        Value=Ref(log_group),
        Export=Export(Sub('${AWS::StackName}-LogGroupName'))
    ),
    Output(
        'LogGroupArn',
        Description='Arn of the log group.',
        Value=GetAtt(log_group, 'Arn'),
        Export=Export(Sub('${AWS::StackName}-LogGroupArn'))
    ),
    Output(
        'FlowLog',
        Description='Flow log ID',
        Value=Ref(vpc_flow_log),
    )
])
#
# Write template
#

cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
