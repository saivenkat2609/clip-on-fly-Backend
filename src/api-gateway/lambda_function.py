"""
Lambda Function 6: API Gateway Handler
Handles HTTP requests and starts Step Functions execution
"""
import json
import boto3
import uuid
import os

stepfunctions = boto3.client('stepfunctions')
def get_storage_client():
    """Get S3-compatible storage client (supports AWS S3, Cloudflare R2, Backblaze B2, etc.)"""
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    if endpoint:
        print(f"[Storage] Using custom endpoint: {endpoint}")
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.environ.get('AWS_REGION', 'auto')
        )
    print("[Storage] Using AWS S3 (default)")
    return boto3.client('s3')

s3 = get_storage_client()

STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')

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
    API Gateway Lambda handler

    Endpoints:
    - POST /process: Start video processing
    - GET /status/{session_id}: Get processing status
    - GET /result/{session_id}: Get final result
    """

    http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
    path = event.get('path', event.get('rawPath', '/'))

    print(f"[API] Method: {http_method}, Path: {path}")

    # Handle OPTIONS preflight requests
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': 'OK'})
        }

    # Route request
    if http_method == 'POST' and path == '/process':
        return handle_process(event)
    elif http_method == 'GET' and '/status/' in path:
        return handle_status(event, path)
    elif http_method == 'GET' and '/result/' in path:
        return handle_result(event, path)
    elif http_method == 'GET' and '/user/' in path and '/videos' in path:
        return handle_user_videos(event, path)
    else:
        return {
            'statusCode': 404,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Not found'})
        }


def handle_process(event):
    """Handle POST /process - Start video processing"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        youtube_url = body.get('youtube_url')
        user_id = body.get('user_id')
        user_email = body.get('user_email', '')
        start_from = body.get('startFrom', 'download')
        if not youtube_url:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'youtube_url is required'})
            }

        if not user_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'user_id is required'})
            }

        # Generate session ID
        session_id = str(uuid.uuid4())

        print(f"[API] Starting processing for session: {session_id}")
        print(f"[API] User ID: {user_id}")
        print(f"[API] YouTube URL: {youtube_url}")

        # Start Step Functions execution
        execution = stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=session_id.replace('-', '_'),  # Step Functions doesn't allow hyphens
            input=json.dumps({
                'session_id': session_id,
                'youtube_url': youtube_url,
                'user_id': user_id,
                'user_email': user_email,
                'startFrom': start_from
            })
        )

        return {
            'statusCode': 202,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'session_id': session_id,
                'status': 'processing',
                'execution_arn': execution['executionArn']
            })
        }

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_status(event, path):
    """Handle GET /status/{session_id} - Get processing status"""
    try:
        # Extract session ID from path
        session_id = path.split('/status/')[-1]
        execution_name = session_id.replace('-', '_')

        print(f"[API] Getting status for session: {session_id}")

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
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_result(event, path):
    """Handle GET /result/{session_id} - Get final result from S3"""
    try:
        # Extract session ID from path
        session_id = path.split('/result/')[-1]

        print(f"[API] Getting result for session: {session_id}")

        # Get result from S3
        result_key = f"{session_id}/result.json"
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
        result = json.loads(obj['Body'].read())

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(result)
        }

    except s3.exceptions.NoSuchKey:
        return {
            'statusCode': 404,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Result not found'})
        }
    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_user_videos(event, path):
    """Handle GET /user/{user_id}/videos - Get all videos for a user"""
    try:
        # Extract user ID from path
        user_id = path.split('/user/')[-1].split('/videos')[0]

        print(f"[API] Getting videos for user: {user_id}")

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
                        'clips': result.get('clips', [])
                    })
                except s3.exceptions.NoSuchKey:
                    # Result not yet available, check if processing
                    videos.append({
                        'session_id': session_id,
                        'status': 'processing',
                        'clips_count': 0
                    })
                except Exception as e:
                    print(f"[API] Error getting result for {session_id}: {str(e)}")
                    continue

        # Sort by created_at descending (newest first)
        videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'user_id': user_id,
                'total_videos': len(videos),
                'videos': videos
            })
        }

    except Exception as e:
        print(f"[API] Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }
