# -*- encoding: utf-8 -*-

__author__ = 'kotaimen'
__date__ = '18/05/2017'

from troposphere import Base64, FindInMap, GetAtt, Join, Select, Sub
from troposphere import ImportValue, Export
from troposphere import Condition, And, Equals, If, Not, Or
from troposphere import Template, Parameter, Ref, Tags, Output
from troposphere import AWS_ACCOUNT_ID, AWS_REGION, AWS_STACK_ID, \
    AWS_STACK_NAME, AWS_NO_VALUE

import troposphere.sns as sns

import cfnutil

#
# Template
#
t = Template()
t.add_version('2010-09-09')
t.add_description('Alarm with email notification')

#
# Interface
#
parameter_groups = [
    {
        'Label': {'default': 'Alarm Configuration'},
        'Parameters':
            [
                'AlarmEmails',
                'NumOfEmails',
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

param_display_name = t.add_parameter(Parameter(
    'DisplayName',
    Description='User defined string that can be used to identify this SNS topic.',
    Type='String',
    Default='',
))

param_alarm_emails = t.add_parameter(
    Parameter(
        'AlarmEmails',
        Default='nobody@amazon.com',
        Description='List of comma delimited email address to notify.',
        Type='CommaDelimitedList',
    )
)

param_num_emails = t.add_parameter(Parameter(
    'NumOfEmails',
    Description='Number of email addresses in AlarmEmails.',
    Type='String',
    Default='1',
    AllowedValues=['1', '2', '3', '4', '5', '6']
))

#
# Conditions
#

t.add_condition(
    'HasDisplayNameCondition',
    Not(Equals(Ref(param_display_name), ''))
)

t.add_condition(
    'SixEmailsCondition',
    Equals(Ref(param_num_emails), '6')
)

t.add_condition(
    'FiveEmailsCondition',
    Or(
        Equals(Ref(param_num_emails), '6'),
        Equals(Ref(param_num_emails), '5'),
    )
)

t.add_condition(
    'FourEmailsCondition',
    Or(
        Equals(Ref(param_num_emails), '6'),
        Equals(Ref(param_num_emails), '5'),
        Equals(Ref(param_num_emails), '4'),

    ))
t.add_condition(
    'ThreeEmailsCondition',
    Or(
        Equals(Ref(param_num_emails), '6'),
        Equals(Ref(param_num_emails), '5'),
        Equals(Ref(param_num_emails), '4'),
        Equals(Ref(param_num_emails), '3'),
    )
)
t.add_condition(
    'TwoEmailsCondition',
    Or(
        Equals(Ref(param_num_emails), '6'),
        Equals(Ref(param_num_emails), '5'),
        Equals(Ref(param_num_emails), '4'),
        Equals(Ref(param_num_emails), '3'),
        Equals(Ref(param_num_emails), '2'),
    )
)

#
# Resources
#

alarm_topic = t.add_resource(sns.Topic(
    'AlarmTopic',

    DisplayName=If('HasDisplayNameCondition', Ref(param_display_name),
                   Ref(AWS_NO_VALUE)),

    Subscription=[

        sns.Subscription(
            Endpoint=Select(0, Ref(param_alarm_emails)),
            Protocol='email'),

        If('TwoEmailsCondition',
           sns.Subscription(
               Endpoint=Select(1, Ref(param_alarm_emails)),
               Protocol='email'
           ),
           Ref(AWS_NO_VALUE)),

        If('ThreeEmailsCondition',
           sns.Subscription(
               Endpoint=Select(2, Ref(param_alarm_emails)),
               Protocol='email'
           ),
           Ref(AWS_NO_VALUE)),

        If('FourEmailsCondition',
           sns.Subscription(
               Endpoint=Select(3, Ref(param_alarm_emails)),
               Protocol='email'
           ),
           Ref(AWS_NO_VALUE)),

        If('FiveEmailsCondition',
           sns.Subscription(
               Endpoint=Select(4, Ref(param_alarm_emails)),
               Protocol='email'
           ),
           Ref(AWS_NO_VALUE)),

        If('SixEmailsCondition',
           sns.Subscription(
               Endpoint=Select(5, Ref(param_alarm_emails)),
               Protocol='email'
           ),
           Ref(AWS_NO_VALUE)),

    ],
))

#
# Output
#
t.add_output([
    Output('TopicArn',
           Description='Topic arn',
           Value=Ref(alarm_topic),
           Export=Export(Sub('${AWS::StackName}-TopicArn')),
           ),
    Output('TopicName',
           Description='Topic name',
           Value=GetAtt(alarm_topic, 'TopicName'),
           Export=Export(Sub('${AWS::StackName}-TopicName')),
           ),
])

#
# Write
#
cfnutil.write(t, __file__.replace('Template.py', '.template.yaml'),
              write_yaml=True)
