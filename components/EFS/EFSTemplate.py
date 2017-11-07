# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '07/11/2017'

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
import troposphere.efs as efs
import troposphere.ec2 as ec2
import troposphere.iam as iam
import troposphere.rds as rds

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
t.add_description('Simple Elastic File System')

#
# Interface
#

parameter_groups = [
    {
        'Label': {'default': 'Network Configuration'},
        'Parameters':
            [
                'VpcId',
                'SubnetIds',
                'NumberOfSubnets',
                'SecurityGroup',
            ]
    },
    {
        'Label': {'default': 'Filesystem Configuration'},
        'Parameters':
            [
                'PerformanceMode',
            ]
    },
    {
        'Label': {'default': 'Security Configuration'},
        'Parameters':
            [
                'Encrypted',
                'KmsKeyId',
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
# Parameters
#
param_vpcid = t.add_parameter(Parameter(
    'VpcId',
    Description='VpcId of an existing VPC.',
    Type='AWS::EC2::VPC::Id'
))

param_subnetids = t.add_parameter(Parameter(
    'SubnetIds',
    Description='SubnetIds of existing subnets of the VPC where mount '
                'target will be created.  Note: for each file system, '
                'you can create only one mount target per AZ.',
    Type='List<AWS::EC2::Subnet::Id>',
))

param_num_of_subnets = t.add_parameter(Parameter(
    'NumberOfSubnets',
    Description='Number of subnets in SubnetIds parameter',
    Type='Number',
    Default=2,
    MinValue=1,
    MaxValue=6,
))

param_sg = t.add_parameter(Parameter(
    'SecurityGroup',
    Description='Mount target security group id, a new security group will be '
                'created this is left empty.',
    Type='String',
    Default='',
))

param_performance_mode = t.add_parameter(Parameter(
    'PerformanceMode',
    Description='Performance mode of the file system.',
    Type='String',
    Default='generalPurpose',
    AllowedValues=['generalPurpose', 'maxIO']
))

param_encrypted = t.add_parameter(Parameter(
    'Encrypted',
    Description='Indicates whether the file system is encrypted.',
    Default='false',
    Type='String',
    AllowedValues=['true', 'false'],
))

param_kms_key = t.add_parameter(Parameter(
    'KmsKeyId',
    Description='The ARN of the KMS master key that is used to encrypt the '
                'file system, If you enable the Encrypted property but '
                'don\'t specify this property, this template uses service '
                'default master key.',
    Default='',
    Type='String'
))

#
# Conditions
#

t.add_condition(
    'TwoSubnetsCondition',
    Or(
        Equals(Ref(param_num_of_subnets), '2'),
        Equals(Ref(param_num_of_subnets), '3'),
        Equals(Ref(param_num_of_subnets), '4'),
        Equals(Ref(param_num_of_subnets), '5'),
        Equals(Ref(param_num_of_subnets), '6'),
    )
)

t.add_condition(
    'ThreeSubnetsCondition',
    Or(
        Equals(Ref(param_num_of_subnets), '3'),
        Equals(Ref(param_num_of_subnets), '4'),
        Equals(Ref(param_num_of_subnets), '5'),
        Equals(Ref(param_num_of_subnets), '6'),
    )
)

t.add_condition(
    'FourSubnetsCondition',
    Or(
        Equals(Ref(param_num_of_subnets), '4'),
        Equals(Ref(param_num_of_subnets), '5'),
        Equals(Ref(param_num_of_subnets), '6'),
    )
)

t.add_condition(
    'FiveSubnetsCondition',
    Or(
        Equals(Ref(param_num_of_subnets), '5'),
        Equals(Ref(param_num_of_subnets), '6'),
    )
)

t.add_condition(
    'SixSubnetsCondition',
    Equals(Ref(param_num_of_subnets), '6'),
)

t.add_condition(
    'StorageEncryptedCondition',
    Equals(Ref(param_encrypted), 'true'),
)

t.add_condition(
    'DefaultKmsCondition',
    Equals(Ref(param_kms_key), '')
)
t.add_condition(
    'CreateSecurityGroupCondition',
    Equals(Ref(param_sg), '')
)

#
# Resources
#

file_system = t.add_resource(efs.FileSystem(
    'FileSystem',
    Encrypted=Ref(param_encrypted),
    KmsKeyId=If('StorageEncryptedCondition',
                If('DefaultKmsCondition',
                   Ref(AWS_NO_VALUE),
                   Ref(param_kms_key)),
                Ref(AWS_NO_VALUE),
                ),
    PerformanceMode=Ref(param_performance_mode),
))

efs_sg = t.add_resource(ec2.SecurityGroup(
    'EfsSecurityGroup',
    Condition='CreateSecurityGroupCondition',
    VpcId=Ref(param_vpcid),
    GroupDescription='Enable local postgres access',
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='2049',
            ToPort='2049',
            CidrIp='0.0.0.0/0',
        ),
    ],
))

mount_target_1 = t.add_resource(efs.MountTarget(
    'MountTarget1',
    FileSystemId=Ref(file_system),
    SubnetId=Select(0, Ref(param_subnetids)),
    SecurityGroups=[
        If(
            'CreateSecurityGroupCondition',
            Ref(efs_sg),
            Ref(param_sg)
        )]
))

mount_target_2 = t.add_resource(efs.MountTarget(
    'MountTarget2',
    Condition='TwoSubnetsCondition',
    FileSystemId=Ref(file_system),
    SubnetId=Select(1, Ref(param_subnetids)),
    SecurityGroups=[
        If(
            'CreateSecurityGroupCondition',
            Ref(efs_sg),
            Ref(param_sg)
        )]
))

mount_target_3 = t.add_resource(efs.MountTarget(
    'MountTarget3',
    Condition='ThreeSubnetsCondition',
    FileSystemId=Ref(file_system),
    SubnetId=Select(2, Ref(param_subnetids)),
    SecurityGroups=[
        If(
            'CreateSecurityGroupCondition',
            Ref(efs_sg),
            Ref(param_sg)
        )]
))

mount_target_4 = t.add_resource(efs.MountTarget(
    'MountTarget4',
    Condition='FourSubnetsCondition',
    FileSystemId=Ref(file_system),
    SubnetId=Select(3, Ref(param_subnetids)),
    SecurityGroups=[
        If(
            'CreateSecurityGroupCondition',
            Ref(efs_sg),
            Ref(param_sg)
        )]
))

mount_target_5 = t.add_resource(efs.MountTarget(
    'MountTarget5',
    Condition='FiveSubnetsCondition',
    FileSystemId=Ref(file_system),
    SubnetId=Select(4, Ref(param_subnetids)),
    SecurityGroups=[
        If(
            'CreateSecurityGroupCondition',
            Ref(efs_sg),
            Ref(param_sg)
        )]
))

mount_target_6 = t.add_resource(efs.MountTarget(
    'MountTarget6',
    Condition='SixSubnetsCondition',
    FileSystemId=Ref(file_system),
    SubnetId=Select(5, Ref(param_subnetids)),
    SecurityGroups=[
        If(
            'CreateSecurityGroupCondition',
            Ref(efs_sg),
            Ref(param_sg)
        )]
))

#
# Output
#
t.add_output([

    Output('MountPoint',
           Description='EFS mount point',
           Value=Sub('${FileSystem}.efs.${AWS::Region}.amazonaws.com'),
           ),

    Output('ElasticFileSystem',
           Description='ElasticFileSystem',
           Value=Ref(file_system)
           ),

    Output('MountTargetSecurityGroup',
           Condition='CreateSecurityGroupCondition',
           Description='MountTargetSecurityGroup',
           Value=Ref(efs_sg)
           ),

    Output('MountTarget1',
           Description='MountTarget1',
           Value=Ref(mount_target_1)
           ),
])

#
# Write template
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
