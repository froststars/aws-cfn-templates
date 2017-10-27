#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import print_function

print('Loading function')

import boto3
import logging
import cfnresponse


def lambda_handler(event, context):
    print('REQUEST RECEIVED: ', event)
    response_data = {}
    arn = None

    try:
        if event['RequestType'] in ['Delete', 'Update']:
            sns = boto3.client('sns')
            sns.unsubscribe(SubscriptionArn=event['PhysicalResourceId'])

        if event['RequestType'] in ['Create', 'Update']:
            sns = boto3.client('sns')
            ret = sns.subscribe(
                TopicArn=event['ResourceProperties']['TopicArn'],
                Protocol=event['ResourceProperties']['Protocol'],
                Endpoint=event['ResourceProperties']['Endpoint']
            )
            arn = ret['SubscriptionArn']

        cfnresponse.send(event, context, cfnresponse.SUCCESS,
                         response_data,
                         arn)
    except Exception as e:
        logging.exception(e)
        response_data = {'exception': repr(e)}

        cfnresponse.send(event, context, cfnresponse.FAILED, response_data)
