"""
Firestore Client for incremental clip updates
Allows Lambda functions to add clips one-by-one as they're processed
"""
import os
import urllib.request
import urllib.parse
import urllib.error
import json
from datetime import datetime, timedelta

FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframeai-87b24')
FIREBASE_WEB_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY', '')


def add_clip_to_firestore(user_id, session_id, clip_data):
    """
    Add a single clip to Firestore video document (incremental update)
    Uses arrayUnion-like behavior by fetching current clips and appending new one

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
    """
    if not user_id or not FIREBASE_WEB_API_KEY:
        print("[Firestore] Skipping clip update - missing user_id or API key")
        return False

    try:
        doc_url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/users/{user_id}/videos/{session_id}"

        # Step 1: Fetch current document to get existing clips
        print(f"[Firestore] Fetching current clips for session {session_id}")
        req = urllib.request.Request(doc_url, method='GET')
        req.add_header('Authorization', f'Bearer {FIREBASE_WEB_API_KEY}')

        try:
            with urllib.request.urlopen(req) as response:
                current_doc = json.loads(response.read().decode())
                existing_clips = []

                if 'fields' in current_doc and 'clips' in current_doc['fields']:
                    clips_array = current_doc['fields']['clips'].get('arrayValue', {}).get('values', [])
                    existing_clips = clips_array
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"[Firestore] Document not found, will create with first clip")
                existing_clips = []
            else:
                print(f"[Firestore] Error fetching document: {e}")
                return False

        # Step 2: Build new clip object
        expiry_time = datetime.utcnow() + timedelta(days=3)
        expiry_iso = expiry_time.isoformat() + "Z"

        new_clip_fields = {
            "clipIndex": {"integerValue": str(clip_data["clip_index"])},
            "downloadUrl": {"stringValue": clip_data["download_url"]},
            "s3Key": {"stringValue": clip_data["s3_key"]},
            "expiresAt": {"timestampValue": expiry_iso}
        }

        # Add optional fields
        if "title" in clip_data and clip_data["title"]:
            new_clip_fields["title"] = {"stringValue": clip_data["title"]}
        if "duration" in clip_data and clip_data["duration"] is not None:
            new_clip_fields["duration"] = {"doubleValue": clip_data["duration"]}
        if "startTime" in clip_data and clip_data["startTime"] is not None:
            new_clip_fields["startTime"] = {"doubleValue": clip_data["startTime"]}
        if "endTime" in clip_data and clip_data["endTime"] is not None:
            new_clip_fields["endTime"] = {"doubleValue": clip_data["endTime"]}
        if "virality_score" in clip_data and clip_data["virality_score"] is not None:
            new_clip_fields["virality_score"] = {"integerValue": str(clip_data["virality_score"])}
        if "template_id" in clip_data and clip_data["template_id"]:
            new_clip_fields["template_id"] = {"stringValue": clip_data["template_id"]}
        if "template_name" in clip_data and clip_data["template_name"]:
            new_clip_fields["template_name"] = {"stringValue": clip_data["template_name"]}

        # Add score breakdown
        if "score_breakdown" in clip_data and clip_data["score_breakdown"]:
            breakdown = clip_data["score_breakdown"]
            new_clip_fields["score_breakdown"] = {
                "mapValue": {
                    "fields": {
                        "hook": {"integerValue": str(breakdown.get("hook", 0))},
                        "flow": {"integerValue": str(breakdown.get("flow", 0))},
                        "engagement": {"integerValue": str(breakdown.get("engagement", 0))},
                        "trend": {"integerValue": str(breakdown.get("trend", 0))}
                    }
                }
            }

        new_clip = {
            "mapValue": {
                "fields": new_clip_fields
            }
        }

        # Step 3: Check if clip already exists (by clipIndex)
        clip_index = clip_data["clip_index"]
        clip_exists = False
        for i, existing_clip in enumerate(existing_clips):
            existing_index = existing_clip.get('mapValue', {}).get('fields', {}).get('clipIndex', {}).get('integerValue')
            if existing_index and int(existing_index) == clip_index:
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
        update_data = {
            "fields": {
                "clips": {
                    "arrayValue": {
                        "values": existing_clips
                    }
                }
            }
        }

        # Use PATCH to update only the clips field
        patch_url = f"{doc_url}?updateMask.fieldPaths=clips"
        req = urllib.request.Request(
            patch_url,
            data=json.dumps(update_data).encode('utf-8'),
            method='PATCH'
        )
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {FIREBASE_WEB_API_KEY}')

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"[Firestore] ✓ Clip {clip_index} added to Firestore successfully")
            return True

    except Exception as e:
        print(f"[Firestore] Error adding clip to Firestore: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
