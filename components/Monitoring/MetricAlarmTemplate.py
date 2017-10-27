# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '12/05/2017'

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
import troposphere.cloudwatch as cloudwatch
import troposphere.logs as logs

import csv
import cfnutil
import six

#
# Template
#
t = Template()
t.add_version('2010-09-09')
t.add_description('Metric and alarm')

#
# Interface
#

parameter_groups = [
    {
        'Label': {'default': 'LogGroup Configuration'},
        'Parameters':
            [
                'LogGroupName',
            ]
    },
    {
        'Label': {'default': 'Metric FilterConfiguration'},
        'Parameters':
            [
                'MetricFilterPattern',
                'MetricName',
                'MetricNamespace',
                'MetricValue'
            ]
    },
    {
        'Label': {'default': 'Alarm Configuration'},
        'Parameters':
            [
                'AlarmEnabled',
                'AlarmComparisonOperator',
                'AlarmStatistic',
                'AlarmThreshold',
                'AlarmPeriod',
                'AlarmEvaluationPeriods',
                'AlarmUnit',
            ]
    },
    {
        'Label': {'default': 'Notification Configuration'},
        'Parameters':
            [
                'NotificationEnabled',
                'AlarmTopic',
                'OkTopic',
                'InsufficientDataTopic',
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
param_loggroup_name = t.add_parameter(Parameter(
    'LogGroupName',
    Description='Name of the Log Group',
    MaxLength=512,
    Type='String',
    AllowedPattern='[\.\-_/#A-Za-z0-9]*',
    Default=''
))

param_metric_filter_pattern = t.add_parameter(Parameter(
    'MetricFilterPattern',
    Description='Filter pattern of LogGroup metric filter.',
    Default='[ERROR]',
    Type='String',
    MinLength=0,
    MaxLength=1024
))

param_metric_name = t.add_parameter(Parameter(
    'MetricName',
    Description='The name of the CloudWatch metric.',
    Default='Metric',
    Type='String',
    MinLength=0,
    MaxLength=255,
    AllowedPattern='[^:*$]*',
))

param_metric_namespace = t.add_parameter(Parameter(
    'MetricNamespace',
    Description='The namespace of the CloudWatch metric.',
    Default='Metrics',
    Type='String',
    MinLength=0,
    MaxLength=255,
    AllowedPattern='[^:*$]*',
))

param_metric_value = t.add_parameter(Parameter(
    'MetricValue',
    Description='The value to publish to the CloudWatch metric when a filter '
                'pattern matches a log event.',
    Default='1',
    Type='String',
    MinLength=0,
    MaxLength=100,
))

param_alarm_enabled = t.add_parameter(Parameter(
    'AlarmEnabled',
    Description='Whether enables the alarm.  Set to false deletes the alarm '
                'resource.',
    Default='true',
    Type='String',
    AllowedValues=['true', 'false']
))

param_alarm_comparison_operator = t.add_parameter(Parameter(
    'AlarmComparisonOperator',
    Description='The arithmetic operation to use when comparing the specified '
                'Statistic and Threshold.',
    Default='GreaterThanThreshold',
    Type='String',
    AllowedValues=['GreaterThanOrEqualToThreshold', 'GreaterThanThreshold',
                   'LessThanThreshold', 'LessThanOrEqualToThreshold']
))

param_alarm_statistic = t.add_parameter(Parameter(
    'AlarmStatistic',
    Description='The statistic to apply to the alarm\'s associated metric.',
    Default='Average',
    Type='String',
    AllowedValues=['SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum']
))

param_alarm_threshold = t.add_parameter(Parameter(
    'AlarmThreshold',
    Description='The value against which the specified statistic is compared.',
    Default='0.0',
    Type='Number',
))

param_alarm_period = t.add_parameter(Parameter(
    'AlarmPeriod',
    Description='The time over which the specified statistic is applied. '
                'You must specify a time in seconds that is also a multiple '
                'of 60.',
    Default='60',
    Type='String',
    # MinValue=60,
    # MaxValue=86400,
    AllowedValues=['60', '300', '900', '3600', '86400']
))

param_alarm_evaluation_periods = t.add_parameter(Parameter(
    'AlarmEvaluationPeriods',
    Description='The number of periods over which data is compared to the '
                'specified threshold.',
    Default='1',
    Type='Number',
    MinValue=1,
    MaxValue=1440,
))

param_alarm_unit = t.add_parameter(Parameter(
    'AlarmUnit',
    Description='The unit for the alarm\'s associated metric.',
    Default='None',
    Type='String',
    AllowedValues=['Seconds', 'Microseconds', 'Milliseconds', 'Bytes',
                   'Kilobytes', 'Megabytes', 'Gigabytes', 'Terabytes', 'Bits',
                   'Kilobits', 'Megabits', 'Gigabits', 'Terabits', 'Percent',
                   'Count', 'Bytes/Second', 'Kilobytes/Second',
                   'Megabytes/Second', 'Gigabytes/Second', 'Terabytes/Second',
                   'Bits/Second', 'Kilobits/Second', 'Megabits/Second',
                   'Gigabits/Second', 'Terabits/Second', 'Count/Second', 'None']
))

param_notification_enabled = t.add_parameter(Parameter(
    'NotificationEnabled',
    Description='whether actions should be executed during any changes to the '
                'alarm\'s state.',
    Default='false',
    Type='String',
    AllowedValues=['true', 'false']
))

param_alarm_topic = t.add_parameter(Parameter(
    'AlarmTopic',
    Description='SNS topic ARN to notify when alarm translates to ALARM '
                'state from any other state',
    Default='',
    Type='String',
))

param_ok_topic = t.add_parameter(Parameter(
    'OkTopic',
    Description='SNS topic ARN to notify when alarm translates to OK '
                'state from any other state',
    Default='',
    Type='String',
))

param_insufficient_data_topic = t.add_parameter(Parameter(
    'InsufficientDataTopic',
    Description='SNS topic ARN to notify when alarm translates to '
                'INSUFFICIENT_DATA state from any other state',
    Default='',
    Type='String',
))

param_treat_missing_data = t.add_parameter(Parameter(
    'TreatMissingData',
    Description='Specifies how the alarm treats missing data points.',
    Default='missing',
    AllowedValues=['breaching', 'notBreaching', 'ignore', 'missing'],
    Type='String',
))

#
# Conditions
#
t.add_condition(
    'AlarmEnabledCondition',
    Equals(Ref(param_alarm_enabled), 'true'),
)

t.add_condition(
    'AlarmTopicCondition',
    Not(Equals(Ref(param_alarm_topic), '')),
)

t.add_condition(
    'OkTopicCondition',
    Not(Equals(Ref(param_ok_topic), '')),
)
t.add_condition(
    'InsufficientDataTopicCondition',
    Not(Equals(Ref(param_insufficient_data_topic), '')),
)

#
# Resources
#

metric_filter = t.add_resource(logs.MetricFilter(
    'MetricFilter',
    LogGroupName=Ref(param_loggroup_name),
    FilterPattern=Ref(param_metric_filter_pattern),
    MetricTransformations=[
        logs.MetricTransformation(
            MetricName=Ref(param_metric_name),
            MetricNamespace=Ref(param_metric_namespace),
            MetricValue=Ref(param_metric_value),
        )
    ]
))

alarm = t.add_resource(cloudwatch.Alarm(
    'Alarm',
    Condition='AlarmEnabledCondition',
    ActionsEnabled=Ref(param_notification_enabled),
    MetricName=Ref(param_metric_name),
    Namespace=Ref(param_metric_namespace),
    ComparisonOperator=Ref(param_alarm_comparison_operator),
    Statistic=Ref(param_alarm_statistic),
    Threshold=Ref(param_alarm_threshold),
    EvaluationPeriods=Ref(param_alarm_evaluation_periods),
    Period=Ref(param_alarm_period),
    Unit=Ref(param_alarm_unit),
    AlarmActions=[
        If('AlarmTopicCondition', Ref(param_alarm_topic), Ref(AWS_NO_VALUE))
    ],
    OKActions=[
        If('OkTopicCondition', Ref(param_ok_topic), Ref(AWS_NO_VALUE))
    ],
    InsufficientDataActions=[
        If('InsufficientDataTopicCondition',
           Ref(param_insufficient_data_topic), Ref(AWS_NO_VALUE))
    ],
    TreatMissingData=Ref(param_treat_missing_data),
))

#
# Output
#
t.add_output([
    Output('MetricFilter',
           Description='Metric filter',
           Value=Ref(metric_filter),
           ),
    Output('AlarmName',
           Condition='AlarmEnabledCondition',
           Description='Alarm name',
           Value=Ref(alarm),
           ),
])

cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
