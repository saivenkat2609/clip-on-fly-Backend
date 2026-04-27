import os
import json
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')


def update_video_status(session_id, status, error=None):
    """Update video status (and optionally error) in Supabase. Fire-and-forget — never raises."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/videos?session_id=eq.{urllib.parse.quote(session_id)}"
        payload = {'status': status}
        if error is not None:
            payload['error'] = error
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=body, method='PATCH', headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
            'apikey': SUPABASE_SERVICE_ROLE_KEY,
            'Prefer': 'return=minimal',
        })
        urllib.request.urlopen(req, timeout=5)
        print(f"[Supabase] status={status} for {session_id}")
    except Exception as e:
        print(f"[Supabase] update_video_status failed: {e}")
