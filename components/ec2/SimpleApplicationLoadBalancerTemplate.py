# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '23/12/2016'

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

import troposphere.ec2 as ec2
import troposphere.iam as iam
import troposphere.s3 as s3
import troposphere.s3 as s3
import troposphere.elasticloadbalancingv2 as elbv2

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
t.add_version('2010-09-09')
t.add_description(
    'Application Load Balancer with single instance as target'
)

#
# Interface
#
parameter_groups = [
    {
        'Label': {'default': 'Network Configuration'},
        'Parameters': [
            'VpcId',
            'SubnetIds',
            'AvailableZones',
        ],
    },
    {
        'Label': {'default': 'LoadBalancer Configuration'},
        'Parameters': [
            'InstanceId',
            'CertificateArn',
            'LogBucket',
            'LogPrefix'
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

param_vpcid = t.add_parameter(Parameter(
    'VpcId',
    Description='VpcId of an existing VPC.',
    Type='AWS::EC2::VPC::Id'
))

param_subnetids = t.add_parameter(Parameter(
    'SubnetIds',
    Description='SubnetIds of an existing subnets in the VPC.',
    Type='List<AWS::EC2::Subnet::Id>'
))

param_securitygroup = t.add_parameter(Parameter(
    'SecurityGroupId',
    Description='Load balancer security group id',
    Type='AWS::EC2::SecurityGroup::Id',
))

param_certificate = t.add_parameter(Parameter(
    'CertificateArn',
    Description='ARN of IAM or ACM certificate to bind to LB.',
    Type='String',
    Default='arn',
))

param_instance_id = t.add_parameter(Parameter(
    'InstanceId',
    Description='Name of the ec2 instance as target',
    Type='AWS::EC2::Instance::Id',
))

param_bucket_name = t.add_parameter(Parameter(
    'BucketName',
    Description='Name of the ELB log bucket, the bucket should have proper '
                'bucket policy to enable log delivery, set to empty string '
                'disables logging.',
    Default='',
    Type='String',
    AllowedPattern=r'[-\.a-z0-9]*',
))

param_log_perfix = t.add_parameter(Parameter(
    'LogPrefix',
    Description='Access log prefix',
    Default='',
    Type='String',
    MinLength=0,
    MaxLength=128,
))

#
# Condition
#

t.add_condition(
    'EnableAccessLogsCondition',
    Not(Equals(Ref(param_bucket_name), ''))
)

#
# Resources
#

load_balancer = t.add_resource(elbv2.LoadBalancer(
    'LoadBalancer',
    Scheme='internet-facing',
    SecurityGroups=[Ref(param_securitygroup)],
    Subnets=Ref(param_subnetids),
    LoadBalancerAttributes=[
        elbv2.LoadBalancerAttributes(
            Key='deletion_protection.enabled',
            Value='false'
        ),
        elbv2.LoadBalancerAttributes(
            Key='idle_timeout.timeout_seconds',
            Value='60'
        ),
        elbv2.LoadBalancerAttributes(
            Key='access_logs.s3.enabled',
            Value=If('EnableAccessLogsCondition', 'true', 'false')
        ),
        elbv2.LoadBalancerAttributes(
            Key='access_logs.s3.bucket',
            Value=Ref(param_bucket_name)
        ),
        elbv2.LoadBalancerAttributes(
            Key='access_logs.s3.prefix',
            Value=Ref(param_log_perfix)
        )
    ]
))

targetgroup = t.add_resource(elbv2.TargetGroup(
    'TargetGroup',
    DependsOn='LoadBalancer',
    VpcId=Ref(param_vpcid),
    Protocol='HTTP',
    Port='80',
    Targets=[
        elbv2.TargetDescription(
            Id=Ref(param_instance_id),
            Port='80',
        )
    ],
    HealthCheckIntervalSeconds='15',
    HealthCheckPath='/',
    HealthCheckPort='80',
    HealthCheckProtocol='HTTP',
    HealthCheckTimeoutSeconds='5',
    HealthyThresholdCount='3',
    UnhealthyThresholdCount='5',
    Matcher=elbv2.Matcher(HttpCode='200'),
    TargetGroupAttributes=[
        elbv2.TargetGroupAttribute(
            Key='deregistration_delay.timeout_seconds',
            Value='20'
        )
    ]
))

http_listener = t.add_resource(elbv2.Listener(
    'HttpListener',
    DefaultActions=[
        elbv2.Action(
            TargetGroupArn=Ref(targetgroup),
            Type='forward'
        )
    ],
    LoadBalancerArn=Ref(load_balancer),
    Port='80',
    Protocol='HTTP',
))

https_listener = t.add_resource(elbv2.Listener(
    'HttpsListener',
    DefaultActions=[
        elbv2.Action(
            TargetGroupArn=Ref(targetgroup),
            Type='forward'
        )
    ],
    LoadBalancerArn=Ref(load_balancer),
    Port='443',
    Protocol='HTTPS',
    Certificates=[
        elbv2.Certificate(
            CertificateArn=Ref(param_certificate)
        )
    ]
))

#
# Output
#
t.add_output([
    Output(
        'LoadBalancerName',
        Description='The name of the Application load balancer',
        Value=GetAtt(load_balancer, 'LoadBalancerName'),
    ),
    Output(
        'LoadBalancerFullName',
        Description='The full name of the Application load balancer',
        Value=GetAtt(load_balancer, 'LoadBalancerFullName'),
    ),
    Output(
        'DNSName',
        Description=' DNS name for the Application load balancer',
        Value=GetAtt(load_balancer, 'DNSName'),
    ),
    Output(
        'CanonicalHostedZoneID',
        Description='Hosted zone ID of the Application load balancer',
        Value=GetAtt(load_balancer, 'CanonicalHostedZoneID'),
    ),
    Output(
        'SecurityGroups',
        Description='The IDs of the security groups for the Application load balancer',
        Value=Select(0, GetAtt(load_balancer, 'SecurityGroups')),
    ),
])

#
# Write
#

cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
