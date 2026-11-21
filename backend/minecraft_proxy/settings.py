"""S3 is the source of truth; offline mutations use the server operation lease."""
import copy
import json
import time
import uuid
from server_config import DEFAULT, validate

KEY = 'settings/server.json'


def read(s3, bucket):
    try:
        value = s3.get_object(Bucket=bucket, Key=KEY)['Body'].read()
    except Exception as error:
        if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404', 'NotFound'):
            return copy.deepcopy(DEFAULT)
        raise
    return validate(json.loads(value))


def write(s3, bucket, value):
    value = validate(value)
    s3.put_object(Bucket=bucket, Key=KEY, Body=json.dumps(value).encode(), ContentType='application/json')
    return value


def lock(db, table, phase='configuring', seconds=60):
    identity = str(uuid.uuid4())
    now = int(time.time())
    db.update_item(TableName=table, Key={'pk': {'S': 'server'}},
        UpdateExpression='SET operation_id=:id, lease_until=:lease, #p=:p',
        ConditionExpression='attribute_not_exists(lease_until) OR lease_until < :now',
        ExpressionAttributeNames={'#p': 'phase'},
        ExpressionAttributeValues={':id': {'S': identity}, ':lease': {'N': str(now + seconds)}, ':now': {'N': str(now)}, ':p': {'S': phase}})
    return identity


def unlock(db, table, identity):
    db.update_item(TableName=table, Key={'pk': {'S': 'server'}},
        UpdateExpression='SET lease_until=:zero, #p=:p, updated_at=:now, #error=:empty REMOVE workflow_url', ConditionExpression='operation_id=:id',
        ExpressionAttributeNames={'#p': 'phase', '#error': 'error'},
        ExpressionAttributeValues={':now': {'N': str(int(time.time()))}, ':empty': {'S': ''}, ':zero': {'N': '0'}, ':id': {'S': identity}, ':p': {'S': 'offline'}})
