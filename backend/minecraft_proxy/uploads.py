"""Multipart uploads become visible only through an offline, locked completion."""
import json
import time
import uuid

PART = 8 * 1024 * 1024
MAX = 1024 ** 3


def begin(s3, db, table, bucket, body, owner, operation):
    size = body.get('size')
    if type(size) is not int or not 0 < size <= MAX or not isinstance(body.get('filename'), str) or not body['filename'].lower().endswith('.zip'):
        raise ValueError('Choose a nonempty map ZIP up to 1 GiB')
    key = 'backups/' + str(uuid.uuid4()) + '.zip'
    upload = s3.create_multipart_upload(Bucket=bucket, Key=key, ContentType='application/zip')['UploadId']
    payload = {'key': key, 'uploadId': upload, 'size': size, 'owner': owner, 'operationId': operation}
    try:
        db.update_item(TableName=table, Key={'pk': {'S': 'upload#' + operation}},
            UpdateExpression='SET payload=:p, expires_at=:e',
            ExpressionAttributeValues={':p': {'S': json.dumps(payload)}, ':e': {'N': str(int(time.time()) + 86400)}})
        parts = [{'partNumber': number, 'url': s3.generate_presigned_url('upload_part', Params={
            'Bucket': bucket, 'Key': key, 'UploadId': upload, 'PartNumber': number,
            'ContentLength': min(PART, size - (number - 1) * PART)}, ExpiresIn=900)}
            for number in range(1, (size + PART - 1) // PART + 1)]
        return {'operationId': operation, 'key': key, 'parts': parts, 'partSize': PART}
    except Exception:
        s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload)
        raise


def load(db, table, operation, owner):
    try:
        if str(uuid.UUID(operation)) != operation:
            raise ValueError()
        item = db.get_item(TableName=table, Key={'pk': {'S': 'upload#' + operation}}, ConsistentRead=True)['Item']
        value = json.loads(item['payload']['S'])
    except (ValueError, KeyError, TypeError):
        raise ValueError('Upload session not found')
    if value['owner'] != owner:
        raise ValueError('Upload session belongs to another account')
    return value


def complete(s3, bucket, session, parts):
    import re
    expected = (session['size'] + PART - 1) // PART
    if not isinstance(parts, list) or len(parts) != expected:
        raise ValueError('All upload parts are required')
    for number, part in enumerate(parts, 1):
        if not isinstance(part, dict) or part.get('PartNumber') != number or not isinstance(part.get('ETag'), str) or not re.fullmatch(r'"?[0-9a-fA-F]{32}"?', part['ETag']):
            raise ValueError('Invalid upload part receipt')
    try:
        s3.complete_multipart_upload(Bucket=bucket, Key=session['key'], UploadId=session['uploadId'], MultipartUpload={'Parts': parts})
    except Exception as error:
        if getattr(error, 'response', {}).get('Error', {}).get('Code') != 'NoSuchUpload':
            raise
    if s3.head_object(Bucket=bucket, Key=session['key'])['ContentLength'] != session['size']:
        raise ValueError('Uploaded size does not match the selected file')
    return {'key': session['key']}
