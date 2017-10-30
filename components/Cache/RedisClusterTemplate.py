# -*- encoding: utf-8 -*-

from __future__ import print_function

__author__ = 'kotaimen'
__date__ = '30/10/2017'

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
import troposphere.elasticache as elasticache
import troposphere.iam as iam
import troposphere.ec2 as ec2

from awacs.aws import Policy, Allow, Deny, Statement, Principal, Everybody
from awacs.aws import Condition, Bool, ArnEquals, StringEquals, IpAddress, Null
from awacs.aws import CurrentTime, EpochTime, MultiFactorAuthAge, Referer, \
    SecureTransport, SourceArn, SourceIp, UserAgent
import awacs.sts
import awacs.cloudformation
import awacs.iam

import csv
import cfnutil
import six

#
# Template
#
t = Template()
t.add_version('2010-09-09')
t.add_description('Simple Elasticache Redis Cluster')

#
# Interface
#


#
# Parameters
#

param_vpcid = t.add_parameter(Parameter(
    'VpcId',
    Description='VpcId of an existing VPC',
    Type='AWS::EC2::VPC::Id',
    ConstraintDescription='must be an existing vpc id.'
))

param_subnetids = t.add_parameter(Parameter(
    'SubnetIds',
    Description='SubnetIds of existing subnets of the VPC',
    Type='List<AWS::EC2::Subnet::Id>',
))

param_sg = t.add_parameter(Parameter(
    'SecurityGroup',
    Description='Cache security group id, a new security group will be '
                'created if this is left empty.',
    Type='String',
    Default='',
))

param_client_location = t.add_parameter(Parameter(
    'ClientLocation',
    Description='Lockdown cache access (default can be accessed '
                'from anywhere)',
    Type='String',
    MinLength='9',
    MaxLength='18',
    Default='0.0.0.0/0',
    AllowedPattern='(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})',
    ConstraintDescription='must be a valid CIDR range of the form x.x.x.x/x.',
))

param_cache_node_type = t.add_parameter(Parameter(
    'CacheNodeType',
    Description='Cache node instance type',
    Type='String',
    Default='cache.t2.micro',
    AllowedValues=sorted(cfnutil.load_mapping(
        'mapping/cache-node-types.json')),
    ConstraintDescription='must be a valid cache node type.'
))

param_cache_node_num = t.add_parameter(Parameter(
    'CacheNodeNum',
    Description='The number of cache nodes that the cache cluster should have.',
    Type='Number',
    Default=1,
    MaxValue=16,
    MinValue=1
))

#
# Mapping
#

#
# Condition
#

t.add_condition(
    'CreateSecurityGroupCondition',
    Equals(Ref(param_sg), '')
)

#
# Resources
#

cache_sg = t.add_resource(ec2.SecurityGroup(
    'CacheSecurityGroup',
    Condition='CreateSecurityGroupCondition',
    VpcId=Ref(param_vpcid),
    GroupDescription='Enable cache access',
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='6379',
            ToPort='6379',
            CidrIp=Ref(param_client_location),
        )
    ],
))

cache_subnet_group = t.add_resource(elasticache.SubnetGroup(
    'CacheSubnetGroup',
    Description='Cache subnet group',
    SubnetIds=Ref(param_subnetids)
))

cache_cluster = t.add_resource(elasticache.CacheCluster(
    'CacheCluster',
    Engine='redis',
    CacheNodeType=Ref(param_cache_node_type),
    NumCacheNodes=Ref(param_cache_node_num),
    AutoMinorVersionUpgrade=True,
    VpcSecurityGroupIds=[
        If('CreateSecurityGroupCondition',
           Ref(cache_sg),
           Ref(param_sg)
           )
    ],
))

#
# Output
#
t.add_output([
    Output('EndpointAddress',
           Description='The DNS address of the configuration endpoint for the Redis cache cluster.',
           Value=GetAtt(cache_cluster, 'RedisEndpoint.Address')
           ),
    Output('EndpointPort',
           Description='The port number of the configuration port for the Redis cache cluster.',
           Value=GetAtt(cache_cluster, 'RedisEndpoint.Port')
           ),
])

#
# Write template
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'))
