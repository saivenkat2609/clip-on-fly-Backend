"""
Lambda Function 5: Finalize Processing
Aggregates results and generates pre-signed URLs
"""
import json
import boto3
from botocore.config import Config
import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

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
FIREBASE_WEB_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY', '')

def update_firestore_video(user_id, session_id, data):
    """
    Update video status in Firestore using REST API
    """
    if not user_id or not FIREBASE_WEB_API_KEY:
        print("[Firestore] Skipping update - missing user_id or API key")
        return

    try:
        # Firestore REST API endpoint
        url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/users/{user_id}/videos/{session_id}"

        # Transform data to Firestore format
        firestore_data = {
            "fields": {
                "status": {"stringValue": data.get("status", "completed")},
                "completedAt": {"timestampValue": datetime.utcnow().isoformat() + "Z"}
            }
        }

        # Add clips data
        if "clips" in data and data["clips"]:
            clips_array = []
            for clip in data["clips"]:
                clip_fields = {
                    "clipIndex": {"integerValue": str(clip["clip_index"])},
                    "downloadUrl": {"stringValue": clip["download_url"]},
                    "s3Key": {"stringValue": clip["s3_key"]}
                }

                # Add optional fields if present
                if "title" in clip and clip["title"]:
                    clip_fields["title"] = {"stringValue": clip["title"]}
                if "virality_score" in clip and clip["virality_score"] is not None:
                    clip_fields["virality_score"] = {"integerValue": str(clip["virality_score"])}
                if "duration" in clip and clip["duration"] is not None:
                    clip_fields["duration"] = {"doubleValue": clip["duration"]}
                if "startTime" in clip and clip["startTime"] is not None:
                    clip_fields["startTime"] = {"doubleValue": clip["startTime"]}
                if "endTime" in clip and clip["endTime"] is not None:
                    clip_fields["endTime"] = {"doubleValue": clip["endTime"]}

                # Add score breakdown if present
                if "score_breakdown" in clip and clip["score_breakdown"]:
                    breakdown = clip["score_breakdown"]
                    clip_fields["score_breakdown"] = {
                        "mapValue": {
                            "fields": {
                                "hook": {"integerValue": str(breakdown.get("hook", 0))},
                                "flow": {"integerValue": str(breakdown.get("flow", 0))},
                                "engagement": {"integerValue": str(breakdown.get("engagement", 0))},
                                "trend": {"integerValue": str(breakdown.get("trend", 0))}
                            }
                        }
                    }

                clips_array.append({
                    "mapValue": {
                        "fields": clip_fields
                    }
                })
            firestore_data["fields"]["clips"] = {"arrayValue": {"values": clips_array}}

        # Add video info if present
        if "video_info" in data and data["video_info"]:
            video_info = data["video_info"]
            firestore_data["fields"]["videoInfo"] = {
                "mapValue": {
                    "fields": {
                        "title": {"stringValue": video_info.get("title", "")},
                        "duration": {"integerValue": str(video_info.get("duration", 0))},
                        "thumbnail": {"stringValue": video_info.get("thumbnail", "")}
                    }
                }
            }

        # Add error if present
        if "error" in data:
            firestore_data["fields"]["error"] = {"stringValue": data["error"]}
            firestore_data["fields"]["status"] = {"stringValue": "failed"}

        # Update document (merge with existing fields)
        # Build query string with multiple updateMask.fieldPaths
        query_params = [
            f"key={FIREBASE_WEB_API_KEY}",
            "updateMask.fieldPaths=status",
            "updateMask.fieldPaths=completedAt",
            "updateMask.fieldPaths=clips",
            "updateMask.fieldPaths=videoInfo",
            "updateMask.fieldPaths=error"
        ]
        params = "&".join(query_params)

        full_url = f"{url}?{params}"
        headers = {"Content-Type": "application/json"}
        data = json.dumps(firestore_data).encode('utf-8')

        req = urllib.request.Request(full_url, data=data, headers=headers, method='PATCH')

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                print(f"[Firestore] Successfully updated video {session_id}")
        except urllib.error.HTTPError as e:
            print(f"[Firestore] Update failed: {e.code} - {e.read().decode()}")

    except Exception as e:
        print(f"[Firestore] Error updating document: {str(e)}")

def update_user_stats(user_id, total_clips):
    """
    Increment user's totalClips count in Firestore
    """
    if not user_id or not FIREBASE_WEB_API_KEY:
        print("[Firestore] Skipping stats update - missing user_id or API key")
        return

    try:
        url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/users/{user_id}"

        # Get current totalClips value
        get_url = f"{url}?key={FIREBASE_WEB_API_KEY}"

        try:
            with urllib.request.urlopen(get_url, timeout=10) as response:
                doc = json.loads(response.read().decode())
                current_clips = int(doc.get("fields", {}).get("totalClips", {}).get("integerValue", 0))
                new_total = current_clips + total_clips

                # Update with new value
                update_data = {
                    "fields": {
                        "totalClips": {"integerValue": str(new_total)}
                    }
                }

                params = urllib.parse.urlencode({
                    "key": FIREBASE_WEB_API_KEY,
                    "updateMask.fieldPaths": "totalClips"
                })
                update_url = f"{url}?{params}"
                data = json.dumps(update_data).encode('utf-8')
                headers = {"Content-Type": "application/json"}

                req = urllib.request.Request(update_url, data=data, headers=headers, method='PATCH')

                try:
                    with urllib.request.urlopen(req, timeout=10) as update_response:
                        print(f"[Firestore] Updated user stats: totalClips = {new_total}")
                except urllib.error.HTTPError as e:
                    print(f"[Firestore] Stats update failed: {e.code}")

        except urllib.error.HTTPError as e:
            print(f"[Firestore] Failed to fetch user doc: {e.code}")

    except Exception as e:
        print(f"[Firestore] Error updating user stats: {str(e)}")

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

        return {
            'statusCode': 200,
            **result
        }

    except Exception as e:
        print(f"[Finalize] Error: {str(e)}")
        raise Exception(f"Failed to finalize: {str(e)}")
