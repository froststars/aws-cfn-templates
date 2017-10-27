# -*- encoding: utf-8 -*-

from __future__ import print_function

__author__ = 'kotaimen'
__date__ = '24/05/2017'

import datetime, calendar
import os
import boto3, boto3.s3.transfer


def lambda_handler(event, context):
    """Export CloudWatch Logs LogGroup to S3 bucket."""

    print('Received event id %s at %s' % (event['id'], event['time']))
    event_time = datetime.datetime.strptime(event['time'], '%Y-%m-%dT%H:%M:%SZ')

    interval = os.getenv('EXPORT_INTERVAL', 'week')

    if interval == 'day':
        delta = datetime.timedelta(days=1)
    elif interval == 'week':
        delta = datetime.timedelta(weeks=1)
    else:
        raise RuntimeError('Unknown interval.')

    to_time = datetime.date(year=event_time.year,
                            month=event_time.month,
                            day=event_time.day)
    from_time = to_time - delta

    print('Export time range: %s ~ %s' % (from_time, to_time))

    # Get the object from the event and show its content type
    src_loggroup = os.getenv('EXPORT_LOGGROUP')
    dst_bucket = os.getenv('EXPORT_DST_BUCKET')
    dst_prefix = os.getenv('EXPORT_DST_PREFIX')
    task_id = export_logs(src_loggroup,
                          dst_bucket, dst_prefix,
                          from_time, to_time)
    return {'TaskId': task_id}


def date2exporttime(d):
    # export task requires EPOCH milliseconds
    return calendar.timegm(d.timetuple()) * 1000


def export_logs(src_loggroup_name, dst_bucket, dst_prefix, from_time, to_time):
    client = boto3.client('logs')
    prefix = '%s/%s/%s' % (dst_prefix, src_loggroup_name, from_time)
    task_name = 'Export Task of %s during %s~%s' % (
        src_loggroup_name, from_time, to_time)
    print('Submitting task %s' % task_name)

    response = client.create_export_task(
        taskName=task_name,
        logGroupName=src_loggroup_name,
        # logStreamNamePrefix='string',
        fromTime=date2exporttime(from_time),
        to=date2exporttime(to_time),
        destination=dst_bucket,
        destinationPrefix=prefix
    )

    print('Submitted export task id %s' % response['taskId'])

    return response['taskId']
