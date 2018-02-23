# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '26/04/2017'

from troposphere import Base64, FindInMap, GetAtt, Join, Select, Sub, \
    ImportValue, Export
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
import troposphere.elasticbeanstalk as beanstalk
import troposphere.route53 as route53

from awacs.aws import Policy, Allow, Deny, Statement, Principal
from awacs.aws import Condition, Bool

import six
import cfnutil

#
# Template
#

t = Template()
t.add_version()
t.add_description(
    'Simple Beanstalk WebServer application using application load balancer'
)

#
# Interface
#
parameter_groups = [
    {
        'Label': {'default': 'Network Configuration'},
        'Parameters': [
            'VpcId',
            'PublicSubnet1',
            'PublicSubnet2',
            'PrivateSubnet1',
            'PrivateSubnet2',
            'LoadBalancerVisibility',
        ],
    },
    {
        'Label': {'default': 'Security & Role'},
        'Parameters': [
            'LoadBalancerSecurityGroup',
            'InstanceSecurityGroup',
            'ServiceRole',
            'InstanceProfile',
        ],
    },
    {
        'Label': {'default': 'Beanstalk Configuration'},
        'Parameters':
            [
                'SolutionStackName',
                'SourceBucket',
                'SourceBundle',
                'Certificate',
                'InstanceType',
                'HealthCheckUrl',
                'MinInstances',
                'MaxInstances',
                'LogRetention',
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
param_vpc_id = t.add_parameter(Parameter(
    'VpcId',
    Description='VPC ID',
    Type='AWS::EC2::VPC::Id',
))

param_public_subnet_1 = t.add_parameter(Parameter(
    'PublicSubnet1',
    Description='Public subnet 1 ID',
    Type='AWS::EC2::Subnet::Id'
))

param_public_subnet_2 = t.add_parameter(Parameter(
    'PublicSubnet2',
    Description='Public subnet 2 ID',
    Type='AWS::EC2::Subnet::Id'
))

param_private_subnet_1 = t.add_parameter(Parameter(
    'PrivateSubnet1',
    Description='Private subnet 1 ID',
    Type='AWS::EC2::Subnet::Id'
))

param_private_subnet_2 = t.add_parameter(Parameter(
    'PrivateSubnet2',
    Description='Private subnet 2 ID',
    Type='AWS::EC2::Subnet::Id'
))

param_lb_visibility = t.add_parameter(Parameter(
    'LoadBalancerVisibility',
    Description='Load balancer visibility',
    Default='public',
    Type='String',
    AllowedValues=['public', 'internal']
))

param_lb_sg = t.add_parameter(Parameter(
    'LoadBalancerSecurityGroup',
    Description='Load balancer security group',
    Type='AWS::EC2::SecurityGroup::Id',
))

param_instance_sg = t.add_parameter(Parameter(
    'InstanceSecurityGroup',
    Description='InstanceSecurityGroup',
    Type='AWS::EC2::SecurityGroup::Id',
))

param_service_role = t.add_parameter(Parameter(
    'ServiceRole',
    Description='Beanstalk service role ARN',
    Type='String',
))

param_instance_profile = t.add_parameter(Parameter(
    'InstanceProfile',
    Description='EC2 instance profile ARN',
    Type='String',
))

# See http://docs.aws.amazon.com/elasticbeanstalk/latest/dg/concepts.platforms.html
# aws elasticbeanstalk list-available-solution-stacks
param_solution_stack = t.add_parameter(Parameter(
    'SolutionStackName',
    Description='Elastic beans tack ',
    Default='',
    Type='String',
    MinLength=0,
    MaxLength=128,
    ConstraintDescription='must be a valid stack name.'
))

param_source_bucket = t.add_parameter(Parameter(
    'SourceBucket',
    Description='Application source bundle bucket',
    Default='Bucket',
    Type='String',
    MinLength=1,
))

param_source_bundle = t.add_parameter(Parameter(
    'SourceBundle',
    Description='Application source bundle prefix',
    Default='app.zip',
    Type='String',
    MinLength=1,
))

param_certificate = t.add_parameter(Parameter(
    'Certificate',
    Description='ARN of IAM or ACM certificate to bind to LB',
    Type='String',
    Default='',
    # AllowedPattern=r'^arn:aws:(acm|iam).*',
))

param_instance_type = t.add_parameter(Parameter(
    'InstanceType',
    Description='EC2 instance type',
    Type='String',
    Default='t2.small',
    AllowedValues=list(six.iterkeys(
        cfnutil.load_mapping('EC2/mapping/ec2-instance-type-to-arch.json'))),
    ConstraintDescription='must be a valid EC2 instance type.'
))

param_health_check = t.add_parameter(Parameter(
    'HealthCheckUrl',
    Description='Health check URL',
    Type='String',
    Default='/',
))

param_min_instances = t.add_parameter(Parameter(
    'MinInstances',
    Description='Minimum number of instances',
    Type='Number',
    MinValue='1',
    Default='1'
))

param_max_instances = t.add_parameter(Parameter(
    'MaxInstances',
    Description='Max number of instances',
    Type='Number',
    MinValue='1',
    Default='2'
))

param_log_retention = t.add_parameter(Parameter(
    'LogRetention',
    Type='Number',
    Description='The number of days log events are kept in CloudWatch Logs.',
    AllowedValues=[-1, 1, 3, 5, 7, 14, 30, 60, 90, 120, 150,
                   180, 365, 400, 545, 731, 1827, 3653],
    Default='30'
))

#
# Condition
#
t.add_condition(
    'InternalLoadBalancerCondition',
    Equals(Ref(param_lb_visibility), 'internal'),
)
t.add_condition(
    'HttpsCertificateCondition',
    Not(Equals(Ref(param_certificate), '')),
)

#
# Resources
#

eb_app = t.add_resource(beanstalk.Application(
    'Application',
    Description=Sub('Stack=${AWS::StackName}')
))

# See http://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options-general.html
CONFIG_TEMPLATE = [

    # === Environment ===

    ('aws:elasticbeanstalk:environment', 'EnvironmentType', 'LoadBalanced'),
    ('aws:elasticbeanstalk:environment', 'ServiceRole', Ref(param_service_role)),
    ('aws:elasticbeanstalk:environment', 'LoadBalancerType', 'application'),

    # === Networking ===
    ('aws:ec2:vpc', 'VPCId', Ref(param_vpc_id)),

    ('aws:ec2:vpc', 'ELBSubnets',
     If('InternalLoadBalancerCondition',
        Join(',', [Ref(param_private_subnet_1), Ref(param_private_subnet_2)]),
        Join(',', [Ref(param_public_subnet_1), Ref(param_public_subnet_2)]),
        )
     ),

    ('aws:ec2:vpc', 'Subnets',
     Join(',', [Ref(param_private_subnet_1), Ref(param_private_subnet_2)]),
     ),

    ('aws:ec2:vpc', 'AssociatePublicIpAddress', 'false'),
    ('aws:ec2:vpc', 'ELBScheme',
     If('InternalLoadBalancerCondition', 'internal', Ref(AWS_NO_VALUE))
     ),

    # === Application ===
    ('aws:elasticbeanstalk:application', 'Application Healthcheck URL',
     Ref(param_health_check)),
    ('aws:elasticbeanstalk:healthreporting:system', 'SystemType', 'enhanced'),

    # === Autoscaling ===
    ('aws:autoscaling:asg', 'Availability Zones', 'Any 2'),
    ('aws:autoscaling:asg', 'MinSize', Ref(param_min_instances)),
    ('aws:autoscaling:asg', 'MaxSize', Ref(param_max_instances)),

    ('aws:autoscaling:launchconfiguration', 'IamInstanceProfile',
     Ref(param_instance_profile)
     ),
    ('aws:autoscaling:launchconfiguration', 'SecurityGroups',
     Ref(param_instance_sg)
     ),

    ('aws:autoscaling:launchconfiguration', 'InstanceType',
     Ref(param_instance_type)),
    ('aws:autoscaling:launchconfiguration', 'MonitoringInterval', '1 minute'),
    # ('aws:autoscaling:launchconfiguration', 'RootVolumeSize', '10'),

    ('aws:autoscaling:trigger', 'MeasureName', 'CPUUtilization'),
    ('aws:autoscaling:trigger', 'Statistic', 'Average'),
    ('aws:autoscaling:trigger', 'Unit', 'Percent'),
    ('aws:autoscaling:trigger', 'LowerThreshold', '25'),
    ('aws:autoscaling:trigger', 'UpperThreshold', '75'),
    ('aws:autoscaling:updatepolicy:rollingupdate', 'RollingUpdateEnabled',
     'true'),
    ('aws:autoscaling:updatepolicy:rollingupdate', 'RollingUpdateType',
     'Health'),

    # === Load balancer ===
    ('aws:elasticbeanstalk:environment:process:default', 'HealthCheckPath',
     Ref(param_health_check)),
    # ('aws:elasticbeanstalk:environment:process:default', 'StickinessEnabled', 'true'),
    # ('aws:elasticbeanstalk:environment:process:default','StickinessLBCookieDuration', '3600'),
    # ('aws:elasticbeanstalk:environment:process:default', 'StickinessType', 'lb_cookie'),

    ('aws:elbv2:listener:default', 'ListenerEnabled', 'true'),

    ('aws:elbv2:listener:443', 'ListenerEnabled',
     If('HttpsCertificateCondition', 'true', 'false')),
    ('aws:elbv2:listener:443', 'Protocol', 'HTTPS'),
    ('aws:elbv2:listener:443', 'SSLCertificateArns', Ref(param_certificate)),

    ('aws:elbv2:loadbalancer', 'ManagedSecurityGroup', Ref(param_lb_sg)),
    ('aws:elbv2:loadbalancer', 'SecurityGroups', Ref(param_lb_sg)),

    #  === Logging ===
    ('aws:elasticbeanstalk:hostmanager', 'LogPublicationControl', 'false'),
    ('aws:elasticbeanstalk:cloudwatch:logs', 'StreamLogs', 'true'),
    ('aws:elasticbeanstalk:cloudwatch:logs', 'DeleteOnTerminate', 'true'),
    ('aws:elasticbeanstalk:cloudwatch:logs', 'RetentionInDays',
     Ref(param_log_retention)
     ),

    # === Change Management ===
    ('aws:elasticbeanstalk:command', 'DeploymentPolicy', 'Rolling'),
    ('aws:elasticbeanstalk:command', 'Timeout', '600'),
    ('aws:elasticbeanstalk:command', 'BatchSizeType', 'Percentage'),
    ('aws:elasticbeanstalk:command', 'BatchSize', '33'),

    ('aws:elasticbeanstalk:managedactions', 'ManagedActionsEnabled', 'true'),
    ('aws:elasticbeanstalk:managedactions', 'PreferredStartTime', 'Sat:10:00'),
    ('aws:elasticbeanstalk:managedactions:platformupdate', 'UpdateLevel',
     'minor'),
    ('aws:elasticbeanstalk:managedactions:platformupdate',
     'InstanceRefreshEnabled', 'false'),
]

eb_version = t.add_resource(beanstalk.ApplicationVersion(
    'Version',
    ApplicationName=Ref(eb_app),
    Description='Version specified in cfn template.',
    SourceBundle=beanstalk.SourceBundle(
        S3Bucket=Ref(param_source_bucket),
        S3Key=Ref(param_source_bundle)
    )
))

eb_template = t.add_resource(beanstalk.ConfigurationTemplate(
    'Template',
    ApplicationName=Ref(eb_app),
    SolutionStackName=Ref(param_solution_stack),
    OptionSettings=cfnutil.make_beanstalk_option_settings(CONFIG_TEMPLATE),
))

ENV_TEMPLATE = [
    # ('aws:elasticbeanstalk:container:tomcat:jvmoptions', 'Xmx', '1024m'),
    # ('aws:elasticbeanstalk:container:tomcat:jvmoptions', 'XX:MaxPermSize', '64m'),
    # ('aws:elasticbeanstalk:container:tomcat:jvmoptions', 'Xms', '256m'),
    # ('aws:elasticbeanstalk:environment:proxy', 'GzipCompression', 'false'),
    # ('aws:elasticbeanstalk:environment:proxy', 'ProxyServer', 'nginx'),
    # ('aws:elasticbeanstalk:xray', 'XRayEnabled', 'false'),
]

eb_env = t.add_resource(beanstalk.Environment(
    'Environment',
    Description='Environment',
    ApplicationName=Ref(eb_app),
    Tier=beanstalk.Tier(
        Name=beanstalk.WebServer,
        Type=beanstalk.WebServerType
    ),
    TemplateName=Ref(eb_template),
    # SolutionStackName=Ref(param_solution_stack),
    OptionSettings=cfnutil.make_beanstalk_option_settings(ENV_TEMPLATE),
    VersionLabel=Ref(eb_version)
))

#
# Output
#
t.add_output([
    Output('Application',
           Description='ElasticBeanstalk application',
           Value=Ref(eb_app),
           ),
    Output('Environment',
           Description='ElasticBeanstalk environment name',
           Value=Ref(eb_env),
           ),
    Output('EndpointURL',
           Description='ElasticBeanstalk environment endpoint url',
           Value=GetAtt(eb_env, 'EndpointURL'),
           ),

])

#
# Write template
#

cfnutil.write(t,
              __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
