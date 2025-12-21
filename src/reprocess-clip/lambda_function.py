"""
Lambda Function: Reprocess Clip with New Template
Allows users to change template styling without re-running entire pipeline
OPTIMIZED: Reuses original video and transcript from S3
"""
import json
import boto3
import os
import subprocess

def get_storage_client():
    """Get S3-compatible storage client"""
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
    return boto3.client('s3')

s3 = get_storage_client()
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')
STEP_FUNCTIONS_ARN = os.environ.get('STEP_FUNCTIONS_ARN')
sfn_client = boto3.client('stepfunctions')

def lambda_handler(event, context):
    """
    Reprocess a single clip with new template

    Input:
    {
        "session_id": "abc123",
        "clip_index": 0,
        "template_id": "creative-bold-energetic"
    }
    """
    try:
        session_id = event['session_id']
        clip_index = event['clip_index']
        new_template_id = event['template_id']

        print(f"[ReprocessClip] Session: {session_id}")
        print(f"[ReprocessClip] Clip Index: {clip_index}")
        print(f"[ReprocessClip] New Template: {new_template_id}")

        # Load original clip metadata from S3
        result_key = f"{session_id}/result.json"

        try:
            result_obj = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
            result_data = json.loads(result_obj['Body'].read())
            print(f"[ReprocessClip] Loaded result.json with {len(result_data.get('clips', []))} clips")
        except Exception as e:
            print(f"[ReprocessClip] Failed to load result.json: {e}")
            raise Exception(f"Could not find original clip data for session {session_id}")

        # Find the clip to reprocess
        clips = result_data.get('clips', [])
        target_clip = None

        for clip in clips:
            if clip.get('clip_index') == clip_index:
                target_clip = clip
                break

        if not target_clip:
            raise Exception(f"Clip index {clip_index} not found in session {session_id}")

        print(f"[ReprocessClip] Found clip: {target_clip.get('title', 'Untitled')}")

        # Get original video S3 key
        s3_video_key = result_data.get('s3_video_key')
        if not s3_video_key:
            # Try alternative location
            s3_video_key = f"{session_id}/original_video.mp4"

        print(f"[ReprocessClip] Original video: {s3_video_key}")

        # Invoke the regular process-clip Lambda with new template
        lambda_client = boto3.client('lambda')

        process_clip_payload = {
            'session_id': session_id,
            's3_video_key': s3_video_key,
            'clip': target_clip,
            'template_id': new_template_id  # NEW TEMPLATE!
        }

        print(f"[ReprocessClip] Invoking opus-process-clip Lambda...")

        response = lambda_client.invoke(
            FunctionName='opus-process-clip',
            InvocationType='RequestResponse',
            Payload=json.dumps(process_clip_payload)
        )

        response_payload = json.loads(response['Payload'].read())
        print(f"[ReprocessClip] Process-clip response: {response_payload}")

        if response_payload.get('statusCode') != 200:
            raise Exception(f"Process-clip failed: {response_payload}")

        # Update result.json with new template info
        for clip in clips:
            if clip.get('clip_index') == clip_index:
                clip['template_id'] = new_template_id
                clip['template_name'] = response_payload.get('template_name', new_template_id)
                clip['s3_key'] = response_payload.get('s3_clip_key')
                # Regenerate download URL
                download_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': response_payload.get('s3_clip_key')},
                    ExpiresIn=259200  # 3 days
                )
                clip['download_url'] = download_url
                print(f"[ReprocessClip] Updated clip metadata with new template")
                break

        # Save updated result.json
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=result_key,
            Body=json.dumps(result_data, indent=2),
            ContentType='application/json'
        )

        print(f"[ReprocessClip] Updated result.json in S3")

        return {
            'statusCode': 200,
            'session_id': session_id,
            'clip_index': clip_index,
            'template_id': new_template_id,
            'template_name': response_payload.get('template_name'),
            's3_clip_key': response_payload.get('s3_clip_key'),
            'download_url': clip['download_url'],
            'message': 'Clip reprocessed successfully with new template'
        }

    except Exception as e:
        print(f"[ReprocessClip] Error: {str(e)}")
        import traceback
        print(f"[ReprocessClip] Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to reprocess clip: {str(e)}")
