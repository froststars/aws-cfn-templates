# -*- encoding: utf-8 -*-

from __future__ import print_function

__author__ = 'kotaimen'
__date__ = '01/01/2017'

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

from awacs.aws import Policy, Allow, Deny, Statement, Principal, Everybody
from awacs.aws import Condition, Bool, ArnEquals, StringEquals, IpAddress, Null
from awacs.aws import CurrentTime, EpochTime, MultiFactorAuthAge, Referer, \
    SecureTransport, SourceArn, SourceIp, UserAgent
import awacs.sts
import awacs.cloudformation
import awacs.iam
import awacs.ec2
import awacs.logs

import csv
import cfnutil
import six

#
# Template
#
t = Template()
t.add_version('2010-09-09')
t.add_description('Amazon EC2 instance running the Ubuntu Linux.')

#
# Interface
#
parameter_groups = [
    {
        'Label': {'default': 'Network Configuration'},
        'Parameters':
            [
                'VpcId',
                'SubnetId',
                'AllocateElasticIp',
                'AssociatePublicIp',
            ]
    },
    {
        'Label': {'default': 'Instance Configuration'},
        'Parameters':
            [
                'KeyName',
                'UbuntuVersion',
                'InstanceType',
                'DetailedMonitoring',
                'InstanceSecurityGroupId',
                'InstanceProfileArn',
            ]
    },
    {
        'Label': {'default': 'EBS Volume Configuration'},
        'Parameters':
            [
                'EbsOptimized',
                'Volume1Size',
                'Volume1Type',
                'Volume1Iops',
                'Volume1Device',
                'VolumeEncryptionKey',
            ]
    },
    {
        'Label': {'default': 'Security & Log Configuration'},
        'Parameters':
            [
                'SshLocation',
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
    Description='VpcId of an existing VPC',
    Type='AWS::EC2::VPC::Id',
    ConstraintDescription='must be an existing vpc id.'
))

param_subnetid = t.add_parameter(Parameter(
    'SubnetId',
    Description='SubnetId of an existing subnet in the VPC',
    Type='AWS::EC2::Subnet::Id',
    ConstraintDescription='must be an existing subnet id.'
))

param_allocate_elastic_ip = t.add_parameter(Parameter(
    'AllocateElasticIp',
    Description='Allocate a ElaticIP and assoicate it to instance',
    Type='String',
    Default='false',
    AllowedValues=['true', 'false'],
))

param_associate_public_ip = t.add_parameter(Parameter(
    'AssociatePublicIp',
    Description='Assoicate a public IP to instance, default means use subnet '
                'default setting, otherwise SSM and CloudwatchLogs won\'t '
                'initalize properly',
    Type='String',
    Default='true',
    AllowedValues=['true', 'false'],
))

param_key_name = t.add_parameter(Parameter(
    'KeyName',
    Description='Name of an existing EC2 KeyPair to enable SSH access',
    Type='AWS::EC2::KeyPair::KeyName',
    ConstraintDescription='must be the name of an existing EC2 KeyPair.'
))

param_ubuntu_version = t.add_parameter(Parameter(
    'UbuntuVersion',
    Description='Ubuntu version (only LTS are allowed)',
    Type='String',
    Default='xenial',
    AllowedValues=['xenial', 'trusty'],
))

param_instance_type = t.add_parameter(Parameter(
    'InstanceType',
    Description='EC2 instance type',
    Type='String',
    Default='t2.small',
    AllowedValues=sorted(six.iterkeys(cfnutil.load_mapping(
        'mapping/ec2-instance-type-to-arch.json'))),
    ConstraintDescription='must be a valid EC2 instance type.'
))

param_detailed_monitoring = t.add_parameter(Parameter(
    'DetailedMonitoring',
    Description='Whether uses detailed 1 minute monitoring interval, which '
                'requires additional charge',
    Type='String',
    Default='false',
    AllowedValues=['true', 'false'],
))

param_instance_profile = t.add_parameter(Parameter(
    'InstanceProfileArn',
    Description='Arn of instance profile, a new instance role and instance '
                'profile will be created if this is left empty.',
    Type='String',
    Default='',
))

param_instance_sg = t.add_parameter(Parameter(
    'InstanceSecurityGroupId',
    Description='Instance security group id, a new security group will be '
                'created this is left empty.',
    Type='String',
    Default='',
))

param_ebs_optimized = t.add_parameter(Parameter(
    'EbsOptimized',
    Description='Whether instance is EBS optimized, default means use default '
                'value of selected instance type',
    Type='String',
    Default='default',
    AllowedValues=['default', 'true', 'false'],
))

param_volume1_size = t.add_parameter(Parameter(
    'Volume1Size',
    Description='Size of the EBS volume in GB, "0" disables volume creation',
    Type='Number',
    Default='0',
    MinValue='0',
    MaxValue='16384',
    ConstraintDescription='1-16384 for gp2, 4-16384 for io1, 500-16384 for st1,'
                          '500-16384 for sc1, and 1-1024 for standard'
))

param_volume1_type = t.add_parameter(Parameter(
    'Volume1Type',
    Description='EBS volume type',
    Type='String',
    Default='gp2',
    AllowedValues=['gp2', 'io1', 'st1', 'sc1', 'standard'],
))

param_volume1_iops = t.add_parameter(Parameter(
    'Volume1Iops',
    Description='IOPS the volume supports, used when the volume type is io1',
    Type='Number',
    Default='100',
    MinValue='100',
    MaxValue='20000',
    ConstraintDescription='Range is 100 to 20000 for Provisioned IOPS '
                          'SSD volumes, with a maximum ratio of 50 IOPS/GiB'
))

param_volume1_device = t.add_parameter(Parameter(
    'Volume1Device',
    Description='Volume device name',
    Type='String',
    Default='/dev/xvdf',
    AllowedValues=list('/dev/xvd%s' % ch for ch in 'fghijklmnop'),
))

param_volume_key = t.add_parameter(Parameter(
    'VolumeEncryptionKey',
    Description='KMS key arn of the volume for data encryption, leave blank '
                'means don\'t use volume SSE, please note previous '
                'generation instances and t2.* instances don\'t suport '
                'encrypted volumes',
    Type='String',
    Default='',
))

param_ssh_location = t.add_parameter(Parameter(
    'SshLocation',
    Description='Lockdown SSH access to the EC2 instance (default can be '
                'accessed from anywhere)',
    Type='String',
    MinLength='9',
    MaxLength='18',
    Default='0.0.0.0/0',
    AllowedPattern='(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})',
    ConstraintDescription='must be a valid CIDR range of the form x.x.x.x/x.',
))


#
# Mapping
#

def load_ubuntu_ami(filename):
    """ See: http://cloud-images.ubuntu.com/locator/ec2/ """
    ubuntu_amis = dict()
    with open(filename) as f:
        reader = csv.DictReader(f)
        for d in reader:
            if d['Zone'] not in ubuntu_amis:
                ubuntu_amis[d['Zone']] = dict()
            ubuntu_amis[d['Zone']][d['Name']] = d['AMI-ID']
    return ubuntu_amis


t.add_mapping(
    'UbuntuAMIs',
    load_ubuntu_ami('mapping/ubuntu-hvm-amis.csv')
)

#
# Condition
#
t.add_condition(
    'DefaultEbsOptimizationCondition',
    Equals(Ref(param_ebs_optimized), 'default'),
)

t.add_condition(
    'AllocateElasticIpCondition',
    Equals(Ref(param_allocate_elastic_ip), 'true'),
)

t.add_condition(
    'PublicIpCondition',
    Or(
        Equals(Ref(param_associate_public_ip), 'true'),
        Equals(Ref(param_allocate_elastic_ip), 'true'),
    )
)

t.add_condition(
    'CreateInstanceProfileCondition',
    Equals(Ref(param_instance_profile), '')
)

t.add_condition(
    'CreateSecurityGroupCondition',
    Equals(Ref(param_instance_sg), '')
)

t.add_condition(
    'Volume1Condition',
    Not(Equals(Ref(param_volume1_size), '0')),
)

t.add_condition(
    'Volume1IopsOptimizedCondition',
    Equals(Ref(param_volume1_type), 'io1'),
)

t.add_condition(
    'VolumeEncryptedCondition',
    Not(Equals(Ref(param_volume_key), ''))
)

#
# Resources
#


instance_ssh_sg = t.add_resource(ec2.SecurityGroup(
    'SshSecurityGroup',
    VpcId=Ref(param_vpcid),
    GroupDescription='Enable SSH access via port 22',
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol='tcp',
            FromPort='22',
            ToPort='22',
            CidrIp=Ref(param_ssh_location),
        ),
    ],
))


instance_role = t.add_resource(iam.Role(
    'InstanceRole',
    AssumeRolePolicyDocument=Policy(
        Statement=[Statement(
            Effect=Allow,
            Action=[awacs.sts.AssumeRole],
            Principal=Principal('Service', [
                Sub('ec2.${AWS::URLSuffix}'),
            ])
        )]
    ),
    ManagedPolicyArns=[
    ],
    Policies=[
    ]
))

instance_profile = t.add_resource(iam.InstanceProfile(
    'InstanceProfile',
    Roles=[
        Ref(instance_role)
    ],
))

instance_resource_name = 'UbuntuInstance'

instance_user_data = Base64(Sub('''#!/bin/bash -xe
sudo apt-get -yq update
sudo apt-get -yq install python-setuptools python-pip

# Install cfn-tools
sudo pip install https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz
sudo cp /usr/local/init/ubuntu/cfn-hup /etc/init.d/cfn-hup
sudo chmod +x /etc/init.d/cfn-hup
sudo update-rc.d cfn-hup defaults

# Run cfn-init
cfn-init -v --stack ${AWS::StackName} --resource %(INSTANCE_NAME)s --configsets Bootstrap --region ${AWS::Region}
cfn-signal -e $? --stack ${AWS::StackName} --resource %(INSTANCE_NAME)s --region ${AWS::Region}

# Install Simple System Manager
# cd /tmp
# sudo curl https://amazon-ssm-${AWS::Region}.s3.amazonaws.com/latest/debian_amd64/amazon-ssm-agent.deb -o amazon-ssm-agent.deb
# sudo dpkg -i amazon-ssm-agent.deb
# sudo start amazon-ssm-agent

''' % {'INSTANCE_NAME': instance_resource_name}))

instance_metadata = cloudformation.Metadata(
    cloudformation.Init(
        cloudformation.InitConfigSets(
            Bootstrap=[
                'ConfigCFNTools',
                'InstallAWSTools',
                'InstallPackages',
            ],
            Update=[
                'ConfigCFNTools',
                'InstallAWSTools',
                'InstallPackages',
            ],
        ),
        ConfigCFNTools=cloudformation.InitConfig(
            files={
                '/etc/cfn/cfn-hup.conf': {
                    'content': Sub(
                        '[main]\n'
                        'stack=${AWS::StackId}\n'
                        'region=${AWS::Region}\n'
                        'interval=5\n'
                        'verbose=false\n'
                    ),
                    'mode': '000400',
                    'owner': 'root',
                    'group': 'root',
                },
                '/etc/cfn/hooks.d/cfn-auto-reloader.conf': {
                    'content': Sub(
                        '[cfn-auto-reloader-hook]\n'
                        'triggers=post.update\n'
                        'path=Resources.%(INSTANCE_NAME)s.Metadata.AWS::CloudFormation::Init\n'
                        'action=/opt/aws/bin/cfn-init -v'
                        '    --stack ${AWS::StackName}'
                        '    --resource %(INSTANCE_NAME)s'
                        '    --configsets Update'
                        '    --region ${AWS::Region}'
                        '\n'
                        'runas=root\n' % \
                        dict(INSTANCE_NAME=instance_resource_name)
                    ),
                },
            },
            services={
                'sysvinit': cloudformation.InitServices(
                    {
                        'cfn-hup': cloudformation.InitService(
                            enabled=True,
                            ensureRunning=True,
                            files=[
                                '/etc/cfn/cfn-hup.conf',
                                '/etc/cfn/hooks.d/cfn-auto-reloader.conf',
                            ]
                        ),
                    }
                )
            },
        ),
        InstallAWSTools=cloudformation.InitConfig(
            packages={
                'apt': {
                    'python-pip': [],
                },
                'python': {
                    'awscli': []
                },
            },
            files={
                '/home/ubuntu/.aws/config': {
                    'content': Sub(
                        '[default]\n'
                        's3 =\n'
                        '    signature_version = s3v4\n'
                        'region = ${AWS::Region}\n'
                    ),
                    'owner': 'ubuntu',
                    'group': 'ubuntu',
                },
            },
            commands={
            },
        ),
        InstallPackages=cloudformation.InitConfig(
            # packages={
            #     'apt': {
            #         'nginx': [],
            #     }
            # },
            # services={'sysvinit': cloudformation.InitServices(
            #     {
            #         'nginx': cloudformation.InitService(
            #             enabled=True,
            #             ensureRunning=True,
            #             files=[
            #                 '/etc/nginx/nginx.conf',
            #             ]
            #         ),
            #     }
            # )},
        ),
    )
)

ubuntu_instance = t.add_resource(ec2.Instance(

    instance_resource_name,

    ImageId=FindInMap('UbuntuAMIs', Ref(AWS_REGION), Ref(param_ubuntu_version)),

    InstanceType=Ref(param_instance_type),
    KeyName=Ref(param_key_name),
    NetworkInterfaces=[ec2.NetworkInterfaceProperty(
        DeviceIndex='0',
        GroupSet=[
            If('CreateSecurityGroupCondition',
               Ref(instance_ssh_sg),
               Ref(param_instance_sg)
               )
        ],
        AssociatePublicIpAddress=Ref(param_associate_public_ip),
        DeleteOnTermination='true',
        SubnetId=Ref(param_subnetid),
    )],
    IamInstanceProfile=If('CreateInstanceProfileCondition',
                          Ref(instance_profile),
                          Ref(param_instance_profile)
                          ),
    Metadata=instance_metadata,
    UserData=instance_user_data,
    CreationPolicy=CreationPolicy(
        ResourceSignal=ResourceSignal(Timeout='PT5M')
    ),
    EbsOptimized=If('DefaultEbsOptimizationCondition',
                    Ref(AWS_NO_VALUE),
                    Ref(param_ebs_optimized)),
    Monitoring=Ref(param_detailed_monitoring),
    Tags=Tags(Name=Ref(AWS_STACK_NAME)),
))

volume1 = t.add_resource(ec2.Volume(
    'Volume1',
    Condition='Volume1Condition',
    # DeletionPolicy=Retain,
    AvailabilityZone=GetAtt(ubuntu_instance, 'AvailabilityZone'),
    VolumeType=Ref(param_volume1_type),
    Size=Ref(param_volume1_size),
    Iops=If('Volume1IopsOptimizedCondition',
            Ref(param_volume1_iops),
            Ref(AWS_NO_VALUE)),
    Encrypted=If('VolumeEncryptedCondition', 'true', 'false'),
    KmsKeyId=If('VolumeEncryptedCondition',
                Ref(param_volume_key),
                Ref(AWS_NO_VALUE)),
    Tags=Tags(Name=Ref(AWS_STACK_NAME)),
))

volume1_attachment = t.add_resource(ec2.VolumeAttachment(
    'Volume1Attachment',
    Condition='Volume1Condition',
    Device=Ref(param_volume1_device),
    InstanceId=Ref(ubuntu_instance),
    VolumeId=Ref(volume1),
))

eip = t.add_resource(ec2.EIP(
    'ElasticIP',
    # only create elastic ip after instance creation
    DependsOn=instance_resource_name,
    Condition='AllocateElasticIpCondition',
    Domain='vpc',
))

eip_association = t.add_resource(ec2.EIPAssociation(
    'EIPAssociation',
    Condition='AllocateElasticIpCondition',
    AllocationId=GetAtt(eip, 'AllocationId'),
    InstanceId=Ref(ubuntu_instance),
))

#
# Output
#
t.add_output([
    Output('PrivateIp',
           Description='Instance private IP address',
           Value=GetAtt(ubuntu_instance, 'PrivateIp'),
           ),
    Output('PublicIp',
           Condition='PublicIpCondition',
           Description='Public IP address',
           Value=GetAtt(ubuntu_instance, 'PublicIp'),
           ),
    Output('InstanceId',
           Description='EC2 Instance Id',
           Value=Ref(ubuntu_instance),
           ),
    Output('Volume1Id',
           Condition='Volume1Condition',
           Description='Volume 1 Id',
           Value=Ref(volume1),
           ),
])

#
# Write template
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
