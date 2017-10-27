# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '04/12/2016'

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
t.add_description('PostGres RDS instance.')

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
                'SecurityGroup',
            ]
    },
    {
        'Label': {'default': 'Database Basic Configuration'},
        'Parameters':
            [
                # 'DatabaseName',
                'DatabaseSnapshot',
                'DatabaseClass',
                'DatabaseEngineVersion',
                'DatabaseMultiAz',
                'DatabaseUser',
                'DatabasePassword',
            ]
    },
    {
        'Label': {'default': 'Database Storage Configuration'},
        'Parameters':
            [
                'StorageSize',
                'StorageType',
                'StorageIops',
                'StorageEncrypted',
                'KmsKeyId',
            ]
    },
    {
        'Label': {'default': 'Database Security Configuration'},
        'Parameters':
            [
                'EnhancedMonitoringConditionRole',
                'ClientLocation',
                'PubliclyAccessible',
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
    Description='SubnetIds of existing subnets of the VPC',
    Type='List<AWS::EC2::Subnet::Id>',
))

param_sg = t.add_parameter(Parameter(
    'SecurityGroup',
    Description='Database security group id, a new security group will be '
                'created this is left empty.',
    Type='String',
    Default='',
))

# param_dbname = t.add_parameter(Parameter(
#     'DatabaseName',
#     Default='MyDatabase',
#     Description='Database name',
#     Type='String',
#     MinLength='1',
#     MaxLength='64',
#     AllowedPattern='[a-zA-Z][a-zA-Z0-9]*',
#     ConstraintDescription=('must begin with a letter and contain only '
#                            'alphanumeric characters.')
# ))

param_db_snapshot = t.add_parameter(Parameter(
    'DatabaseSnapshot',
    Description='ARN of a DB snapshot to restore from',
    Type='String',
    Default='',
))

param_db_class = t.add_parameter(Parameter(
    'DatabaseClass',
    Default='db.t2.micro',
    Description='Database instance class',
    Type='String',
    AllowedValues=cfnutil.load_mapping('mapping/rds-instance-types.json'),
))

param_db_engine_version = t.add_parameter(Parameter(
    'DatabaseEngineVersion',
    Default='9.5.4',
    Description='Database engine version',
    Type='String',
    AllowedValues=cfnutil.load_mapping('mapping/rds-postgres-versions.json'),
))

param_db_user = t.add_parameter(Parameter(
    'DatabaseUser',
    NoEcho=True,
    Description='The database admin account username, ignored when '
                'a snapshot is specified',
    Type='String',
    MinLength='1',
    MaxLength='16',
    AllowedPattern='[a-zA-Z][a-zA-Z0-9]*',
    ConstraintDescription=('must begin with a letter and contain only'
                           ' alphanumeric characters.')
))

param_db_password = t.add_parameter(Parameter(
    'DatabasePassword',
    NoEcho=True,
    Description='The database admin account password, ignored when a snapshot is specified',
    Type='String',
    MinLength='1',
    MaxLength='41',
    AllowedPattern='[a-zA-Z0-9]*',
    ConstraintDescription='must contain only alphanumeric characters.'
))

param_db_multi_az = t.add_parameter(Parameter(
    'DatabaseMultiAz',
    NoEcho=True,
    Description='Whether use a multi-AZ Deployment',
    Type='String',
    Default='false',
    AllowedValues=['true', 'false'],
))

param_db_storage_size = t.add_parameter(Parameter(
    'StorageSize',
    Default='5',
    Description='The size of the database storage in GB',
    Type='Number',
    MinValue='5',
    MaxValue='6144',
    ConstraintDescription='must be between 5GB and 6TB.',
))

param_db_stroage_type = t.add_parameter(Parameter(
    'StorageType',
    Description='Database storage type',
    Type='String',
    Default='gp2',
    AllowedValues=['gp2', 'io1', 'default'],
))

param_db_storage_iops = t.add_parameter(Parameter(
    'StorageIops',
    Description='IOPS database storage supports, used when the volume type is io1',
    Type='Number',
    Default='100',
    MinValue='100',
    MaxValue='30000',
    ConstraintDescription='IOPS range is 100 to 30000'
))

param_db_storage_encrypted = t.add_parameter(Parameter(
    'StorageEncrypted',
    Description='Indicates whether the DB instance is encrypted.',
    Default='false',
    Type='String',
    AllowedValues=['true', 'false'],
))

param_db_kms_key = t.add_parameter(Parameter(
    'KmsKeyId',
    Description='The ARN of the KMS master key that is used to encrypt the DB '
                'instance, If you enable the StorageEncrypted property but '
                'don\'t specify this property, AWS CloudFormation uses the '
                'default master key.',
    Default='',
    Type='String'
))

param_db_monitoring_role = t.add_parameter(Parameter(
    'EnhancedMonitoringConditionRole',
    Description='Database enhanced monitoring role name, leaf blank to '
                'disable enhanced monitoring',
    Type='String',
    Default='',
    AllowedValues=['', 'rds-monitoring-role'],
))

param_db_client_location = t.add_parameter(Parameter(
    'ClientLocation',
    Description='Lockdown database access (default can be accessed '
                'from anywhere)',
    Type='String',
    MinLength='9',
    MaxLength='18',
    Default='0.0.0.0/0',
    AllowedPattern='(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})',
    ConstraintDescription='must be a valid CIDR range of the form x.x.x.x/x.',
))

param_db_publicly_accessible = t.add_parameter(Parameter(
    'PubliclyAccessible',
    Description='Whether the database endpoint is publicly accessible',
    Type='String',
    Default='false',
    AllowedValues=['false', 'true'],
))

#
# Condition
#

t.add_condition(
    'CreateSecurityGroupCondition',
    Equals(Ref(param_sg), '')
)

t.add_condition(
    'NewDatabaseCondition',
    Equals(Ref(param_db_snapshot), ''),
)

t.add_condition(
    'UseSnapshotCondition',
    Not(Equals(Ref(param_db_snapshot), ''))
)

t.add_condition(
    'IopsStorageCondition',
    Equals(Ref(param_db_stroage_type), 'io1'),
)

t.add_condition(
    'DefaultKmsCondition',
    And(
        Equals(Ref(param_db_storage_encrypted), 'true'),
        Equals(Ref(param_db_kms_key), '')
    ),
)

t.add_condition(
    'EnhancedMonitoringCondition',
    Not(Equals(Ref(param_db_monitoring_role), '')),
)

#
# Resources
#

rds_sg = t.add_resource(ec2.SecurityGroup(
    'RdsSecurityGroup',
    Condition='CreateSecurityGroupCondition',
    VpcId=Ref(param_vpcid),
    GroupDescription='Enable local postgres access',
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='5432',
            ToPort='5432',
            CidrIp=Ref(param_db_client_location),
        )
    ],
))

subnet_group = t.add_resource(rds.DBSubnetGroup(
    'DatabaseSubnetGroup',
    DBSubnetGroupDescription='RDS subnet group',
    SubnetIds=Ref(param_subnetids)
))

rds_instance = t.add_resource(rds.DBInstance(
    'PostgresRDS',
    DeletionPolicy=Snapshot,

    # DBName=Ref(param_dbname),
    DBSnapshotIdentifier=If('UseSnapshotCondition', Ref(param_db_snapshot),
                            Ref(AWS_NO_VALUE)),
    MasterUsername=If('NewDatabaseCondition', Ref(param_db_user),
                      Ref(AWS_NO_VALUE)),
    MasterUserPassword=If('NewDatabaseCondition', Ref(param_db_password),
                          Ref(AWS_NO_VALUE)),

    Engine='postgres',
    EngineVersion=Ref(param_db_engine_version),
    DBInstanceClass=Ref(param_db_class),

    StorageType=Ref(param_db_stroage_type),
    AllocatedStorage=Ref(param_db_storage_size),
    Iops=If('IopsStorageCondition', Ref(param_db_storage_iops),
            Ref(AWS_NO_VALUE)),
    StorageEncrypted=Ref(param_db_storage_encrypted),
    KmsKeyId=If('DefaultKmsCondition', Ref(AWS_NO_VALUE),
                Ref(param_db_kms_key)),

    DBSubnetGroupName=Ref(subnet_group),
    Port='5432',
    VPCSecurityGroups=[
        If('CreateSecurityGroupCondition',
           Ref(rds_sg),
           Ref(param_sg)
           )
    ],
    PubliclyAccessible=Ref(param_db_publicly_accessible),

    MonitoringInterval=If('EnhancedMonitoringCondition', '60',
                          Ref(AWS_NO_VALUE)),
    MonitoringRoleArn=If('EnhancedMonitoringCondition',
                         Sub('arn:aws:iam::${AWS::AccountId}:role/'
                             '${EnhancedMonitoringConditionRole}'),
                         Ref(AWS_NO_VALUE)),
))

#
# Output
#
t.add_output([
    Output('EndpointAddress',
           Description='Endpoint address',
           Value=GetAtt(rds_instance, 'Endpoint.Address')
           ),
    Output('EndpointPort',
           Description='Endpoint port',
           Value=GetAtt(rds_instance, 'Endpoint.Port')
           ),
    Output('EnvironmentVariables',
           Description='Database environment variables',
           Value=Join('', [
               'PGHOST=', GetAtt(rds_instance, 'Endpoint.Address'), ' ',
               'PGPORT=', GetAtt(rds_instance, 'Endpoint.Port'), ' ',
               'PGUSER=', Ref(param_db_user), ' ',
               'PGPASSWORD=', Ref(param_db_password), ' ',
           ])),
])

#
# Write template
#

cfnutil.write(t,
              __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
