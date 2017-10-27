# -*- encoding: utf-8 -*-

__author__ = 'ray'
__date__ = '1/3/17'

from troposphere import Template, Parameter, Output, Retain
from troposphere import GetAtt, Export, Equals, Ref, If, AWS_NO_VALUE, Not, Sub

from troposphere import logs

import cfnutil

t = Template()
t.add_version()
t.add_description(
    'CloudWatch Logs log group'
)

#
# Parameter
#

param_name = t.add_parameter(Parameter(
    'LogGroupName',
    Type='String',
    Description='Name of the Log Group',
    MaxLength=512,
    AllowedPattern='[\.\-_/#A-Za-z0-9]*',
    Default=''
))

param_retention = t.add_parameter(Parameter(
    'RetentionDays',
    Type='Number',
    Description='The number of days log events are kept in CloudWatch Logs.',
    AllowedValues=[-1, 1, 3, 5, 7, 14, 30, 60, 90, 120, 150,
                   180, 365, 400, 545, 731, 1827, 3653],
    Default='-1'
))

#
# Condition
#
t.add_condition(
    'HasName',
    Not(Equals(Ref(param_name), ''))
)

t.add_condition(
    'NotExpire',
    Equals(Ref(param_retention), -1)
)

#
# Resource
#
log_group = t.add_resource(logs.LogGroup(
    'LogGroup',
    # DeletionPolicy=Retain,
    LogGroupName=If('HasName', Ref(param_name), Ref(AWS_NO_VALUE)),
    RetentionInDays=If('NotExpire', Ref(AWS_NO_VALUE), Ref(param_retention))
))

#
# Output
#
t.add_output([
    Output(
        'LogGroupName',
        Description='Name of the log group.',
        Value=Ref(log_group),
        # Export=Export(Sub('${AWS::StackName}-LogGroupName'))
    ),
    Output(
        'LogGroupArn',
        Description='Arn of the log group.',
        Value=GetAtt(log_group, 'Arn'),
        # Export=Export(Sub('${AWS::StackName}-LogGroupArn'))
    ),
])

#
# Write
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)

