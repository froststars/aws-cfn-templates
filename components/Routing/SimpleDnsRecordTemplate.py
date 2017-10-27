# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '16/05/2017'

from troposphere import Base64, FindInMap, GetAtt, Join, Select, Sub
from troposphere import ImportValue, Export
from troposphere import Condition, And, Equals, If, Not, Or
from troposphere import Template, Parameter, Ref, Tags, Output
from troposphere import AWS_ACCOUNT_ID, AWS_REGION, AWS_STACK_ID, \
    AWS_STACK_NAME, AWS_NO_VALUE
from troposphere import Delete, Retain, Snapshot

from troposphere.policies import CreationPolicy, ResourceSignal, UpdatePolicy, \
    AutoScalingReplacingUpdate, AutoScalingRollingUpdate

import troposphere.route53 as route53
import troposphere.ec2 as ec2
import troposphere.iam as iam

import csv
import cfnutil
import six

#
# Template
#
t = Template()
t.add_version()
t.add_description('Dns alias record to a specific ip')

#
# Interface
#
parameter_groups = [
    {
        'Label': {'default': 'Dns Configuration'},
        'Parameters':
            [
                'HostedZoneName',
                'DomainName',
                'RecordType'
                'Target',
                'Ttl',
            ]
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
# Parameter
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

param_record_type = t.add_parameter(Parameter(
    'RecordType',
    Type='String',
    Description='Dns record type',
    Default='A',
    AllowedValues=['A', 'CNAME']
))

param_ttl = t.add_parameter(Parameter(
    'Ttl',
    Description='DNS time to live',
    Type='Number',
    MaxValue='86400',
    MinValue='1',
    Default='300',
))

param_target = t.add_parameter(Parameter(
    'Target',
    Description='Alias/cname target',
    Type='String',
))

#
# Resource
#

record = t.add_resource(route53.RecordSetType(
    'Record',
    HostedZoneName=Sub('${HostedZoneName}.'),
    Name=Join('.', [Ref(param_domain_name), Ref(param_hosted_domain)]),
    Type=Ref(param_record_type),
    TTL=Ref(param_ttl),
    ResourceRecords=[
        Ref(param_target)
    ]
))

#
# Output
#
t.add_output([
    Output('DnsName',
           Description='DNS name',
           Value=Ref(record),
           Export=Export(Sub('${AWS::StackName}-DnsName')),
           ),
])

#
# Write Template
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'), True)
