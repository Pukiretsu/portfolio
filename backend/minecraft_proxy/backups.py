"""Private map archive catalog and constrained, short-lived browser transfers."""
import os
import re

MAX_UPLOAD = 1024 ** 3
KEY = re.compile(r'^(backups|uploads)/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.zip$')


def bucket():
    return os.environ['BACKUP_BUCKET']


def key(value, *, backups_only=False):
    if not isinstance(value, str) or not KEY.fullmatch(value) or (backups_only and not value.startswith('backups/')):
        raise ValueError('Select a valid map archive')
    return value


def existing(s3, value, *, backups_only=False):
    value = key(value, backups_only=backups_only)
    try:
        head = s3.head_object(Bucket=bucket(), Key=value)
    except Exception as error:
        code = getattr(error, 'response', {}).get('Error', {}).get('Code')
        if code in ('404', 'NoSuchKey', 'NotFound'):
            raise ValueError('Archive not found; upload it again or refresh the list') from error
        raise
    if not 0 < head['ContentLength'] <= MAX_UPLOAD:
        raise ValueError('Archive must be between 1 byte and 1 GiB')
    return value


def catalog(s3, cursor=None):
    arguments = dict(Bucket=bucket(), Prefix='backups/', MaxKeys=100)
    if cursor:
        if not isinstance(cursor, str) or len(cursor) > 2048:
            raise ValueError('Invalid archive cursor')
        arguments['ContinuationToken'] = cursor
    response = s3.list_objects_v2(**arguments)
    items = [{'key': item['Key'], 'size': item['Size'], 'createdAt': item['LastModified'].isoformat()}
             for item in response.get('Contents', []) if KEY.fullmatch(item['Key'])]
    return {'items': sorted(items, key=lambda item: item['createdAt'], reverse=True),
            'nextCursor': response.get('NextContinuationToken')}


def download(s3, body):
    value = existing(s3, body.get('key'), backups_only=True)
    url = s3.generate_presigned_url('get_object', Params={
        'Bucket': bucket(), 'Key': value,
        'ResponseContentDisposition': 'attachment; filename="minecraft-world-' + value.split('/')[1] + '"',
    }, ExpiresIn=300)
    return {'url': url, 'expiresIn': 300}
