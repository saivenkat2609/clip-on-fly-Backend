"""
Lambda Function 6 (UPLOAD FLOW): API Gateway Handler for User Uploads
Handles HTTP requests for video upload flow and starts Step Functions execution
Supports pre-signed URL generation for direct S3/R2 upload
"""
import json
import boto3
import uuid
import os
from botocore.config import Config

stepfunctions = boto3.client('stepfunctions')

def get_storage_client():
    """Get S3-compatible storage client (supports AWS S3, Cloudflare R2, Backblaze B2, etc.)"""
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    # Configure SigV4 for R2 compatibility
    s3_config = Config(signature_version='s3v4')

    if endpoint:
        print(f"[Storage] Using custom endpoint: {endpoint}")
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=s3_config,
            region_name=os.environ.get('AWS_REGION', 'auto')
        )
    print("[Storage] Using AWS S3 (default)")
    return boto3.client('s3', config=s3_config)

s3 = get_storage_client()

STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN_UPLOAD')  # Separate state machine for upload flow
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '524288000'))  # 500MB default
UPLOAD_EXPIRY = int(os.environ.get('UPLOAD_EXPIRY', '3600'))  # 1 hour

def get_cors_headers():
    """Return CORS headers for all responses"""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }

def lambda_handler(event, context):
    """
    API Gateway Lambda handler for upload flow

    Endpoints:
    - POST /upload/generate-url: Generate pre-signed URL for upload
    - POST /upload/start: Start video processing after upload
    - GET /upload/status/{session_id}: Get processing status
    - GET /upload/result/{session_id}: Get final result
    - GET /upload/user/{user_id}/videos: Get all videos for a user
    """

    http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
    path = event.get('path', event.get('rawPath', '/'))

    print(f"[API-Upload] Method: {http_method}, Path: {path}")
    print(f"[API-Upload] Full event: {json.dumps(event)}")  # Debug: See full request

    # Handle OPTIONS preflight requests
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': 'OK'})
        }

    # Route request
    if http_method == 'POST' and '/upload/generate-url' in path:
        return handle_generate_upload_url(event)
    elif http_method == 'POST' and '/upload/start' in path:
        return handle_start_processing(event)
    elif http_method == 'GET' and '/upload/status/' in path:
        return handle_status(event, path)
    elif http_method == 'GET' and '/upload/result/' in path:
        return handle_result(event, path)
    elif http_method == 'GET' and '/upload/user/' in path and '/videos' in path:
        return handle_user_videos(event, path)
    else:
        return {
            'statusCode': 404,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Not found'})
        }


def handle_generate_upload_url(event):
    """Handle POST /upload/generate-url - Generate pre-signed URL for upload"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        user_id = body.get('user_id')
        user_email = body.get('user_email', '')
        file_name = body.get('fileName')
        file_size = body.get('fileSize')
        content_type = body.get('contentType', 'video/mp4')
        video_title = body.get('videoTitle', 'Uploaded Video')
        video_description = body.get('videoDescription', '')

        if not user_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'user_id is required'})
            }

        if not file_name or not file_size:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'fileName and fileSize are required'})
            }

        # Validate file size
        if file_size > MAX_FILE_SIZE:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': f'File size {file_size / 1024 / 1024:.2f} MB exceeds limit of {MAX_FILE_SIZE / 1024 / 1024:.2f} MB'
                })
            }

        # Generate session ID
        session_id = str(uuid.uuid4())

        print(f"[API-Upload] Generating upload URL for session: {session_id}")
        print(f"[API-Upload] User ID: {user_id}")
        print(f"[API-Upload] File: {file_name} ({file_size / 1024 / 1024:.2f} MB)")

        # Generate pre-signed URL
        s3_key = f"{session_id}/uploaded_video.mp4"

        # Note: ContentLength is removed from params to avoid CORS issues
        # The browser will automatically set Content-Length, and including it
        # in the signature causes mismatches with CORS preflight requests
        upload_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=UPLOAD_EXPIRY,
            HttpMethod='PUT'
        )

        print(f"[API-Upload] Generated pre-signed URL (expires in {UPLOAD_EXPIRY}s)")
        print(f"[API-Upload] Pre-signed URL for key: {s3_key}")

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'session_id': session_id,
                'uploadUrl': upload_url,
                's3_key': s3_key,
                'expiresIn': UPLOAD_EXPIRY,
                'message': 'Upload URL generated. Use PUT request to upload your video.'
            })
        }

    except Exception as e:
        print(f"[API-Upload] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_start_processing(event):
    """Handle POST /upload/start - Start video processing after upload"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        session_id = body.get('session_id')
        user_id = body.get('user_id')
        user_email = body.get('user_email', '')
        video_title = body.get('videoTitle', 'Uploaded Video')
        video_description = body.get('videoDescription', '')
        s3_key = body.get('s3_key')

        if not session_id or not user_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'session_id and user_id are required'})
            }

        if not s3_key:
            s3_key = f"{session_id}/uploaded_video.mp4"

        print(f"[API-Upload] Starting processing for session: {session_id}")
        print(f"[API-Upload] User ID: {user_id}")
        print(f"[API-Upload] S3 Key: {s3_key}")

        # Verify upload exists (optional - Worker already confirmed upload)
        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
            print(f"[API-Upload] File verified in R2: {s3_key}")
        except Exception as e:
            print(f"[API-Upload] Warning: Could not verify file in R2: {str(e)}")
            print(f"[API-Upload] Continuing anyway since Worker confirmed upload...")
            # Don't fail - Worker already confirmed the upload succeeded

        # Start Step Functions execution
        execution = stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=session_id.replace('-', '_'),  # Step Functions doesn't allow hyphens
            input=json.dumps({
                'session_id': session_id,
                's3_video_key': s3_key,
                'user_id': user_id,
                'user_email': user_email,
                'video_title': video_title,
                'video_description': video_description,
                'source': 'upload'
            })
        )

        return {
            'statusCode': 202,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'session_id': session_id,
                'status': 'processing',
                'execution_arn': execution['executionArn'],
                'message': 'Video processing started successfully'
            })
        }

    except Exception as e:
        print(f"[API-Upload] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_status(event, path):
    """Handle GET /upload/status/{session_id} - Get processing status"""
    try:
        # Extract session ID from path
        session_id = path.split('/status/')[-1]
        execution_name = session_id.replace('-', '_')

        print(f"[API-Upload] Getting status for session: {session_id}")

        # Get execution status
        try:
            response = stepfunctions.describe_execution(
                executionArn=f"{STATE_MACHINE_ARN.replace(':stateMachine:', ':execution:')}:{execution_name}"
            )

            status_map = {
                'RUNNING': 'processing',
                'SUCCEEDED': 'completed',
                'FAILED': 'failed',
                'TIMED_OUT': 'failed',
                'ABORTED': 'failed'
            }

            result = {
                'session_id': session_id,
                'status': status_map.get(response['status'], 'unknown'),
                'start_time': response['startDate'].isoformat()
            }

            # If completed, include output
            if response['status'] == 'SUCCEEDED':
                output = json.loads(response.get('output', '{}'))
                result['result'] = output

            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }

        except stepfunctions.exceptions.ExecutionDoesNotExist:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Session not found'})
            }

    except Exception as e:
        print(f"[API-Upload] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_result(event, path):
    """Handle GET /upload/result/{session_id} - Get final result from S3"""
    try:
        # Extract session ID from path
        session_id = path.split('/result/')[-1]

        print(f"[API-Upload] Getting result for session: {session_id}")

        # Try to get result from user-specific path first, then fall back to session path
        result_keys = [
            f"{session_id}/result.json",
            f"users/*/{ session_id}/result.json"
        ]

        for result_key in result_keys:
            try:
                obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                result = json.loads(obj['Body'].read())

                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps(result)
                }
            except s3.exceptions.NoSuchKey:
                continue

        return {
            'statusCode': 404,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Result not found'})
        }

    except Exception as e:
        print(f"[API-Upload] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_user_videos(event, path):
    """Handle GET /upload/user/{user_id}/videos - Get all videos for a user"""
    try:
        # Extract user ID from path
        user_id = path.split('/user/')[-1].split('/videos')[0]

        print(f"[API-Upload] Getting videos for user: {user_id}")

        # List all objects in user's directory
        user_prefix = f"users/{user_id}/"
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=user_prefix,
            Delimiter='/'
        )

        videos = []

        # Get all session directories for this user
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                session_id = prefix['Prefix'].split('/')[-2]

                # Try to get result.json for this session
                try:
                    result_key = f"{prefix['Prefix']}result.json"
                    obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
                    result = json.loads(obj['Body'].read())

                    # Get metadata (last modified time)
                    metadata_obj = s3.head_object(Bucket=BUCKET_NAME, Key=result_key)

                    videos.append({
                        'session_id': session_id,
                        'status': result.get('status', 'unknown'),
                        'clips_count': result.get('total_clips', 0),
                        'video_info': result.get('video_info', {}),
                        'created_at': metadata_obj['LastModified'].isoformat(),
                        'clips': result.get('clips', []),
                        'source': 'upload'
                    })
                except s3.exceptions.NoSuchKey:
                    # Result not yet available, check if processing
                    videos.append({
                        'session_id': session_id,
                        'status': 'processing',
                        'clips_count': 0,
                        'source': 'upload'
                    })
                except Exception as e:
                    print(f"[API-Upload] Error getting result for {session_id}: {str(e)}")
                    continue

        # Sort by created_at descending (newest first)
        videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'user_id': user_id,
                'total_videos': len(videos),
                'videos': videos,
                'source': 'upload'
            })
        }

    except Exception as e:
        print(f"[API-Upload] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }
