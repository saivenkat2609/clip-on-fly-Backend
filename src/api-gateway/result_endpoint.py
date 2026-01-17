"""
API Endpoint: GET /result/{sessionId}
LAYER 3 RESILIENCE: Fetch result.json from S3/R2 and sync to Firestore

This endpoint is called by the frontend when a video appears stuck in "processing" state.
It fetches result.json from storage and returns it, triggering Firestore sync on the frontend.

Flow:
1. Frontend detects video stuck (processing > 15 minutes)
2. User clicks "Refresh Status" button
3. Frontend calls GET /result/{sessionId}
4. This Lambda fetches result.json from R2
5. Returns clips data to frontend
6. Frontend updates Firestore directly
"""

import json
import boto3
from botocore.config import Config
import os

def get_storage_client():
    """Get S3-compatible storage client (R2/S3)"""
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    s3_config = Config(signature_version='s3v4')

    if endpoint:
        print(f"[Result API] Using custom endpoint: {endpoint}")
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=s3_config,
            region_name=os.environ.get('AWS_REGION', 'auto')
        )
    print("[Result API] Using AWS S3 (default)")
    return boto3.client('s3', config=s3_config)

def lambda_handler(event, context):
    """
    GET /result/{sessionId}

    Fetches result.json from R2/S3 for a given session.

    Path Parameters:
        sessionId: Video session ID

    Headers:
        Authorization: Bearer <firebase-id-token>

    Returns:
        200: { status: "completed", clips: [...], video_info: {...} }
        404: { error: "Result not found" }
        500: { error: "Internal server error" }
    """
    try:
        # Extract session ID from path parameters
        session_id = event.get('pathParameters', {}).get('sessionId')

        if not session_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing session ID'
                })
            }

        # Get user ID from authorizer context (JWT validation)
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('userId')

        if not user_id:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Unauthorized'
                })
            }

        print(f"[Result API] Fetching result for session: {session_id}, user: {user_id}")

        # Initialize S3 client
        s3 = get_storage_client()
        bucket_name = os.environ.get('BUCKET_NAME', 'opus-clip-videos')

        # Try user-specific location first (newer format)
        result_key = f"users/{user_id}/{session_id}/result.json"

        try:
            print(f"[Result API] Checking: {result_key}")
            response = s3.get_object(Bucket=bucket_name, Key=result_key)
            result_data = json.loads(response['Body'].read())

            print(f"[Result API] ✓ Found result with {len(result_data.get('clips', []))} clips")

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(result_data)
            }

        except s3.exceptions.NoSuchKey:
            # Try legacy location
            result_key = f"{session_id}/result.json"

            try:
                print(f"[Result API] Trying legacy location: {result_key}")
                response = s3.get_object(Bucket=bucket_name, Key=result_key)
                result_data = json.loads(response['Body'].read())

                print(f"[Result API] ✓ Found result in legacy location with {len(result_data.get('clips', []))} clips")

                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps(result_data)
                }

            except s3.exceptions.NoSuchKey:
                # Result not found in either location
                print(f"[Result API] ✗ Result not found for session: {session_id}")

                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'Result not found. Video may still be processing.',
                        'session_id': session_id
                    })
                }

    except Exception as e:
        print(f"[Result API] Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }
