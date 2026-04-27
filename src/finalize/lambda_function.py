"""
Lambda Function 5: Finalize Processing
Aggregates results and generates pre-signed URLs
INTEGRATED: With logging, metrics, DynamoDB tracking, and WebSocket notifications
"""
import json
import boto3
from botocore.config import Config
import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
import sys

# Add Lambda Layer path
sys.path.insert(0, '/opt/python')
# Add shared modules path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import scalability utilities (graceful fallback)
try:
    from shared.logger import get_logger
    from shared.websocket_notifier import notify_processing_complete, notify_processing_error
    from shared.dynamodb_client import update_video_session
    from shared.metrics import track_video_processing_complete
    UTILITIES_AVAILABLE = True
    print("[Finalize] Scalability utilities loaded successfully")
except ImportError as e:
    print(f"[Finalize] Warning: Shared utilities not available: {str(e)}")
    UTILITIES_AVAILABLE = False

# Supabase config
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')


# Initialize logger if available
if UTILITIES_AVAILABLE:
    logger = get_logger('finalize')
else:
    logger = None

def get_storage_client():
    """Get S3-compatible storage client (supports AWS S3, Cloudflare R2, Backblaze B2, etc.)"""
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    # IMPORTANT: Configure SigV4 for R2 compatibility
    s3_config = Config(signature_version='s3v4')

    if endpoint:
        print(f"[Storage] Using custom endpoint: {endpoint}")
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=s3_config,  # Add SigV4 config
            region_name=os.environ.get('AWS_REGION', 'auto')
        )
    print("[Storage] Using AWS S3 (default)")
    return boto3.client('s3', config=s3_config)  # Add SigV4 config

s3 = get_storage_client()
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframeai-87b24')


def update_supabase_video(session_id, data):
    """Update video status and clips in Supabase via REST API."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("[Supabase] Skipping update - SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        return

    try:
        expiry_time = (datetime.utcnow() + timedelta(days=3)).isoformat() + 'Z'

        clips_array = []
        for clip in data.get('clips', []):
            clip_obj = {
                'clipIndex': clip['clip_index'],
                'downloadUrl': clip['download_url'],
                's3Key': clip['s3_key'],
                'expiresAt': expiry_time,
            }
            for field in ('title', 'virality_score', 'duration', 'startTime', 'endTime',
                          'template_id', 'template_name', 'score_breakdown'):
                if clip.get(field) is not None:
                    clip_obj[field] = clip[field]
            clips_array.append(clip_obj)

        update_payload = {
            'status': 'failed' if 'error' in data else data.get('status', 'completed'),
            'clips': clips_array,
            'completed_at': datetime.utcnow().isoformat() + 'Z',
        }
        if data.get('error'):
            update_payload['error'] = data['error']
        if data.get('video_info'):
            update_payload['video_info'] = data['video_info']

        url = f"{SUPABASE_URL}/rest/v1/videos?session_id=eq.{urllib.parse.quote(session_id)}"
        body = json.dumps(update_payload).encode('utf-8')
        req = urllib.request.Request(
            url, data=body, method='PATCH',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
                'apikey': SUPABASE_SERVICE_ROLE_KEY,
                'Prefer': 'return=minimal',
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[Supabase] ✓ Video {session_id} updated (HTTP {resp.status})")

    except Exception as e:
        print(f"[Supabase] Error updating video: {e}")


def update_supabase_user_stats(user_id, total_clips):
    """Increment total_clips for a user in Supabase via RPC."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return
    try:
        # Read current value then write back (Supabase REST has no atomic increment without RPC)
        url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{urllib.parse.quote(user_id)}&select=total_clips"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
            'apikey': SUPABASE_SERVICE_ROLE_KEY,
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
        current = rows[0].get('total_clips', 0) if rows else 0

        patch_url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{urllib.parse.quote(user_id)}"
        body = json.dumps({'total_clips': current + total_clips}).encode('utf-8')
        patch_req = urllib.request.Request(
            patch_url, data=body, method='PATCH',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
                'apikey': SUPABASE_SERVICE_ROLE_KEY,
                'Prefer': 'return=minimal',
            }
        )
        with urllib.request.urlopen(patch_req, timeout=5) as resp:
            print(f"[Supabase] ✓ User {user_id} total_clips → {current + total_clips}")
    except Exception as e:
        print(f"[Supabase] Error updating user stats: {e}")



def lambda_handler(event, context):
    """
    Finalize processing and generate download URLs

    Input event:
    {
        "session_id": "uuid",
        "processed_clips": [
            {
                "clip_index": 0,
                "s3_clip_key": "session_id/clips/clip_0.mp4"
            },
            ...
        ],
        "video_info": {...}
    }

    Output:
    {
        "session_id": "uuid",
        "status": "completed",
        "clips": [
            {
                "clip_index": 0,
                "download_url": "https://...",
                "s3_key": "..."
            }
        ],
        "video_info": {...}
    }
    """
    try:
        session_id = event['session_id']
        processed_clips = event.get('processed_clips', [])
        video_info = event.get('video_info', {})
        user_id = event.get('user_id', '')
        user_email = event.get('user_email', '')

        print(f"[Finalize] Session: {session_id}")
        print(f"[Finalize] User ID: {user_id}")
        print(f"[Finalize] Processing {len(processed_clips)} clips")

        # Log start
        if logger:
            logger.info("Finalizing clips", session_id=session_id, user_id=user_id, clip_count=len(processed_clips))

        # Calculate expiry timestamp (3 days from now)
        expiry_time = datetime.utcnow() + timedelta(days=3)
        expiry_unix = int(expiry_time.timestamp())
        expiry_iso = expiry_time.isoformat() + "Z"

        print(f"[Finalize] Clips will expire at: {expiry_iso}")

        # Generate download URLs
        clip_urls = []
        r2_public_domain = os.environ.get('R2_PUBLIC_DOMAIN', '')  # e.g., "pub-xxxxx.r2.dev" or "cdn.yourdomain.com"

        # Strip https:// or http:// if user accidentally included it
        if r2_public_domain:
            r2_public_domain = r2_public_domain.replace('https://', '').replace('http://', '').strip('/')

        for clip in processed_clips:
            s3_key = clip['s3_clip_key']

            # Generate URL based on configuration
            if r2_public_domain:
                # Use public R2 URL (no expiry, better for long-term)
                url = f"https://{r2_public_domain}/{s3_key}"
                print(f"[Finalize] Using public URL: {url}")
            else:
                # Fallback: Generate pre-signed URL (valid for 7 days)
                url = s3.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': BUCKET_NAME,
                        'Key': s3_key
                    },
                    ExpiresIn=604800  # 7 days (increased from 24 hours)
                )
                print(f"[Finalize] Using pre-signed URL (7 day expiry)")

            # Preserve all clip metadata (title, virality scores, etc.)
            clip_data = {
                'clip_index': clip['clip_index'],
                'download_url': url,
                's3_key': s3_key
            }

            # Add optional fields if present
            if 'duration' in clip:
                clip_data['duration'] = clip['duration']
            if 'start' in clip:
                clip_data['startTime'] = clip['start']
            if 'end' in clip:
                clip_data['endTime'] = clip['end']
            if 'title' in clip:
                clip_data['title'] = clip['title']
            if 'virality_score' in clip:
                clip_data['virality_score'] = clip['virality_score']
            if 'score_breakdown' in clip:
                clip_data['score_breakdown'] = clip['score_breakdown']
            if 'template_id' in clip:
                clip_data['template_id'] = clip['template_id']
            if 'template_name' in clip:
                clip_data['template_name'] = clip['template_name']

            clip_urls.append(clip_data)

        # Sort by clip index
        clip_urls.sort(key=lambda x: x['clip_index'])

        # Log what we're saving
        print(f"[Finalize] Prepared {len(clip_urls)} clips with metadata:")
        for clip in clip_urls:
            print(f"[Finalize] Clip {clip['clip_index']}: {clip.get('title', 'No title')} - Score: {clip.get('virality_score', 'N/A')}")

        result = {
            'session_id': session_id,
            'status': 'completed',
            'clips': clip_urls,
            'total_clips': len(clip_urls),
            'video_info': video_info,
            'user_id': user_id,
            'user_email': user_email
        }

        # Save result to S3 in user-specific directory
        if user_id:
            result_key = f"users/{user_id}/{session_id}/result.json"
        else:
            result_key = f"{session_id}/result.json"

        print(f"[Finalize] Saving result to S3: {result_key}")

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=result_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )

        print(f"[Finalize] Complete! Generated {len(clip_urls)} download URLs")

        # Update Supabase (primary) and Firestore (legacy fallback)
        if user_id:
            update_supabase_video(session_id, result)
            update_supabase_user_stats(user_id, len(clip_urls))

        # Update session and notify via WebSocket
        if UTILITIES_AVAILABLE and user_id:
            try:
                update_video_session(
                    session_id, user_id,
                    status='completed',
                    current_step='All clips ready',
                    clips_count=len(clip_urls)
                )
                notify_processing_complete(session_id, {'total_clips': len(clip_urls), 'status': 'completed'})
                track_video_processing_complete(session_id, len(clip_urls))
            except Exception as e:
                print(f"[Finalize] Warning: Notification failed: {e}")

        if logger:
            logger.info("Finalization complete", session_id=session_id, clip_count=len(clip_urls))

        return {
            'statusCode': 200,
            **result
        }

    except Exception as e:
        print(f"[Finalize] Error: {str(e)}")

        if 'session_id' in locals():
            try:
                update_supabase_video(session_id, {'error': str(e), 'status': 'failed'})
            except Exception as db_err:
                print(f"[Finalize] Failed to update DB status: {db_err}")
            if UTILITIES_AVAILABLE:
                try:
                    notify_processing_error(session_id, f"Finalization failed: {str(e)}")
                except Exception as ws_err:
                    print(f"[Finalize] Failed to send WS error: {ws_err}")

        raise Exception(f"Failed to finalize: {str(e)}")
