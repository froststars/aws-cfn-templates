# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '04/12/2016'

from troposphere import Base64, FindInMap, GetAtt, Join, Select, Sub, Split
from troposphere import ImportValue, Export
from troposphere import Condition, And, Equals, If, Not, Or
from troposphere import Template, Parameter, Ref, Tags, Output
from troposphere import AWS_ACCOUNT_ID, AWS_REGION, AWS_STACK_ID, \
    AWS_STACK_NAME, AWS_NO_VALUE, AWS_URL_SUFFIX, AWS_PARTITION
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
t.add_description('Creates a simple amazon RDS database instance with default '
                  'database parameters and optional encryption, iops storage, '
                  'multi-az deployment and read replicas in same region.')

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
                'DatabaseEngine',
                'DatabaseEngineVersion',
                'DatabaseParameterGroupFamily',
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
                'ClientLocation',
                'PubliclyAccessible',
            ]
    },
    {
        'Label': {'default': 'Database Replication Configuration'},
        'Parameters':
            [
                'DatabaseReplication',
            ]
    },
    {

        'Label': {'default': 'Database Monitoring Configuration'},
        'Parameters':
            [
                'EnhancedMonitoringInterval',
                'SnsTopicArn',
            ]

    }
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

# https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html
param_db_class = t.add_parameter(Parameter(
    'DatabaseClass',
    Default='db.t2.micro',
    Description='Database instance class',
    Type='String',
    AllowedValues=cfnutil.load_mapping('mapping/rds-instance-types.json'),
))

param_db_engine = t.add_parameter(Parameter(
    'DatabaseEngine',
    Default='postgres',
    Description='Database engine',
    Type='String',
    AllowedValues=['postgres',
                   'mysql',
                   'mariadb'],
))

# https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_CreateDBInstance.html
param_db_engine_version = t.add_parameter(Parameter(
    'DatabaseEngineVersion',
    Default='postgres-9.6.6',
    Description='Database engine version, must be a version matches '
                'specified database engine.',
    Type='String',
    AllowedValues=cfnutil.load_mapping('mapping/rds-versions.json'),
))

param_db_param_group_family = t.add_parameter(Parameter(
    'DatabaseParameterGroupFamily',
    Default='postgres9.6',
    Description='Database parameter group family',
    Type='String',
    AllowedValues=cfnutil.load_mapping('mapping/rds-parameter-groups.json')
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
    ConstraintDescription=('must begin with a letter and contain only '
                           'alphanumeric characters.')
))

param_db_password = t.add_parameter(Parameter(
    'DatabasePassword',
    NoEcho=True,
    Description='The database admin account password, ignored when a snapshot '
                'is specified',
    Type='String',
    MinLength='1',
    MaxLength='41',
    # AllowedPattern='[a-zA-Z0-9]*',
    # ConstraintDescription='must contain only alphanumeric characters.'
))

param_db_multi_az = t.add_parameter(Parameter(
    'DatabaseMultiAz',
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
    Description='IOPS capability of the database storage, only used when the '
                'volume type is io1',
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
                'don\'t specify this property, this template uses the '
                'default master key.',
    Default='',
    Type='String'
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

param_db_read_replica = t.add_parameter(Parameter(
    'DatabaseReadReplicas',
    Description='Number of read replicas of the master database, set to 0 '
                'disables read replica, please note not all RDS engines '
                'supports read replica.',
    Type='String',
    Default='0',
    AllowedValues=['0', '1', '2', '3'],
))

param_db_enhanced_monitoring_interval = t.add_parameter(Parameter(
    'EnhancedMonitoringInterval',
    Description='Interval, in seconds, between points when Enhanced Monitoring '
                'metrics are collected for the DB instance, set to 0 disables '
                'enhanced monitoring.',
    Type='String',
    Default='0',
    AllowedValues=['0', '1', '5', '10', '15', '30', '60']
))

param_sns_topic_arn = t.add_parameter(Parameter(
    'SnsTopicArn',
    Description='ARN of an SNS topic that database send event notifications '
                'are sent to, set this to blank disables event notification.',
    Type='String',
    Default=''
))

#
# Condition
#
conditions = [
    (
        'CreateSecurityGroupCondition',
        Equals(Ref(param_sg), '')
    ),
    (
        'PostgresCondition',
        Equals(Ref(param_db_engine), 'postgres'),
    ),
    (
        'MysqlCondition',
        Equals(Ref(param_db_engine), 'mysql'),
    ),
    (
        'MariadbCondition',
        Equals(Ref(param_db_engine), 'mariadb'),
    ),
    (
        'OrcaleCondition',
        Or(
            Equals(Ref(param_db_engine), 'oracle-se1'),
            Equals(Ref(param_db_engine), 'oracle-se2'),
        )
    ),
    (
        'NewDatabaseCondition',
        Equals(Ref(param_db_snapshot), ''),
    ),
    (
        'UseSnapshotCondition',
        Not(Equals(Ref(param_db_snapshot), ''))
    ),
    (
        'IopsStorageCondition',
        Equals(Ref(param_db_stroage_type), 'io1'),
    ),
    (
        'StorageEncryptedConditon',
        Equals(Ref(param_db_storage_encrypted), 'true'),
    ),
    (
        'DefaultKmsCondition',
        Equals(Ref(param_db_kms_key), '')
    ),
    # (
    #     'ChinaRegionCondition',
    #     Equals(Ref(AWS_REGION), 'cn-north-1')
    # ),
    (
        'EnhancedMonitoringCondition',
        Not(Equals(Ref(param_db_enhanced_monitoring_interval), '0')),
    ),
    (
        'DatabaseReadReplicaCondition1',
        Or(
            Equals(Ref(param_db_read_replica), '1'),
            Equals(Ref(param_db_read_replica), '2'),
            Equals(Ref(param_db_read_replica), '3'),
        )
    ),
    (
        'DatabaseReadReplicaCondition2',
        Or(
            Equals(Ref(param_db_read_replica), '2'),
            Equals(Ref(param_db_read_replica), '3'),
        )
    ),
    (
        'DatabaseReadReplicaCondition3',
        Equals(Ref(param_db_read_replica), '3')

    ),
    (
        'EventNotificationCondition',
        Not(Equals(Ref(param_sns_topic_arn), ''))
    )
]

for args in conditions:
    t.add_condition(*args)

#
# Resources
#

rds_sg = t.add_resource(ec2.SecurityGroup(
    'RdsSecurityGroup',
    Condition='CreateSecurityGroupCondition',
    VpcId=Ref(param_vpcid),
    GroupDescription='Enable local postgres access',
    SecurityGroupIngress=[
        If('PostgresCondition',
           ec2.SecurityGroupRule(
               IpProtocol='tcp',
               FromPort='5432',
               ToPort='5432',
               CidrIp=Ref(param_db_client_location),
           ),
           Ref(AWS_NO_VALUE)),
        If('MysqlCondition',
           ec2.SecurityGroupRule(
               IpProtocol='tcp',
               FromPort='3306',
               ToPort='3306',
               CidrIp=Ref(param_db_client_location),
           ),
           Ref(AWS_NO_VALUE)),
        If('MariadbCondition',
           ec2.SecurityGroupRule(
               IpProtocol='tcp',
               FromPort='3306',
               ToPort='3306',
               CidrIp=Ref(param_db_client_location),
           ),
           Ref(AWS_NO_VALUE)),
        If('OrcaleCondition',
           ec2.SecurityGroupRule(
               IpProtocol='tcp',
               FromPort='1521',
               ToPort='1521',
               CidrIp=Ref(param_db_client_location),
           ),
           Ref(AWS_NO_VALUE)),
    ],
))

subnet_group = t.add_resource(rds.DBSubnetGroup(
    'DatabaseSubnetGroup',
    DBSubnetGroupDescription='RDS subnet group',
    SubnetIds=Ref(param_subnetids)
))

param_group = t.add_resource(rds.DBParameterGroup(
    'DatabaseParameterGroup',
    Description='RDS parameter group',
    Family=Ref(param_db_param_group_family),
))

enhanced_monitoring_role = t.add_resource(iam.Role(
    'EnhancedMonitoringRole',
    Condition='EnhancedMonitoringCondition',
    AssumeRolePolicyDocument=Policy(
        Statement=[Statement(
            Effect=Allow,
            Action=[awacs.sts.AssumeRole],
            Principal=Principal(
                'Service', Sub('monitoring.rds.${AWS::URLSuffix}')
            ))
        ]),
    ManagedPolicyArns=[
        Sub(
            'arn:${AWS::Partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole')
    ],
))

rds_instance = t.add_resource(rds.DBInstance(
    'RdsInstance',
    # DeletionPolicy=Retain,

    # DBName=Ref(param_dbname),
    DBSnapshotIdentifier=If('UseSnapshotCondition', Ref(param_db_snapshot),
                            Ref(AWS_NO_VALUE)),
    MasterUsername=If('NewDatabaseCondition', Ref(param_db_user),
                      Ref(AWS_NO_VALUE)),
    MasterUserPassword=If('NewDatabaseCondition', Ref(param_db_password),
                          Ref(AWS_NO_VALUE)),

    Engine=Ref(param_db_engine),
    LicenseModel=If('OrcaleCondition', 'license-included', Ref(AWS_NO_VALUE)),
    EngineVersion=Select(1, Split('-', Ref(param_db_engine_version))),
    AllowMajorVersionUpgrade=False,
    AutoMinorVersionUpgrade=True,
    DBInstanceClass=Ref(param_db_class),

    MultiAZ=Ref(param_db_multi_az),
    StorageType=Ref(param_db_stroage_type),
    AllocatedStorage=Ref(param_db_storage_size),
    Iops=If('IopsStorageCondition', Ref(param_db_storage_iops),
            Ref(AWS_NO_VALUE)),
    StorageEncrypted=Ref(param_db_storage_encrypted),
    KmsKeyId=If('StorageEncryptedConditon',
                If('DefaultKmsCondition',
                   Ref(AWS_NO_VALUE),
                   Ref(param_db_kms_key)),
                Ref(AWS_NO_VALUE),
                ),

    DBSubnetGroupName=Ref(subnet_group),

    DBParameterGroupName=Ref(param_group),

    VPCSecurityGroups=[
        If(
            'CreateSecurityGroupCondition',
            Ref(rds_sg),
            Ref(param_sg)
        )
    ],
    PubliclyAccessible=Ref(
        param_db_publicly_accessible),

    MonitoringInterval=If(
        'EnhancedMonitoringCondition',
        Ref(param_db_enhanced_monitoring_interval),
        Ref(AWS_NO_VALUE)),
    MonitoringRoleArn=If(
        'EnhancedMonitoringCondition',
        GetAtt(enhanced_monitoring_role, 'Arn'),
        Ref(AWS_NO_VALUE)),

    BackupRetentionPeriod=30,
    CopyTagsToSnapshot=True,
))

for n in [1, 2, 3]:
    t.add_resource(rds.DBInstance(
        'RdsReadReplicaInstance%d' % n,
        Condition='DatabaseReadReplicaCondition%d' % n,
        DependsOn='RdsInstance',
        SourceDBInstanceIdentifier=Ref(rds_instance),
        Engine=Ref(param_db_engine),
        EngineVersion=Select(1, Split('-', Ref(param_db_engine_version))),
        AllowMajorVersionUpgrade=False,
        AutoMinorVersionUpgrade=True,
        DBInstanceClass=Ref(param_db_class),
        StorageType=Ref(param_db_stroage_type),
        AllocatedStorage=Ref(param_db_storage_size),
        Iops=If('IopsStorageCondition', Ref(param_db_storage_iops),
                Ref(AWS_NO_VALUE)),
        StorageEncrypted=Ref(param_db_storage_encrypted),
        KmsKeyId=If('StorageEncryptedConditon',
                    If('DefaultKmsCondition',
                       Ref(AWS_NO_VALUE),
                       Ref(param_db_kms_key)),
                    Ref(AWS_NO_VALUE),
                    ),
        VPCSecurityGroups=[
            If(
                'CreateSecurityGroupCondition',
                Ref(rds_sg),
                Ref(param_sg)
            )
        ],
        PubliclyAccessible=Ref(
            param_db_publicly_accessible),
        MonitoringInterval=If(
            'EnhancedMonitoringCondition',
            Ref(param_db_enhanced_monitoring_interval),
            Ref(AWS_NO_VALUE)),
        MonitoringRoleArn=If(
            'EnhancedMonitoringCondition',
            GetAtt(enhanced_monitoring_role, 'Arn'),
            Ref(AWS_NO_VALUE)),
    ))

instance_event_subscription = t.add_resource(rds.EventSubscription(
    'InstanceEventSubscription',
    Condition='EventNotificationCondition',
    Enabled=True,
    SnsTopicArn=Ref(param_sns_topic_arn),
    SourceType='db-instance',
    SourceIds=[
        Ref(rds_instance),
        If('DatabaseReadReplicaCondition1', Ref('RdsReadReplicaInstance1'),
           Ref(AWS_NO_VALUE)),
        If('DatabaseReadReplicaCondition2', Ref('RdsReadReplicaInstance2'),
           Ref(AWS_NO_VALUE)),
        If('DatabaseReadReplicaCondition3', Ref('RdsReadReplicaInstance3'),
           Ref(AWS_NO_VALUE)),
    ]
))

# security_group_event_subscription = t.add_resource(rds.EventSubscription(
#     'SecurityGroupEventSubscription',
#     Condition='EventNotificationCondition',
#     Enabled=True,
#     SnsTopicArn=Ref(param_sns_topic_arn),
#     SourceType='db-security-group',
#     SourceIds=[
#         If(
#             'CreateSecurityGroupCondition',
#             Ref(rds_sg),
#             Ref(param_sg)
#         )]
# ))

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
    Output('DBInstanceIdentifier',
           Description='Database instance identifier',
           Value=Ref(rds_instance)
           ),
    Output('Replica1EndpointAddress',
           Condition='DatabaseReadReplicaCondition1',
           Description='Endpoint address',
           Value=GetAtt('RdsReadReplicaInstance1', 'Endpoint.Address')
           ),
    Output('Replica1EndpointPort',
           Condition='DatabaseReadReplicaCondition1',
           Description='Endpoint port',
           Value=GetAtt('RdsReadReplicaInstance1', 'Endpoint.Port')
           ),
    Output('Replica1InstanceIdentifier',
           Condition='DatabaseReadReplicaCondition1',
           Description='Database instance identifier',
           Value=Ref('RdsReadReplicaInstance1')
           ),
    Output('Replica2EndpointAddress',
           Condition='DatabaseReadReplicaCondition2',
           Description='Endpoint address',
           Value=GetAtt('RdsReadReplicaInstance2', 'Endpoint.Address')
           ),
    Output('Replica2EndpointPort',
           Condition='DatabaseReadReplicaCondition2',
           Description='Endpoint port',
           Value=GetAtt('RdsReadReplicaInstance2', 'Endpoint.Port')
           ),
    Output('Replica2InstanceIdentifier',
           Condition='DatabaseReadReplicaCondition2',
           Description='Database instance identifier',
           Value=Ref('RdsReadReplicaInstance2')
           ),
    Output('Replica3EndpointAddress',
           Condition='DatabaseReadReplicaCondition3',
           Description='Endpoint address',
           Value=GetAtt('RdsReadReplicaInstance3', 'Endpoint.Address')
           ),
    Output('Replica3EndpointPort',
           Condition='DatabaseReadReplicaCondition3',
           Description='Endpoint port',
           Value=GetAtt('RdsReadReplicaInstance3', 'Endpoint.Port')
           ),
    Output('Replica3InstanceIdentifier',
           Condition='DatabaseReadReplicaCondition3',
           Description='Database instance identifier',
           Value=Ref('RdsReadReplicaInstance3')
           ),
    # Output('EnvironmentVariables',
    #        Description='Database environment variables',
    #        Value=Join('', [
    #            'PGHOST=', GetAtt(rds_instance, 'Endpoint.Address'), ' ',
    #            'PGPORT=', GetAtt(rds_instance, 'Endpoint.Port'), ' ',
    #            'PGUSER=', Ref(param_db_user), ' ',
    #            'PGPASSWORD=', Ref(param_db_password), ' ',
    #        ])),
])

#
# Write template
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'))
