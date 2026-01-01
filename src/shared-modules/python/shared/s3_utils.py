"""
S3 utilities with hash-based prefix sharding for high throughput.

This module provides utilities for generating S3 keys with proper prefix sharding
to avoid S3 throughput bottlenecks (3,500 PUTs/sec per prefix).

With hash-based sharding, throughput increases to 896,000 PUTs/sec (256x improvement).
"""

import hashlib
import boto3
import os
import json
from typing import Dict, Optional, Any


def get_storage_client():
    """
    Get S3-compatible storage client (supports AWS S3 and Cloudflare R2).

    Returns:
        boto3 S3 client configured for AWS S3 or Cloudflare R2
    """
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    if endpoint:
        # Using Cloudflare R2 or custom endpoint
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.environ.get('AWS_REGION', 'auto')
        )

    # Using AWS S3
    return boto3.client('s3')


# S3 client
s3 = get_storage_client()

# Configuration
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')
# Support both ENABLE_S3_SHARDING and USE_S3_SHARDING env vars
USE_SHARDING = os.environ.get('ENABLE_S3_SHARDING', os.environ.get('USE_S3_SHARDING', 'true')).lower() == 'true'


def get_s3_prefix(user_id: str, session_id: str) -> str:
    """
    Generate S3 prefix with hash-based sharding for higher throughput.

    Structure: users/{hash_prefix}/{user_id}/{session_id}/

    Example:
      user_id = "user123"
      hash = md5("user123") = "a1b2c3d4..."
      hash_prefix = "a1"  (first 2 chars)
      prefix = "users/a1/user123/session456/"

    This distributes load across 256 prefixes (16^2) instead of 1.
    Throughput: 3,500 PUTs/sec → 896,000 PUTs/sec

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        S3 prefix path without trailing slash
    """
    if USE_SHARDING:
        # Hash user_id to get consistent prefix
        hash_object = hashlib.md5(user_id.encode())
        hash_hex = hash_object.hexdigest()

        # Use first 2 characters as shard key (256 possible values: 00-ff)
        shard_prefix = hash_hex[:2]

        # Full prefix with sharding
        prefix = f"users/{shard_prefix}/{user_id}/{session_id}"
    else:
        # Legacy prefix structure (for backwards compatibility)
        prefix = f"users/{user_id}/{session_id}"

    return prefix


def get_video_key(user_id: str, session_id: str, filename: str = "original_video.mp4") -> str:
    """
    Generate S3 key for video file.

    Args:
        user_id: User identifier
        session_id: Session identifier
        filename: Video filename (default: original_video.mp4)

    Returns:
        Full S3 key path
    """
    prefix = get_s3_prefix(user_id, session_id)
    return f"{prefix}/{filename}"


def get_clip_key(user_id: str, session_id: str, clip_index: int, aspect_ratio: str) -> str:
    """
    Generate S3 key for clip file.

    Args:
        user_id: User identifier
        session_id: Session identifier
        clip_index: Clip index (0, 1, 2, ...)
        aspect_ratio: Aspect ratio (9x16, 16x9, 1x1)

    Returns:
        Full S3 key path
    """
    prefix = get_s3_prefix(user_id, session_id)
    return f"{prefix}/clips/clip_{clip_index}_{aspect_ratio}.mp4"


def get_transcript_key(user_id: str, session_id: str) -> str:
    """
    Generate S3 key for transcript file.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Full S3 key path
    """
    prefix = get_s3_prefix(user_id, session_id)
    return f"{prefix}/transcript.json"


def get_result_key(user_id: str, session_id: str) -> str:
    """
    Generate S3 key for result file.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Full S3 key path
    """
    prefix = get_s3_prefix(user_id, session_id)
    return f"{prefix}/result.json"


def get_object_with_fallback(key: str, user_id: str, session_id: str, filename: str) -> Optional[Dict[str, Any]]:
    """
    Get object from S3 with fallback to legacy prefix structure.

    This provides backwards compatibility during migration from non-sharded to sharded prefixes.

    Args:
        key: Primary S3 key (with sharding)
        user_id: User identifier
        session_id: Session identifier
        filename: Filename to try in legacy path

    Returns:
        S3 object response or None if not found
    """
    try:
        # Try new prefix (with hash)
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return response
    except s3.exceptions.NoSuchKey:
        print(f"Key not found with sharding: {key}, trying legacy prefix...")
        pass

    try:
        # Fallback to old prefix (without hash)
        legacy_key = f"users/{user_id}/{session_id}/{filename}"
        response = s3.get_object(Bucket=BUCKET_NAME, Key=legacy_key)
        print(f"Found object in legacy prefix: {legacy_key}")
        return response
    except s3.exceptions.NoSuchKey:
        print(f"Key not found in legacy prefix either: {legacy_key}")
        return None


def get_result_from_s3(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get result.json from S3 with backwards compatibility.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Result data as dictionary or None if not found
    """
    key = get_result_key(user_id, session_id)
    response = get_object_with_fallback(key, user_id, session_id, "result.json")

    if response:
        body = response['Body'].read()
        return json.loads(body)

    return None


def get_transcript_from_s3(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get transcript.json from S3 with backwards compatibility.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Transcript data as dictionary or None if not found
    """
    key = get_transcript_key(user_id, session_id)
    response = get_object_with_fallback(key, user_id, session_id, "transcript.json")

    if response:
        body = response['Body'].read()
        return json.loads(body)

    return None


def put_json_to_s3(key: str, data: Dict[str, Any]) -> bool:
    """
    Put JSON data to S3.

    Args:
        key: S3 key
        data: Dictionary to store as JSON

    Returns:
        True if successful, False otherwise
    """
    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        print(f"Successfully uploaded JSON to s3://{BUCKET_NAME}/{key}")
        return True
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        return False


def generate_presigned_url(key: str, expiration: int = 604800) -> str:
    """
    Generate pre-signed URL for S3 object.

    Args:
        key: S3 key
        expiration: URL expiration in seconds (default: 7 days)

    Returns:
        Pre-signed URL
    """
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': key
            },
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return ""


def list_session_objects(user_id: str, session_id: str) -> list:
    """
    List all objects in a session directory.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        List of object keys
    """
    prefix = get_s3_prefix(user_id, session_id)

    try:
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix + "/"
        )

        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        return []
    except Exception as e:
        print(f"Error listing objects: {str(e)}")
        return []


# Export commonly used functions
__all__ = [
    'get_storage_client',
    'get_s3_prefix',
    'get_video_key',
    'get_clip_key',
    'get_transcript_key',
    'get_result_key',
    'get_result_from_s3',
    'get_transcript_from_s3',
    'put_json_to_s3',
    'generate_presigned_url',
    'list_session_objects'
]
