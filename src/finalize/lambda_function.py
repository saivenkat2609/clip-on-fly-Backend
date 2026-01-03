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

# DEBUG: Check if firebase-admin is accessible
print(f"[DEBUG] sys.path: {sys.path[:3]}")  # Show first 3 paths
import os as os_check
if os_check.path.exists('/opt/python'):
    print(f"[DEBUG] /opt/python exists")
    opt_contents = os_check.listdir('/opt/python')
    print(f"[DEBUG] /opt/python contents: {opt_contents[:10]}")  # First 10 items
    if 'firebase_admin' in opt_contents:
        print("[DEBUG] ✅ firebase_admin found in /opt/python")
    else:
        print("[DEBUG] ❌ firebase_admin NOT in /opt/python")
else:
    print("[DEBUG] ❌ /opt/python does not exist")

# Import scalability utilities (graceful fallback)
try:
    from shared.logger import get_logger
    from shared.websocket_notifier import notify_processing_complete
    from shared.dynamodb_client import update_video_session
    from shared.metrics import track_video_processing_complete
    UTILITIES_AVAILABLE = True
    print("[Finalize] Scalability utilities loaded successfully")
except ImportError as e:
    print(f"[Finalize] Warning: Shared utilities not available: {str(e)}")
    UTILITIES_AVAILABLE = False

# HIGH PRIORITY FIX #9: Import Firebase Admin SDK-based Firestore client
try:
    from shared.firestore_client import get_firestore_client
    FIRESTORE_CLIENT_AVAILABLE = True
    print("[Finalize] Firestore Admin SDK client loaded successfully")
except ImportError as e:
    print(f"[Finalize] Warning: Firestore client not available: {str(e)}")
    FIRESTORE_CLIENT_AVAILABLE = False

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


def update_firestore_video(user_id, session_id, data):
    """
    HIGH PRIORITY FIX #9: Update video status in Firestore using Admin SDK
    Replaced Firebase Web API Key with Admin SDK for secure backend authentication
    """
    if not user_id:
        print("[Firestore] Skipping update - missing user_id")
        return

    if not FIRESTORE_CLIENT_AVAILABLE:
        print("[Firestore] WARNING: Firestore client not available, skipping update")
        return

    try:
        db = get_firestore_client()
        if not db:
            print("[Firestore] ERROR: Could not initialize Firestore client")
            return

        # Reference to the video document
        doc_ref = db.collection('users').document(user_id).collection('videos').document(session_id)

        # Build update data
        update_data = {
            'status': data.get('status', 'completed'),
            'completedAt': datetime.utcnow()
        }

        # Add clips data
        if "clips" in data and data["clips"]:
            clips_array = []
            # Calculate expiry: 3 days from now
            expiry_time = datetime.utcnow() + timedelta(days=3)

            for clip in data["clips"]:
                clip_obj = {
                    "clipIndex": clip["clip_index"],
                    "downloadUrl": clip["download_url"],
                    "s3Key": clip["s3_key"],
                    "expiresAt": expiry_time
                }

                # Add optional fields if present
                if "title" in clip and clip["title"]:
                    clip_obj["title"] = clip["title"]
                if "virality_score" in clip and clip["virality_score"] is not None:
                    clip_obj["virality_score"] = clip["virality_score"]
                if "duration" in clip and clip["duration"] is not None:
                    clip_obj["duration"] = clip["duration"]
                if "startTime" in clip and clip["startTime"] is not None:
                    clip_obj["startTime"] = clip["startTime"]
                if "endTime" in clip and clip["endTime"] is not None:
                    clip_obj["endTime"] = clip["endTime"]
                if "template_id" in clip and clip["template_id"]:
                    clip_obj["template_id"] = clip["template_id"]
                if "template_name" in clip and clip["template_name"]:
                    clip_obj["template_name"] = clip["template_name"]

                # Add score breakdown if present
                if "score_breakdown" in clip and clip["score_breakdown"]:
                    clip_obj["score_breakdown"] = clip["score_breakdown"]

                clips_array.append(clip_obj)

            update_data["clips"] = clips_array

        # Add video info if present
        if "video_info" in data and data["video_info"]:
            video_info = data["video_info"]
            update_data["videoInfo"] = {
                "title": video_info.get("title", ""),
                "duration": video_info.get("duration", 0),
                "thumbnail": video_info.get("thumbnail", "")
            }

        # Add error if present
        if "error" in data:
            update_data["error"] = data["error"]
            update_data["status"] = "failed"

        # Update document (merge with existing fields)
        doc_ref.set(update_data, merge=True)
        print(f"[Firestore] ✓ Successfully updated video {session_id}")

    except Exception as e:
        print(f"[Firestore] Error updating document: {str(e)}")
        import traceback
        traceback.print_exc()


def update_user_stats(user_id, total_clips):
    """
    HIGH PRIORITY FIX #9: Increment user's totalClips count in Firestore using Admin SDK
    Replaced Firebase Web API Key with Admin SDK for secure backend authentication
    """
    if not user_id:
        print("[Firestore] Skipping stats update - missing user_id")
        return

    if not FIRESTORE_CLIENT_AVAILABLE:
        print("[Firestore] WARNING: Firestore client not available, skipping stats update")
        return

    try:
        db = get_firestore_client()
        if not db:
            print("[Firestore] ERROR: Could not initialize Firestore client")
            return

        # Import firestore for FieldValue
        from firebase_admin import firestore as admin_firestore

        # Reference to user document
        user_ref = db.collection('users').document(user_id)

        # Use Firestore increment to atomically add to totalClips
        user_ref.set({
            'totalClips': admin_firestore.Increment(total_clips)
        }, merge=True)

        print(f"[Firestore] ✓ Incremented user stats: totalClips += {total_clips}")

    except Exception as e:
        print(f"[Firestore] Error updating user stats: {str(e)}")
        import traceback
        traceback.print_exc()

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

        # Update Firestore with completed video data
        if user_id:
            update_firestore_video(user_id, session_id, result)
            update_user_stats(user_id, len(clip_urls))

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
        raise Exception(f"Failed to finalize: {str(e)}")
