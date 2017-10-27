# -*- encoding: utf-8 -*-

'''
Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
'''

import boto3
import hashlib
import json
import os
import urllib2

# Name of the service, as seen in the ip-groups.json file, to extract information for
SERVICE = "CLOUDFRONT"
# Ports your application uses that need inbound permissions from the service for
INGRESS_PORTS = {'Http': 80, 'Https': 443}
# Tags which identify the security groups you want to update
HTTP_SG_TAG = {'Name': 'cloudfront', 'AutoUpdate': 'true', 'Protocol': 'http'}
HTTPS_SG_TAG = {'Name': 'cloudfront', 'AutoUpdate': 'true', 'Protocol': 'https'}


def lambda_handler(event, context):
    # print("Received event: " + json.dumps(event, indent=2))
    message = json.loads(event['Records'][0]['Sns']['Message'])

    # Load the ip ranges from the url
    ip_ranges = json.loads(get_ip_groups_json(message['url'], message['md5']))

    # extract the service ranges
    cf_ranges = get_ranges_for_service(ip_ranges, SERVICE)

    # update the security groups
    for region in os.getenv('REGIONS', 'us-east-1').split(','):
        result = update_security_groups(cf_ranges, region.strip())

    return result


def get_ip_groups_json(url, expected_hash):
    # print("Updating from " + url)

    response = urllib2.urlopen(url)
    ip_json = response.read()

    m = hashlib.md5()
    m.update(ip_json)
    hash = m.hexdigest()

    if hash != expected_hash:
        raise Exception(
            'MD5 mismatch, expected %s got %s.' % (expected_hash, hash))

    return ip_json


def get_ranges_for_service(ranges, service):
    service_ranges = list()
    for prefix in ranges['prefixes']:
        if prefix['service'] == service:
            # print('Found ' + service + ' range: ' + prefix['ip_prefix'])
            service_ranges.append(prefix['ip_prefix'])

    return service_ranges


def update_security_groups(new_ranges, region):
    client = boto3.client('ec2', region_name=region)
    print('Region: %s' % region)
    http_group = get_sg_for_update(client, HTTP_SG_TAG)
    https_group = get_sg_for_update(client, HTTPS_SG_TAG)
    print('Found %d Http SG to update' % len(http_group))
    print('Found %d Https SG to update' % len(https_group))

    result = list()
    http_updated = 0
    https_updated = 0
    for group in http_group:
        if update_security_group(client, group, new_ranges,
                                 INGRESS_PORTS['Http']):
            http_updated += 1
            result.append('Updated ' + group['GroupId'])
    for group in https_group:
        if update_security_group(client, group, new_ranges,
                                 INGRESS_PORTS['Https']):
            https_updated += 1
            result.append('Updated ' + group['GroupId'])

    result.append('Updated %s of %s HTTP' % (http_updated, len(http_group)))
    result.append('Updated %s of %s HTTPS' % (https_updated, len(https_group)))

    return result


def update_security_group(client, group, new_ranges, port):
    added = 0
    removed = 0

    if len(group['IpPermissions']) > 0:
        for permission in group['IpPermissions']:
            if permission['FromPort'] <= port and permission['ToPort'] >= port:
                old_prefixes = list()
                to_revoke = list()
                to_add = list()
                for range in permission['IpRanges']:
                    cidr = range['CidrIp']
                    old_prefixes.append(cidr)
                    if new_ranges.count(cidr) == 0:
                        to_revoke.append(range)
                        # print('%s: Revoking %s : %s' % (group['GroupId'], cidr, permission['ToPort']))

                for range in new_ranges:
                    if old_prefixes.count(range) == 0:
                        to_add.append({'CidrIp': range})
                        # print('%s: Adding %s : %s' % ( group['GroupId'], range, permission['ToPort']))

                removed += revoke_permissions(client, group, permission,
                                              to_revoke)
                added += add_permissions(client, group, permission, to_add)
    else:
        to_add = list()
        for range in new_ranges:
            to_add.append({'CidrIp': range})
            # print('%s: Adding %s : %s' % (group['GroupId'], range, port))
        permission = {'ToPort': port, 'FromPort': port, 'IpProtocol': 'tcp'}
        added += add_permissions(client, group, permission, to_add)

    print('')

    print(
        group['GroupId'] + ": Added " + str(added) + ", Revoked " + str(
            removed))
    return (added > 0 or removed > 0)


def revoke_permissions(client, group, permission, to_revoke):
    if len(to_revoke) > 0:
        revoke_params = {
            'ToPort': permission['ToPort'],
            'FromPort': permission['FromPort'],
            'IpRanges': to_revoke,
            'IpProtocol': permission['IpProtocol']
        }

        client.revoke_security_group_ingress(GroupId=group['GroupId'],
                                             IpPermissions=[revoke_params])

    return len(to_revoke)


def add_permissions(client, group, permission, to_add):
    if len(to_add) > 0:
        add_params = {
            'ToPort': permission['ToPort'],
            'FromPort': permission['FromPort'],
            'IpRanges': to_add,
            'IpProtocol': permission['IpProtocol']
        }

        client.authorize_security_group_ingress(GroupId=group['GroupId'],
                                                IpPermissions=[add_params])

    return len(to_add)


def get_sg_for_update(client, security_group_tag):
    filters = list()
    for key, value in security_group_tag.iteritems():
        filters.extend(
            [
                {'Name': "tag-key", 'Values': [key]},
                {'Name': "tag-value", 'Values': [value]}
            ]
        )

    response = client.describe_security_groups(Filters=filters)

    return response['SecurityGroups']
