# -*- encoding: utf-8 -*-

from __future__ import print_function

__author__ = 'kotaimen'
__date__ = '11/10/2016'

from troposphere import Base64, FindInMap, GetAtt, Join, Sub, Select, Export, \
    ImportValue, Condition, GetAZs
from troposphere import And, Equals, If, Not, Or
from troposphere import Template, Parameter, Ref, Tags, Output
from troposphere import AWS_ACCOUNT_ID, AWS_REGION, AWS_STACK_ID, \
    AWS_STACK_NAME, AWS_NO_VALUE
from troposphere import Delete, Retain, Snapshot
from troposphere.policies import CreationPolicy, ResourceSignal

import troposphere.cloudformation as cloudformation
import troposphere.ec2 as ec2

import cfnutil

#
# Template
#

t = Template()

t.add_version('2010-09-09')
t.add_description(
    'VPC with specified number of public subnets'
)

#
# Interface
#
t.add_metadata(
    {
        'AWS::CloudFormation::Interface': {
            'ParameterGroups': [
                {
                    'Label': {'default': 'Availability Zone Configuration'},
                    'Parameters': [
                        'NumberOfAZs',
                        'AvailabilityZones',
                    ]
                },
                {
                    'Label': {'default': 'Network Configuration'},
                    'Parameters': [
                        'VpcCidr',
                        'PublicSubnetCidrs',
                    ]
                },
                {
                    'Label': {'default': 'Subnet Configuration'},
                    'Parameters': [
                        'AutoAssignPublicIp',
                    ]
                },
            ],
            'ParameterLabels': {
                'AvailabilityZones': {'default': 'Availability Zones'},
                'NumberOfAZs': {'default': 'Number of Availability Zones'},
                'VpcCidr': {'default': 'VPC CIDR'},
                'PublicSubnetCidrs': {'default': 'Public Subnet CIDRs'},
                'AutoAssignPublicIp': {'default': 'Auto Assign Public IP'},
            },
        }
    }
)

#
# Parameters
#

param_number_of_azs = t.add_parameter(Parameter(
    'NumberOfAZs',
    Description='Number of Availability Zones to use in the VPC. '
                'This must match your selections in the list of '
                'Availability Zones parameter.',
    Default='2',
    AllowedValues=['2', '3', '4'],
    Type='String'
))

param_availability_zones = t.add_parameter(Parameter(
    'AvailabilityZones',
    Description='List of Availability Zones to use for the subnets in the VPC.'
                'Note: The logical order is preserved.',
    Type='List<AWS::EC2::AvailabilityZone::Name>'
))

param_vpc_cidr = t.add_parameter(Parameter(
    'VpcCidr',
    Description='CIDR block for the VPC',
    Default='10.0.0.0/16',
    Type='String',
))

param_subnet_cidrs = t.add_parameter(Parameter(
    'PublicSubnetCidrs',
    Description='Comma-delimited list of public subnet CIDR blocks.',
    Default='10.0.128.0/20, 10.0.144.0/20, 10.0.160.0/20, 10.0.176.0/20',
    Type='CommaDelimitedList',
))

param_assign_public_ip = t.add_parameter(Parameter(
    'AutoAssignPublicIp',
    Description='Automatically assign instance with a Public IP.',
    AllowedValues=['true', 'false'],
    Default='true',
    Type='String'
))

#
# Conditions
#

t.add_condition(
    '4AZCondition',
    Equals(Ref(param_number_of_azs), '4')
)

t.add_condition(
    '3AZCondition',
    Or(
        Equals(Ref(param_number_of_azs), '3'),
        Condition('4AZCondition')
    )
)

#
# Resources
#

dhcp_options = t.add_resource(ec2.DHCPOptions(
    'DHCPOptions',
    DomainNameServers=['AmazonProvidedDNS']
))

vpc = t.add_resource(ec2.VPC(
    'VPC',
    CidrBlock=Ref(param_vpc_cidr),
    EnableDnsSupport='true',
    EnableDnsHostnames='true',
    Tags=Tags(Name=Ref(AWS_STACK_NAME))
))

dhcp_association = t.add_resource(ec2.VPCDHCPOptionsAssociation(
    'VPCDHCPOptionsAssociation',
    VpcId=Ref(vpc),
    DhcpOptionsId=Ref(dhcp_options),
))

internet_gateway = t.add_resource(ec2.InternetGateway(
    'InternetGateway',
    Tags=Tags(Name=Ref(AWS_STACK_NAME))
))

gateway_attachment = t.add_resource(ec2.VPCGatewayAttachment(
    'VPCGatewayAttachment',
    VpcId=Ref(vpc),
    InternetGatewayId=Ref(internet_gateway),
))

public_subnet_1 = t.add_resource(ec2.Subnet(
    'PublicSubnet1',
    VpcId=Ref(vpc),
    AvailabilityZone=Select(0,
                            Ref(param_availability_zones)),
    CidrBlock=Select(0, Ref(param_subnet_cidrs)),
    MapPublicIpOnLaunch=Ref(param_assign_public_ip),
    Tags=Tags(Name=Sub('${AWS::StackName} Public Subnet 1')),
))

public_subnet_2 = t.add_resource(ec2.Subnet(
    'PublicSubnet2',
    VpcId=Ref(vpc),
    AvailabilityZone=Select(1, Ref(param_availability_zones)),
    CidrBlock=Select(1, Ref(param_subnet_cidrs)),
    MapPublicIpOnLaunch=Ref(param_assign_public_ip),
    Tags=Tags(Name=Sub('${AWS::StackName} Public Subnet 2')),
))

public_subnet_3 = t.add_resource(ec2.Subnet(
    'PublicSubnet3',
    Condition='3AZCondition',
    VpcId=Ref(vpc),
    AvailabilityZone=Select(2, Ref(param_availability_zones)),
    CidrBlock=Select(2, Ref(param_subnet_cidrs)),
    MapPublicIpOnLaunch=Ref(param_assign_public_ip),
    Tags=Tags(Name=Sub('${AWS::StackName} Public Subnet 3')),
))

public_subnet_4 = t.add_resource(ec2.Subnet(
    'PublicSubnet4',
    Condition='4AZCondition',
    VpcId=Ref(vpc),
    AvailabilityZone=Select(3, Ref(param_availability_zones)),
    CidrBlock=Select(3, Ref(param_subnet_cidrs)),
    MapPublicIpOnLaunch=Ref(param_assign_public_ip),
    Tags=Tags(Name=Sub('${AWS::StackName} Public Subnet 4')),
))

public_subnet_routetable = t.add_resource(ec2.RouteTable(
    'PublicSubnetRouteTable',
    VpcId=Ref(vpc),
    Tags=Tags(Name='PublicSubnetRouteTable'),
))

public_subnet_route = t.add_resource(ec2.Route(
    'PublicSubnetRoute',
    RouteTableId=Ref(public_subnet_routetable),
    DestinationCidrBlock='0.0.0.0/0',
    GatewayId=Ref(internet_gateway)
))

public_subnet_1_routetable_association = t.add_resource(
    ec2.SubnetRouteTableAssociation(
        'PublicSubnet1RouteTableAssociation',
        SubnetId=Ref(public_subnet_1),
        RouteTableId=Ref(public_subnet_routetable)
    )
)

public_subnet_2_routetable_association = t.add_resource(
    ec2.SubnetRouteTableAssociation(
        'PublicSubnet2RouteTableAssociation',
        SubnetId=Ref(public_subnet_2),
        RouteTableId=Ref(public_subnet_routetable)
    )
)

public_subnet_3_routetable_association = t.add_resource(
    ec2.SubnetRouteTableAssociation(
        'PublicSubnet3RouteTableAssociation',
        Condition='3AZCondition',
        SubnetId=Ref(public_subnet_3),
        RouteTableId=Ref(public_subnet_routetable)
    )
)

public_subnet_4_routetable_association = t.add_resource(
    ec2.SubnetRouteTableAssociation(
        'PublicSubnet4RouteTableAssociation',
        Condition='4AZCondition',
        SubnetId=Ref(public_subnet_4),
        RouteTableId=Ref(public_subnet_routetable)
    )
)

public_subnet_acl = t.add_resource(ec2.NetworkAcl(
    'PublicSubnetACL',
    VpcId=Ref(vpc),
    Tags=Tags(Name='PublicSubnetACL')
))

public_subnet_acl_inbound = t.add_resource(ec2.NetworkAclEntry(
    'PublicSubnetACLIngress',
    CidrBlock='0.0.0.0/0',
    Egress='false',
    NetworkAclId=Ref(public_subnet_acl),
    Protocol='-1',
    RuleAction='allow',
    RuleNumber='100'
))

public_subnet_acl_outbound = t.add_resource(ec2.NetworkAclEntry(
    'PublicSubnetACLEgress',
    CidrBlock='0.0.0.0/0',
    Egress='true',
    NetworkAclId=Ref(public_subnet_acl),
    Protocol='-1',
    RuleAction='allow',
    RuleNumber='100'
))

public_subnet_1_acl_association = t.add_resource(
    ec2.SubnetNetworkAclAssociation(
        'PublicSubnet1ACLAssociation',
        SubnetId=Ref(public_subnet_1),
        NetworkAclId=Ref(public_subnet_acl)
    )
)

public_subnet_2_acl_association = t.add_resource(
    ec2.SubnetNetworkAclAssociation(
        'PublicSubnet2ACLAssociation',
        SubnetId=Ref(public_subnet_2),
        NetworkAclId=Ref(public_subnet_acl)
    )
)

public_subnet_3_acl_association = t.add_resource(
    ec2.SubnetNetworkAclAssociation(
        'PublicSubnet3ACLAssociation',
        Condition='3AZCondition',
        SubnetId=Ref(public_subnet_3),
        NetworkAclId=Ref(public_subnet_acl)
    )
)

public_subnet_4_acl_association = t.add_resource(
    ec2.SubnetNetworkAclAssociation(
        'PublicSubnet4ACLAssociation',
        Condition='4AZCondition',
        SubnetId=Ref(public_subnet_4),
        NetworkAclId=Ref(public_subnet_acl)
    )
)

#
# Output
#
t.add_output([
    Output('VpcId',
           Description='VPC ID',
           Value=Ref(vpc),
           Export=Export(Sub('${AWS::StackName}-VpcId')),
           ),

    Output('VpcCidr',
           Description='VPC CIDR',
           Value=GetAtt('VPC', 'CidrBlock'),
           ),

    Output('PublicSubnet1Id',
           Description='Public subnet 1 ID',
           Value=Ref('PublicSubnet1'),
           Export=Export(Sub('${AWS::StackName}-PublicSubnet1Id')),
           ),
    Output('PublicSubnet2Id',
           Description='Public subnet 2 ID',
           Value=Ref('PublicSubnet2'),
           Export=Export(Sub('${AWS::StackName}-PublicSubnet2Id')),
           ),
    Output('PublicSubnet3Id',
           Description='Public subnet 3 ID',
           Condition='3AZCondition',
           Value=Ref('PublicSubnet3'),
           Export=Export(Sub('${AWS::StackName}-PublicSubnet3Id')),
           ),
    Output('PublicSubnet4Id',
           Description='Public subnet 4 ID',
           Condition='4AZCondition',
           Value=Ref('PublicSubnet4'),
           Export=Export(Sub('${AWS::StackName}-PublicSubnet4Id')),
           ),

    Output('PublicSubnet1Az',
           Description='Public subnet 1 availability zone',
           Value=GetAtt('PublicSubnet1', 'AvailabilityZone')
           ),
    Output('PublicSubnet2Az',
           Description='Public subnet 2 availability zone',
           Value=GetAtt('PublicSubnet2', 'AvailabilityZone')
           ),
    Output('PublicSubnet3Az',
           Description='Public subnet 3 availability zone',
           Condition='3AZCondition',
           Value=GetAtt('PublicSubnet3', 'AvailabilityZone')
           ),
    Output('PublicSubnet4Az',
           Description='Public subnet 4 availability zone',
           Condition='4AZCondition',
           Value=GetAtt('PublicSubnet4', 'AvailabilityZone')
           ),

    Output('PublicSubnet1Cidr',
           Description='Public subnet 1 CIDR',
           Value=Select(0, Ref(param_subnet_cidrs))
           ),
    Output('PublicSubnet2Cidr',
           Description='Public subnet 2 CIDR',
           Value=Select(1, Ref(param_subnet_cidrs))
           ),
    Output('PublicSubnet3Cidr',
           Description='Public subnet 3 CIDR',
           Condition='3AZCondition',
           Value=Select(2, Ref(param_subnet_cidrs))
           ),
    Output('PublicSubnet4Cidr',
           Description='Public subnet 4 CIDR',
           Condition='4AZCondition',
           Value=Select(3, Ref(param_subnet_cidrs))
           ),

])

#
# Write to json
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
