"""
Reconciliation Lambda - Auto-Healing for Stuck Videos
Runs every 5 minutes via EventBridge (CloudWatch Events)

PURPOSE:
- Finds videos stuck in "processing" state for > 10 minutes
- Checks if result.json exists in S3
- If exists, syncs data from S3 to Firestore
- Acts as automatic self-healing for Firestore sync failures

TRIGGER:
- EventBridge rule: rate(5 minutes)
- Or manual invocation for testing

BENEFITS:
- Zero manual intervention required
- Catches edge cases (Lambda timeout, network issues, etc.)
- Users see completed clips within 5 minutes even if finalize fails
"""

import json
import boto3
from botocore.config import Config
import os
import sys
from datetime import datetime, timedelta

# Add Lambda Layer path
sys.path.insert(0, '/opt/python')

# Import Firestore client with retry logic
try:
    from shared.firestore_client import get_firestore_client, update_video_completion_with_clips
    FIRESTORE_AVAILABLE = True
    print("[Reconcile] Firestore client loaded successfully")
except ImportError as e:
    print(f"[Reconcile] ERROR: Firestore client not available: {e}")
    FIRESTORE_AVAILABLE = False

# Initialize clients
def get_storage_client():
    """Get S3-compatible storage client"""
    endpoint = os.environ.get('R2_ENDPOINT') or os.environ.get('STORAGE_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')

    s3_config = Config(signature_version='s3v4')

    if endpoint:
        print(f"[Reconcile] Using custom endpoint: {endpoint}")
        return boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=s3_config,
            region_name=os.environ.get('AWS_REGION', 'auto')
        )
    print("[Reconcile] Using AWS S3 (default)")
    return boto3.client('s3', config=s3_config)

s3 = get_storage_client()
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')

# Configuration
STUCK_VIDEO_THRESHOLD_MINUTES = int(os.environ.get('STUCK_VIDEO_THRESHOLD_MINUTES', '10'))
MAX_VIDEOS_PER_RUN = int(os.environ.get('MAX_VIDEOS_PER_RUN', '20'))


def find_stuck_videos():
    """
    Query Firestore for videos stuck in 'processing' state for > threshold minutes

    Returns:
        List of dicts with user_id, session_id, created_at
    """
    if not FIRESTORE_AVAILABLE:
        print("[Reconcile] Firestore not available, cannot query stuck videos")
        return []

    try:
        db = get_firestore_client()
        if not db:
            print("[Reconcile] Could not initialize Firestore client")
            return []

        # Calculate threshold timestamp
        threshold_time = datetime.utcnow() - timedelta(minutes=STUCK_VIDEO_THRESHOLD_MINUTES)

        print(f"[Reconcile] Searching for videos stuck since before {threshold_time.isoformat()}")

        stuck_videos = []

        # Query all users (in production, you might want to batch this)
        users_ref = db.collection('users')

        # For efficiency, limit to a reasonable number of users per run
        # In production, implement pagination or use a DynamoDB index
        for user_doc in users_ref.stream():
            user_id = user_doc.id

            # Query videos for this user that are still processing
            videos_ref = user_doc.reference.collection('videos') \
                .where('status', '==', 'processing') \
                .where('createdAt', '<', threshold_time) \
                .limit(MAX_VIDEOS_PER_RUN)

            for video_doc in videos_ref.stream():
                video_data = video_doc.to_dict()
                stuck_videos.append({
                    'user_id': user_id,
                    'session_id': video_doc.id,
                    'created_at': video_data.get('createdAt'),
                    'project_name': video_data.get('projectName', 'Unknown')
                })

            # Stop if we've found enough videos to process
            if len(stuck_videos) >= MAX_VIDEOS_PER_RUN:
                break

        print(f"[Reconcile] Found {len(stuck_videos)} stuck videos")
        return stuck_videos

    except Exception as e:
        print(f"[Reconcile] Error querying stuck videos: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def check_s3_result_exists(user_id, session_id):
    """
    Check if result.json exists in S3 for this session

    Returns:
        (exists: bool, result_key: str or None, result_data: dict or None)
    """
    # Try user-specific location first (newer)
    result_key = f"users/{user_id}/{session_id}/result.json"

    try:
        print(f"[Reconcile] Checking S3: {result_key}")
        response = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
        result_data = json.loads(response['Body'].read())

        print(f"[Reconcile] ✓ Found result in S3 with {len(result_data.get('clips', []))} clips")
        return True, result_key, result_data

    except s3.exceptions.NoSuchKey:
        # Try legacy location
        result_key = f"{session_id}/result.json"
        try:
            print(f"[Reconcile] Trying legacy location: {result_key}")
            response = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
            result_data = json.loads(response['Body'].read())

            print(f"[Reconcile] ✓ Found result in legacy S3 location with {len(result_data.get('clips', []))} clips")
            return True, result_key, result_data

        except s3.exceptions.NoSuchKey:
            print(f"[Reconcile] ✗ No result.json found in S3")
            return False, None, None

    except Exception as e:
        print(f"[Reconcile] Error checking S3: {str(e)}")
        return False, None, None


def sync_result_to_firestore(user_id, session_id, result_data):
    """
    Sync result from S3 to Firestore

    Returns:
        True if successful, False otherwise
    """
    if not FIRESTORE_AVAILABLE:
        print("[Reconcile] Firestore not available")
        return False

    try:
        clips = result_data.get('clips', [])
        video_info = result_data.get('video_info', {})

        print(f"[Reconcile] Syncing {len(clips)} clips to Firestore for session {session_id}")

        # Use the retry-enabled function
        success = update_video_completion_with_clips(
            user_id=user_id,
            session_id=session_id,
            clips=clips,
            video_info=video_info
        )

        if success:
            print(f"[Reconcile] ✓ Successfully synced session {session_id} to Firestore")
            return True
        else:
            print(f"[Reconcile] ✗ Failed to sync session {session_id}")
            return False

    except Exception as e:
        print(f"[Reconcile] Error syncing to Firestore: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def lambda_handler(event, context):
    """
    Reconciliation Lambda handler

    Runs periodically to auto-heal stuck videos
    """
    print("[Reconcile] ========== RECONCILIATION RUN STARTED ==========")
    print(f"[Reconcile] Threshold: {STUCK_VIDEO_THRESHOLD_MINUTES} minutes")
    print(f"[Reconcile] Max videos per run: {MAX_VIDEOS_PER_RUN}")

    if not FIRESTORE_AVAILABLE:
        print("[Reconcile] ERROR: Firestore client not available, cannot run reconciliation")
        return {
            'statusCode': 500,
            'error': 'Firestore client not available'
        }

    # Find stuck videos
    stuck_videos = find_stuck_videos()

    if not stuck_videos:
        print("[Reconcile] No stuck videos found. All systems healthy! ✓")
        return {
            'statusCode': 200,
            'message': 'No stuck videos found',
            'reconciled_count': 0
        }

    print(f"[Reconcile] Processing {len(stuck_videos)} stuck videos...")

    reconciled_count = 0
    failed_count = 0
    not_ready_count = 0

    for video in stuck_videos:
        user_id = video['user_id']
        session_id = video['session_id']
        project_name = video['project_name']

        print(f"\n[Reconcile] --- Processing: {project_name} ({session_id[:8]}...)")

        # Check if result exists in S3
        exists, result_key, result_data = check_s3_result_exists(user_id, session_id)

        if not exists:
            not_ready_count += 1
            print(f"[Reconcile] ⏳ Video still processing (no result.json in S3)")
            continue

        # Result exists in S3, sync to Firestore
        success = sync_result_to_firestore(user_id, session_id, result_data)

        if success:
            reconciled_count += 1
            print(f"[Reconcile] ✓ Reconciled: {project_name}")
        else:
            failed_count += 1
            print(f"[Reconcile] ✗ Failed to reconcile: {project_name}")

    # Emit CloudWatch metrics
    try:
        cloudwatch = boto3.client('cloudwatch')

        metrics = [
            {
                'MetricName': 'StuckVideosFound',
                'Value': len(stuck_videos),
                'Unit': 'Count'
            },
            {
                'MetricName': 'VideosReconciled',
                'Value': reconciled_count,
                'Unit': 'Count'
            },
            {
                'MetricName': 'ReconciliationFailed',
                'Value': failed_count,
                'Unit': 'Count'
            }
        ]

        cloudwatch.put_metric_data(
            Namespace='OpusClip/Reconciliation',
            MetricData=metrics
        )

        print(f"[Reconcile] ✓ Emitted CloudWatch metrics")

    except Exception as metric_err:
        print(f"[Reconcile] Warning: Failed to emit metrics: {metric_err}")

    print(f"\n[Reconcile] ========== RECONCILIATION RUN COMPLETE ==========")
    print(f"[Reconcile] Total stuck videos: {len(stuck_videos)}")
    print(f"[Reconcile] Successfully reconciled: {reconciled_count}")
    print(f"[Reconcile] Still processing: {not_ready_count}")
    print(f"[Reconcile] Failed: {failed_count}")

    return {
        'statusCode': 200,
        'stuck_videos_found': len(stuck_videos),
        'reconciled_count': reconciled_count,
        'not_ready_count': not_ready_count,
        'failed_count': failed_count
    }
