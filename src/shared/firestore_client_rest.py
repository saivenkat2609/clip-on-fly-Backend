"""
Firestore Client using REST API (no firebase-admin dependency needed!)
Works with just standard library + requests (already available in Lambda)
"""
import os
import json
import base64
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import urllib.request
import urllib.parse
import urllib.error

FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframe-1e182')

# Cache for access token
_access_token_cache = None
_token_expiry = 0


def get_access_token():
    """
    Get OAuth2 access token from service account credentials
    Uses standard library only (no firebase-admin needed)
    """
    global _access_token_cache, _token_expiry

    # Return cached token if still valid
    if _access_token_cache and time.time() < _token_expiry:
        return _access_token_cache

    try:
        # Get service account credentials from environment
        base64_creds = os.environ.get('FIREBASE_ADMIN_SDK_BASE64')
        if not base64_creds:
            print("[Firestore REST] ERROR: FIREBASE_ADMIN_SDK_BASE64 not set")
            return None

        # Decode credentials
        creds_json = base64.b64decode(base64_creds).decode('utf-8')
        creds = json.loads(creds_json)

        # Create JWT for Google OAuth
        import jwt  # PyJWT - usually available in Lambda

        now = int(time.time())
        payload = {
            'iss': creds['client_email'],
            'sub': creds['client_email'],
            'aud': 'https://oauth2.googleapis.com/token',
            'iat': now,
            'exp': now + 3600,
            'scope': 'https://www.googleapis.com/auth/datastore'
        }

        # Sign JWT with private key
        signed_jwt = jwt.encode(payload, creds['private_key'], algorithm='RS256')

        # Exchange JWT for access token
        data = urllib.parse.urlencode({
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': signed_jwt
        }).encode()

        req = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())

        _access_token_cache = result['access_token']
        _token_expiry = now + result.get('expires_in', 3600) - 60  # 60s buffer

        print("[Firestore REST] ✓ Access token obtained")
        return _access_token_cache

    except Exception as e:
        print(f"[Firestore REST] ERROR getting access token: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def firestore_rest_request(method, path, data=None):
    """
    Make a REST API request to Firestore
    """
    token = get_access_token()
    if not token:
        return None

    url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents{path}"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode() if data else None,
            headers=headers,
            method=method
        )

        response = urllib.request.urlopen(req)
        return json.loads(response.read().decode())

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"[Firestore REST] HTTP Error: {e.code} - {error_body}")
        return None
    except Exception as e:
        print(f"[Firestore REST] Error: {str(e)}")
        return None


def update_firestore_video_rest(user_id: str, session_id: str, data: Dict) -> bool:
    """
    Update video document in Firestore using REST API
    No firebase-admin dependency needed!
    """
    if not user_id or not session_id:
        print("[Firestore REST] Missing user_id or session_id")
        return False

    try:
        # Build Firestore document path
        doc_path = f"/users/{user_id}/videos/{session_id}"

        # Convert data to Firestore format
        firestore_data = {
            'fields': {}
        }

        # Add status
        if 'status' in data:
            firestore_data['fields']['status'] = {'stringValue': data['status']}

        # Add completedAt timestamp
        firestore_data['fields']['completedAt'] = {
            'timestampValue': datetime.utcnow().isoformat() + 'Z'
        }

        # Add clips array
        if 'clips' in data and data['clips']:
            clips_array = []
            for clip in data['clips']:
                clip_obj = {
                    'mapValue': {
                        'fields': {
                            'clipIndex': {'integerValue': str(clip.get('clip_index', 0))},
                            'downloadUrl': {'stringValue': clip.get('download_url', '')},
                            's3Key': {'stringValue': clip.get('s3_key', '')}
                        }
                    }
                }

                # Add optional fields
                if 'title' in clip and clip['title']:
                    clip_obj['mapValue']['fields']['title'] = {'stringValue': clip['title']}
                if 'virality_score' in clip and clip['virality_score'] is not None:
                    clip_obj['mapValue']['fields']['virality_score'] = {'integerValue': str(clip['virality_score'])}
                if 'duration' in clip and clip['duration'] is not None:
                    clip_obj['mapValue']['fields']['duration'] = {'doubleValue': clip['duration']}

                clips_array.append(clip_obj)

            firestore_data['fields']['clips'] = {'arrayValue': {'values': clips_array}}

        # Make PATCH request to merge update
        query = '?updateMask.fieldPaths=status&updateMask.fieldPaths=completedAt&updateMask.fieldPaths=clips'
        result = firestore_rest_request('PATCH', doc_path + query, firestore_data)

        if result:
            print(f"[Firestore REST] ✓ Successfully updated video {session_id}")
            return True
        else:
            print(f"[Firestore REST] ✗ Failed to update video {session_id}")
            return False

    except Exception as e:
        print(f"[Firestore REST] Error updating document: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
