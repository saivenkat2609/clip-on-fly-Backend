"""
Firestore Client for incremental clip updates
Allows Lambda functions to add clips one-by-one as they're processed

HIGH PRIORITY FIX #9: Migrated from Firebase Web API Key to Firebase Admin SDK
- Web API keys are meant for frontend and can be extracted from client bundles
- Admin SDK uses service account credentials for secure backend access
- Prevents attackers from directly manipulating Firestore data

ROBUST RESILIENCE UPDATE:
- Added retry logic with exponential backoff for all Firestore operations
- Better error handling and validation for Firebase credentials
- CloudWatch metrics for monitoring Firestore failures
"""
import os
import json
import base64
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any

# HIGH PRIORITY FIX #9: Use Firebase Admin SDK instead of REST API
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_ADMIN_AVAILABLE = True
except ImportError:
    print("[Firestore] WARNING: firebase-admin not installed. Install with: pip install firebase-admin")
    FIREBASE_ADMIN_AVAILABLE = False

FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframeai-87b24')

# Initialize Firebase Admin SDK (singleton pattern)
_firebase_app = None
_firestore_client = None


def retry_with_backoff(func: Callable, max_attempts: int = 3, base_delay: float = 2.0, operation_name: str = "operation") -> Any:
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry (no-argument callable)
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 2.0)
        operation_name: Name of the operation for logging

    Returns:
        Result of the function

    Raises:
        Last exception if all retries fail

    Backoff schedule:
        - Attempt 1: No delay
        - Attempt 2: 2 seconds
        - Attempt 3: 4 seconds
        - Attempt 4: 8 seconds (if max_attempts > 3)
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[Firestore Retry] Attempt {attempt}/{max_attempts}: {operation_name}")
            result = func()

            if attempt > 1:
                print(f"[Firestore Retry] ✓ {operation_name} succeeded on attempt {attempt}")

            return result

        except Exception as e:
            last_exception = e
            print(f"[Firestore Retry] ✗ Attempt {attempt} failed: {str(e)}")

            # Don't sleep after last attempt
            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff: 2s, 4s, 8s
                print(f"[Firestore Retry] Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                print(f"[Firestore Retry] All {max_attempts} attempts failed for {operation_name}")

                # Emit CloudWatch metric for monitoring
                try:
                    import boto3
                    cloudwatch = boto3.client('cloudwatch')
                    cloudwatch.put_metric_data(
                        Namespace='OpusClip/Firestore',
                        MetricData=[
                            {
                                'MetricName': 'FirestoreUpdateFailed',
                                'Value': 1,
                                'Unit': 'Count',
                                'Dimensions': [
                                    {'Name': 'Operation', 'Value': operation_name}
                                ]
                            }
                        ]
                    )
                    print(f"[Firestore Retry] ⚠️ Emitted CloudWatch metric: FirestoreUpdateFailed")
                except Exception as metric_error:
                    print(f"[Firestore Retry] Warning: Failed to emit metric: {metric_error}")

    # Re-raise the last exception
    if last_exception:
        raise last_exception


def get_firestore_client():
    """
    Get or initialize Firestore client using Admin SDK

    Returns:
        Firestore client or None if initialization fails

    Supports multiple credential sources (in order of priority):
        1. FIREBASE_ADMIN_SDK_BASE64 - Base64-encoded service account JSON (for Lambda env vars)
        2. GOOGLE_APPLICATION_CREDENTIALS - Path to service account JSON file
        3. FIREBASE_SERVICE_ACCOUNT_PATH - Path to service account JSON file
        4. Default credentials (works in some GCP/AWS environments)
    """
    global _firebase_app, _firestore_client

    if not FIREBASE_ADMIN_AVAILABLE:
        print("[Firestore] ERROR: firebase-admin package not available")
        return None

    # Return existing client if already initialized
    if _firestore_client is not None:
        return _firestore_client

    try:
        # Initialize Firebase Admin if not already done
        if not _firebase_app:
            cred_path = None

            # Option 1: Base64-encoded credentials in environment variable (for Lambda)
            # This allows storing service account JSON directly in Lambda env vars
            base64_creds = os.environ.get('FIREBASE_ADMIN_SDK_BASE64')
            if base64_creds:
                try:
                    print("[Firestore] Decoding base64 credentials from FIREBASE_ADMIN_SDK_BASE64")

                    # ROBUST FIX: Validate base64 string before decoding
                    if not base64_creds or base64_creds.strip() == '':
                        raise ValueError("FIREBASE_ADMIN_SDK_BASE64 is empty")

                    # Remove any whitespace/newlines that might corrupt the base64 string
                    base64_creds = base64_creds.strip().replace('\n', '').replace('\r', '').replace(' ', '')

                    # Decode base64 string to JSON
                    creds_json = base64.b64decode(base64_creds).decode('utf-8')

                    # ROBUST FIX: Validate JSON structure before writing
                    if not creds_json or creds_json.strip() == '':
                        raise ValueError("Decoded credentials are empty")

                    # Validate it's valid JSON
                    creds_dict = json.loads(creds_json)

                    # Validate required fields for service account
                    required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
                    missing_fields = [field for field in required_fields if field not in creds_dict]
                    if missing_fields:
                        raise ValueError(f"Service account JSON missing required fields: {missing_fields}")

                    if creds_dict.get('type') != 'service_account':
                        raise ValueError(f"Invalid credential type: {creds_dict.get('type')} (expected 'service_account')")

                    # Write to /tmp directory (writable in Lambda)
                    tmp_cred_path = '/tmp/firebase-credentials.json'
                    with open(tmp_cred_path, 'w') as f:
                        f.write(creds_json)

                    cred_path = tmp_cred_path
                    print(f"[Firestore] ✓ Credentials validated and written to {tmp_cred_path}")
                    print(f"[Firestore] ✓ Project ID: {creds_dict.get('project_id')}")
                    print(f"[Firestore] ✓ Client Email: {creds_dict.get('client_email')}")
                except json.JSONDecodeError as e:
                    print(f"[Firestore] ERROR: Invalid JSON in decoded credentials: {str(e)}")
                    print(f"[Firestore] ERROR: Decoded content preview: {creds_json[:100] if 'creds_json' in locals() else 'N/A'}...")
                    print(f"[Firestore] ERROR: Please verify FIREBASE_ADMIN_SDK_BASE64 env var is correctly base64-encoded service account JSON")
                    return None
                except ValueError as e:
                    print(f"[Firestore] ERROR: Invalid credentials: {str(e)}")
                    print(f"[Firestore] ERROR: Please verify FIREBASE_ADMIN_SDK_BASE64 contains valid service account JSON")
                    return None
                except Exception as e:
                    print(f"[Firestore] ERROR: Failed to decode base64 credentials: {str(e)}")
                    print(f"[Firestore] ERROR: Base64 length: {len(base64_creds) if base64_creds else 0} chars")
                    return None

            # Option 2 & 3: Check for service account file path in environment variables
            if not cred_path:
                cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or \
                           os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')

            if cred_path and os.path.exists(cred_path):
                # Use service account file
                print(f"[Firestore] Initializing with service account: {cred_path}")
                cred = credentials.Certificate(cred_path)
                _firebase_app = firebase_admin.initialize_app(cred)
            else:
                # Option 4: Try default credentials (works in some GCP/AWS environments)
                print("[Firestore] Attempting to use default credentials")
                _firebase_app = firebase_admin.initialize_app()

        # Get Firestore client
        _firestore_client = firestore.client()
        print("[Firestore] ✓ Admin SDK initialized successfully")
        return _firestore_client

    except ValueError as e:
        # Firebase app already initialized - this is OK
        if "already exists" in str(e):
            try:
                _firebase_app = firebase_admin.get_app()
                _firestore_client = firestore.client()
                print("[Firestore] ✓ Using existing Admin SDK instance")
                return _firestore_client
            except Exception as inner_e:
                print(f"[Firestore] ERROR: Failed to get existing app: {str(inner_e)}")
                return None
        else:
            print(f"[Firestore] ERROR: Failed to initialize Firebase Admin: {str(e)}")
            return None
    except Exception as e:
        print(f"[Firestore] ERROR: Unexpected error initializing Firebase Admin: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def add_clip_to_firestore(user_id: str, session_id: str, clip_data: Dict) -> bool:
    """
    Add a single clip to Firestore video document (incremental update)
    Uses Firebase Admin SDK for secure backend authentication
    WITH RETRY LOGIC: Automatically retries up to 3 times with exponential backoff

    Args:
        user_id: Firebase user ID
        session_id: Video session ID
        clip_data: Dict with clip information:
            - clip_index: int
            - download_url: str
            - s3_key: str
            - title: str (optional)
            - duration: float (optional)
            - startTime: float (optional)
            - endTime: float (optional)
            - virality_score: int (optional)
            - score_breakdown: dict (optional)
            - template_id: str (optional)
            - template_name: str (optional)

    Returns:
        True if successful, False otherwise
    """
    if not user_id:
        print("[Firestore] Skipping clip update - missing user_id")
        return False

    # Get Firestore client
    db = get_firestore_client()
    if not db:
        print("[Firestore] ERROR: Could not initialize Firestore client")
        return False

    def _add_clip_operation():
        """Inner function for retry logic"""
        # Reference to the video document
        doc_ref = db.collection('users').document(user_id).collection('videos').document(session_id)

        # Step 1: Fetch current document to get existing clips
        print(f"[Firestore] Fetching current clips for session {session_id}")
        doc = doc_ref.get()

        existing_clips = []
        if doc.exists:
            doc_data = doc.to_dict()
            existing_clips = doc_data.get('clips', [])
            print(f"[Firestore] Found {len(existing_clips)} existing clips")
        else:
            print(f"[Firestore] Document not found, will create with first clip")

        # Step 2: Build new clip object
        expiry_time = datetime.utcnow() + timedelta(days=3)

        new_clip = {
            "clipIndex": clip_data["clip_index"],
            "downloadUrl": clip_data["download_url"],
            "s3Key": clip_data["s3_key"],
            "expiresAt": expiry_time
        }

        # Add optional fields
        if "title" in clip_data and clip_data["title"]:
            new_clip["title"] = clip_data["title"]
        if "duration" in clip_data and clip_data["duration"] is not None:
            new_clip["duration"] = clip_data["duration"]
        if "startTime" in clip_data and clip_data["startTime"] is not None:
            new_clip["startTime"] = clip_data["startTime"]
        if "endTime" in clip_data and clip_data["endTime"] is not None:
            new_clip["endTime"] = clip_data["endTime"]
        if "virality_score" in clip_data and clip_data["virality_score"] is not None:
            new_clip["virality_score"] = clip_data["virality_score"]
        if "template_id" in clip_data and clip_data["template_id"]:
            new_clip["template_id"] = clip_data["template_id"]
        if "template_name" in clip_data and clip_data["template_name"]:
            new_clip["template_name"] = clip_data["template_name"]

        # Add score breakdown
        if "score_breakdown" in clip_data and clip_data["score_breakdown"]:
            new_clip["score_breakdown"] = clip_data["score_breakdown"]

        # Step 3: Check if clip already exists (by clipIndex)
        clip_index = clip_data["clip_index"]
        clip_exists = False

        for i, existing_clip in enumerate(existing_clips):
            if existing_clip.get('clipIndex') == clip_index:
                # Replace existing clip
                existing_clips[i] = new_clip
                clip_exists = True
                print(f"[Firestore] Updating existing clip {clip_index}")
                break

        if not clip_exists:
            # Append new clip
            existing_clips.append(new_clip)
            print(f"[Firestore] Adding new clip {clip_index}")

        # Step 4: Update document with new clips array
        # Use set with merge=True to update only the clips field
        doc_ref.set({
            'clips': existing_clips
        }, merge=True)

        print(f"[Firestore] ✓ Clip {clip_index} added to Firestore successfully")
        return True

    # Execute with retry logic
    try:
        return retry_with_backoff(
            _add_clip_operation,
            max_attempts=3,
            operation_name=f"add_clip_{clip_data.get('clip_index', '?')}_to_firestore"
        )
    except Exception as e:
        print(f"[Firestore] ❌ Final error after all retries: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def update_video_status(user_id: str, session_id: str, status: str, additional_data: Optional[Dict] = None) -> bool:
    """
    Update video processing status in Firestore

    Args:
        user_id: Firebase user ID
        session_id: Video session ID
        status: Status string (e.g., 'processing', 'completed', 'failed')
        additional_data: Optional dict with additional fields to update

    Returns:
        True if successful, False otherwise
    """
    if not user_id:
        print("[Firestore] Skipping status update - missing user_id")
        return False

    db = get_firestore_client()
    if not db:
        print("[Firestore] ERROR: Could not initialize Firestore client")
        return False

    try:
        doc_ref = db.collection('users').document(user_id).collection('videos').document(session_id)

        update_data = {
            'status': status,
            'updatedAt': firestore.SERVER_TIMESTAMP
        }

        # Add any additional data
        if additional_data:
            update_data.update(additional_data)

        doc_ref.set(update_data, merge=True)
        print(f"[Firestore] ✓ Status updated to '{status}' for session {session_id}")
        return True

    except Exception as e:
        print(f"[Firestore] Error updating status: {str(e)}")
        return False


def get_video_document(user_id: str, session_id: str) -> Optional[Dict]:
    """
    Retrieve video document from Firestore

    Args:
        user_id: Firebase user ID
        session_id: Video session ID

    Returns:
        Document data as dict, or None if not found/error
    """
    if not user_id:
        print("[Firestore] Cannot get document - missing user_id")
        return None

    db = get_firestore_client()
    if not db:
        print("[Firestore] ERROR: Could not initialize Firestore client")
        return None

    try:
        doc_ref = db.collection('users').document(user_id).collection('videos').document(session_id)
        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()
        else:
            print(f"[Firestore] Document not found: {session_id}")
            return None

    except Exception as e:
        print(f"[Firestore] Error retrieving document: {str(e)}")
        return None


def update_video_completion_with_clips(user_id: str, session_id: str, clips: list, video_info: dict = None) -> bool:
    """
    Update video status to completed and add all clips in a single atomic operation.
    Specifically designed for finalize lambda with retry logic.
    WITH RETRY LOGIC: Automatically retries up to 3 times with exponential backoff

    Args:
        user_id: Firebase user ID
        session_id: Video session ID
        clips: List of clip objects with download URLs
        video_info: Optional video metadata

    Returns:
        True if successful, False otherwise
    """
    if not user_id:
        print("[Firestore] Skipping completion update - missing user_id")
        return False

    db = get_firestore_client()
    if not db:
        print("[Firestore] ERROR: Could not initialize Firestore client")
        return False

    def _update_completion_operation():
        """Inner function for retry logic"""
        doc_ref = db.collection('users').document(user_id).collection('videos').document(session_id)

        # Build update data
        update_data = {
            'status': 'completed',
            'completedAt': datetime.utcnow()
        }

        # Add clips
        if clips:
            clips_array = []
            expiry_time = datetime.utcnow() + timedelta(days=3)

            for clip in clips:
                clip_obj = {
                    "clipIndex": clip.get("clip_index"),
                    "downloadUrl": clip.get("download_url"),
                    "s3Key": clip.get("s3_key"),
                    "expiresAt": expiry_time
                }

                # Add optional fields
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
                if "score_breakdown" in clip and clip["score_breakdown"]:
                    clip_obj["score_breakdown"] = clip["score_breakdown"]

                clips_array.append(clip_obj)

            update_data["clips"] = clips_array

        # Add video info
        if video_info:
            update_data["videoInfo"] = {
                "title": video_info.get("title", ""),
                "duration": video_info.get("duration", 0),
                "thumbnail": video_info.get("thumbnail", "")
            }

        # Update document
        doc_ref.set(update_data, merge=True)
        print(f"[Firestore] ✓ Successfully updated video {session_id} with status=completed and {len(clips)} clips")
        return True

    # Execute with retry logic
    try:
        return retry_with_backoff(
            _update_completion_operation,
            max_attempts=3,
            operation_name=f"update_video_completion_{session_id}"
        )
    except Exception as e:
        print(f"[Firestore] ❌ Final error after all retries: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
