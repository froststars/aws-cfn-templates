# -*- encoding: utf-8 -*-

from __future__ import print_function

__author__ = 'kotaimen'
__date__ = '24/05/2017'

import urllib
import zipfile
import gzip
import os
import io
import boto3, boto3.s3.transfer


def lambda_handler(event, context):
    """Response to a S3 object creation notification and extract compressed 
    file contents to dst_bucket, supports zip and gzip files.
    
    Note: Input stream is read into memory using BytesIO.
    
    Required lambda environment variables:
        
        - `DST_BUCKET` - Destination bucket
        - `DST_PREFIX` - Destination prefix (should end with '/') 
    
    """

    # Get the object from the event and show its content type
    src_bucket = event['Records'][0]['s3']['bucket']['name']
    src_key = urllib.unquote_plus(
        event['Records'][0]['s3']['object']['key'].encode('utf8'))

    dst_bucket = os.getenv('DST_BUCKET', src_bucket)

    # Behave like OSX unzip if environment variables are not specified
    if src_key.lower().endswith('.zip'):
        dst_prefix = os.getenv('DST_PREFIX', src_key[:-4] + '/')
        zip_extract(src_bucket, src_key, dst_bucket, dst_prefix)
    elif src_key.lower().endswith('.gz'):
        dst_prefix = os.getenv('DST_PREFIX', src_key[:-3])
        gzip_extract(src_bucket, src_key, dst_bucket, dst_prefix)
    else:
        raise RuntimeError('Unsupported file.')


def zip_extract(src_bucket, src_key, dst_bucket, dst_prefix):
    s3 = boto3.client('s3')

    with io.BytesIO() as fp:
        print('Downloading {}/{}'.format(src_bucket, src_key))
        s3.download_fileobj(src_bucket, src_key, fp)

        zip_file = zipfile.ZipFile(fp, mode='r')

        for zip_info in zip_file.filelist:
            if zip_info.filename.endswith('/'):
                # directories not required on S3
                continue
            dst_key = '{}{}'.format(dst_prefix, zip_info.filename)
            print('Uploading {0.filename} to {1}/{2} ({0.file_size} bytes)' \
                  .format(zip_info, dst_bucket, dst_key))
            with zip_file.open(zip_info) as decompressed_file:
                s3.upload_fileobj(decompressed_file, dst_bucket, dst_key)


def gzip_extract(src_bucket, src_key, dst_bucket, dst_prefix):
    s3 = boto3.client('s3')

    with io.BytesIO() as fp:
        print('Downloading {}/{}'.format(src_bucket, src_key))
        s3.download_fileobj(src_bucket, src_key, fp)
        fp.seek(0)
        dst_key = dst_prefix

        # HACK: boto3 requires a seekable file object which Gzip doesn't support
        with gzip.GzipFile(fileobj=fp, mode='rb') as gzip_file:
            buf = gzip_file.read()
            print('Uploading to {}/{} ({} bytes)'.format(
                dst_bucket, dst_prefix, len(buf)))

            s3.put_object(Bucket=dst_bucket,
                          Key=dst_key,
                          Body=buf)
