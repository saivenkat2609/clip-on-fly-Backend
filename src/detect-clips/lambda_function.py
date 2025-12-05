"""
Lambda Function 3: Detect Viral Clips with AI-Powered Virality Score
Analyzes transcript and identifies potential viral clip segments
Uses Groq AI to intelligently score clips (no static keywords)
"""
import json
import boto3
import os
import re
# Storage helper - works with S3, R2, B2, and any S3-compatible storage
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
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'opus-clip-videos')

# Clip detection settings
MIN_CLIP_DURATION = int(os.environ.get('MIN_CLIP_DURATION', '15'))
MAX_CLIP_DURATION = int(os.environ.get('MAX_CLIP_DURATION', '60'))
TARGET_CLIP_DURATION = int(os.environ.get('TARGET_CLIP_DURATION', '45'))
NUM_CLIPS = int(os.environ.get('NUM_CLIPS', '3'))

# AI Configuration for virality scoring
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
USE_AI_SCORING = os.environ.get('USE_AI_SCORING', 'true').lower() == 'true'



def lambda_handler(event, context):
    """
    Detect viral clips from transcript with AI-powered virality scoring

    Input event:
    {
        "session_id": "uuid",
        "s3_video_key": "...",
        "s3_transcript_key": "session_id/transcript.json",
        "video_info": {...}
    }

    Output:
    {
        "session_id": "uuid",
        "s3_video_key": "...",
        "clips": [
            {
                "clip_index": 0,
                "start": 10.5,
                "end": 40.2,
                "duration": 29.7,
                "text": "...",
                "segments": [...],
                "virality_score": 87,
                "score_breakdown": {
                    "hook": 85,
                    "flow": 90,
                    "engagement": 88,
                    "trend": 85
                }
            }
        ],
        "video_info": {...}
    }
    """
    try:
        session_id = event['session_id']
        s3_video_key = event['s3_video_key']
        transcript_key = event['s3_transcript_key']
        video_info = event.get('video_info', {})

        print(f"[Detect] Session: {session_id}")
        print(f"[Detect] Transcript: {transcript_key}")
        print(f"[Detect] AI Scoring: {'Enabled (Groq)' if USE_AI_SCORING and GROQ_API_KEY else 'Disabled (fallback)'}")

        # Download transcript from S3
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=transcript_key)
        transcript_data = json.loads(obj['Body'].read())
        segments = transcript_data['segments']

        print(f"[Detect] Analyzing {len(segments)} segments...")

        # Use AI to detect clips in ONE call (or fallback to basic detection)
        if USE_AI_SCORING and GROQ_API_KEY:
            try:
                final_clips = detect_clips_with_ai(segments, NUM_CLIPS)
            except Exception as e:
                print(f"[Detect] AI detection failed: {str(e)}, using fallback")
                final_clips = detect_clips_fallback(segments, NUM_CLIPS)
        else:
            print(f"[Detect] Using fallback detection (AI disabled or no API key)")
            final_clips = detect_clips_fallback(segments, NUM_CLIPS)

        # Add clip_index and generate titles
        for idx, clip in enumerate(final_clips):
            clip['clip_index'] = idx
            # Generate AI-powered title for the clip
            clip['title'] = generate_clip_title_ai(clip['text'], clip['virality_score'], clip['score_breakdown'])

        print(f"[Detect] Found {len(final_clips)} clips")
        for clip in final_clips:
            print(f"[Detect] Clip {clip['clip_index']}: \"{clip['title']}\" - Score {clip['virality_score']}/100 "
                  f"(Hook:{clip['score_breakdown']['hook']}, "
                  f"Flow:{clip['score_breakdown']['flow']}, "
                  f"Engagement:{clip['score_breakdown']['engagement']}, "
                  f"Trend:{clip['score_breakdown']['trend']})")

        return {
            'statusCode': 200,
            'session_id': session_id,
            's3_video_key': s3_video_key,
            'clips': final_clips,
            'video_info': video_info
        }

    except Exception as e:
        print(f"[Detect] Error: {str(e)}")
        raise Exception(f"Failed to detect clips: {str(e)}")


def detect_clips_with_ai(segments, num_clips):
    """
    Use Groq AI to detect viral clips in ONE API call
    Analyzes the full transcript and identifies the best clips with timestamps
    """
    print(f"[Detect] Using AI to detect clips (single API call)...")

    # Build full transcript with timestamps
    transcript_lines = []
    for seg in segments:
        transcript_lines.append(f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")

    full_transcript = '\n'.join(transcript_lines)

    # Prepare prompt for Groq
    prompt = f"""Analyze this video transcript and identify the {num_clips} BEST viral clip segments for social media (TikTok, Instagram Reels, YouTube Shorts).

TRANSCRIPT:
{full_transcript[:4000]}

REQUIREMENTS:
- Each clip must be {MIN_CLIP_DURATION}-{MAX_CLIP_DURATION} seconds long
- Target duration: ~{TARGET_CLIP_DURATION} seconds
- Clips should NOT overlap
- Identify clips with strong hooks, good pacing, high engagement potential

For each clip, provide:
1. start_time (seconds, from transcript timestamps)
2. end_time (seconds, from transcript timestamps)
3. virality_score (0-100 overall score)
4. hook_score (0-100: opening strength)
5. flow_score (0-100: pacing/rhythm)
6. engagement_score (0-100: viewer retention)
7. trend_score (0-100: viral potential)

Respond ONLY with valid JSON array (no markdown, no extra text):
[
  {{"start_time": 10.5, "end_time": 45.2, "virality_score": 87, "hook_score": 90, "flow_score": 85, "engagement_score": 88, "trend_score": 85}},
  {{"start_time": 120.0, "end_time": 165.5, "virality_score": 82, "hook_score": 85, "flow_score": 80, "engagement_score": 83, "trend_score": 80}}
]"""

    import urllib.request
    import urllib.error

    url = "https://api.groq.com/openai/v1/chat/completions"

    request_data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert at analyzing viral social media content. Respond ONLY with JSON arrays, no other text."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1000
    }

    # Convert to JSON bytes
    json_data = json.dumps(request_data).encode('utf-8')

    # Create request with headers
    req = urllib.request.Request(
        url,
        data=json_data,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    # Make API call
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_data = response.read().decode('utf-8')
            result = json.loads(response_data)
            ai_response = result['choices'][0]['message']['content'].strip()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        raise Exception(f"Groq API error ({e.code}): {error_body}")
    except urllib.error.URLError as e:
        raise Exception(f"Groq API connection error: {str(e)}")

    print(f"[Detect] AI Response: {ai_response[:200]}...")

    # Parse JSON response
    ai_response = ai_response.replace('```json', '').replace('```', '').strip()
    ai_clips = json.loads(ai_response)

    # Convert AI response to our clip format
    final_clips = []
    for ai_clip in ai_clips[:num_clips]:
        start_time = float(ai_clip.get('start_time') or ai_clip.get('start'))
        end_time = float(ai_clip.get('end_time') or ai_clip.get('end'))

        # Find matching segments
        clip_segments = []
        clip_text_parts = []
        for seg in segments:
            # Include segment if it overlaps with the clip timerange
            if seg['start'] < end_time and seg['end'] > start_time:
                clip_segments.append(seg)
                clip_text_parts.append(seg['text'])

        if not clip_segments:
            continue

        # Use actual segment boundaries
        actual_start = clip_segments[0]['start']
        actual_end = clip_segments[-1]['end']
        duration = actual_end - actual_start

        # Validate duration
        if duration < MIN_CLIP_DURATION or duration > MAX_CLIP_DURATION:
            continue

        clip_text = ' '.join(clip_text_parts)

        # Extract scores
        virality_score = min(max(int(ai_clip.get('virality_score', 75)), 0), 100)
        hook_score = min(max(int(ai_clip.get('hook_score', 75)), 0), 100)
        flow_score = min(max(int(ai_clip.get('flow_score', 75)), 0), 100)
        engagement_score = min(max(int(ai_clip.get('engagement_score', 75)), 0), 100)
        trend_score = min(max(int(ai_clip.get('trend_score', 75)), 0), 100)

        final_clips.append({
            'start': actual_start,
            'end': actual_end,
            'duration': duration,
            'text': clip_text,
            'segments': clip_segments,
            'virality_score': virality_score,
            'score_breakdown': {
                'hook': hook_score,
                'flow': flow_score,
                'engagement': engagement_score,
                'trend': trend_score
            },
            'score': virality_score  # For backward compatibility
        })

    print(f"[Detect] AI identified {len(final_clips)} clips")
    return final_clips


def detect_clips_fallback(segments, num_clips):
    """
    Fallback clip detection using basic heuristics (no AI)
    Generates candidates and scores them with simple rules
    """
    print(f"[Detect] Using fallback detection (no AI)...")

    candidates = []
    for i in range(len(segments)):
        for j in range(i + 1, len(segments) + 1):
            clip_start = segments[i]['start']
            clip_end = segments[j - 1]['end']
            duration = clip_end - clip_start

            # Check duration constraints
            if duration < MIN_CLIP_DURATION:
                continue
            if duration > MAX_CLIP_DURATION:
                break

            # Extract text for this clip
            clip_text = ' '.join([seg['text'] for seg in segments[i:j]])

            # Calculate basic score
            score_data = score_with_fallback(clip_text, duration, segments[i:j])

            candidates.append({
                'start': clip_start,
                'end': clip_end,
                'duration': duration,
                'text': clip_text,
                'segments': segments[i:j],
                'virality_score': score_data['total'],
                'score_breakdown': score_data['breakdown'],
                'score': score_data['total']
            })

    # Sort by virality score
    candidates.sort(key=lambda x: x['virality_score'], reverse=True)

    # Filter overlapping clips
    final_clips = filter_overlapping_clips(candidates, num_clips)

    return final_clips


def score_with_fallback(text, duration, segments):
    """
    Fallback scoring when AI is unavailable
    Uses basic heuristics
    """
    text_lower = text.lower()
    words = text.split()
    word_count = len(words)

    # Hook score (0-100)
    hook_score = 50
    first_segment = segments[0] if segments else {'text': text[:100]}
    first_text = first_segment.get('text', '').lower()

    # Check for hook patterns
    if any(word in first_text for word in ['secret', 'shocking', 'revealed', 'never', 'why', 'how']):
        hook_score += 20
    if '?' in first_text:
        hook_score += 15
    if re.search(r'\b\d+\b', first_text):
        hook_score += 10
    hook_score = min(hook_score, 100)

    # Flow score (0-100)
    flow_score = 50
    if 30 <= duration <= 50:
        flow_score += 20
    elif 20 <= duration <= 60:
        flow_score += 10

    words_per_second = word_count / duration if duration > 0 else 0
    if 2.5 <= words_per_second <= 3.5:
        flow_score += 15

    if text.strip().endswith(('.', '!', '?')):
        flow_score += 10
    flow_score = min(flow_score, 100)

    # Engagement score (0-100)
    engagement_score = 50
    engagement_score += text.count('?') * 12
    if any(word in text_lower for word in ['you', 'your', 'imagine', 'think']):
        engagement_score += 15
    engagement_score += text.count('!') * 5
    engagement_score = min(engagement_score, 100)

    # Trend score (0-100)
    trend_score = 50
    if any(word in text_lower for word in ['tip', 'trick', 'hack', 'secret']):
        trend_score += 20
    if 'how to' in text_lower:
        trend_score += 15
    if re.search(r'\b\d+\b', text):
        trend_score += 10
    trend_score = min(trend_score, 100)

    # Calculate total
    total = round(hook_score * 0.30 + flow_score * 0.25 + engagement_score * 0.25 + trend_score * 0.20)

    return {
        'total': total,
        'breakdown': {
            'hook': hook_score,
            'flow': flow_score,
            'engagement': engagement_score,
            'trend': trend_score
        }
    }


def filter_overlapping_clips(candidates, num_clips):
    """Filter out overlapping clips"""
    selected = []

    for candidate in candidates:
        overlaps = False
        for selected_clip in selected:
            if clips_overlap(candidate, selected_clip):
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

        if len(selected) >= num_clips:
            break

    return selected


def clips_overlap(clip1, clip2, threshold=0.3):
    """Check if two clips overlap significantly"""
    start1, end1 = clip1['start'], clip1['end']
    start2, end2 = clip2['start'], clip2['end']

    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap_duration = max(0, overlap_end - overlap_start)

    clip1_duration = end1 - start1
    clip2_duration = end2 - start2

    overlap_ratio1 = overlap_duration / clip1_duration if clip1_duration > 0 else 0
    overlap_ratio2 = overlap_duration / clip2_duration if clip2_duration > 0 else 0

    return max(overlap_ratio1, overlap_ratio2) > threshold


def generate_clip_title_ai(text, virality_score, score_breakdown):
    """
    Generate an AI-powered catchy title for the clip

    Args:
        text: The clip transcript text
        virality_score: Overall virality score
        score_breakdown: Individual scores (hook, flow, engagement, trend)

    Returns:
        str: A catchy, engaging title for the clip
    """
    if not (USE_AI_SCORING and GROQ_API_KEY):
        # Fallback: Generate simple title from text
        return generate_fallback_title(text)

    try:
        import urllib.request
        import urllib.error

        print(f"[Detect] Generating title with Groq AI...")

        # Prepare prompt for title generation
        prompt = f"""Generate a catchy, attention-grabbing title for this social media clip.

Clip Text: "{text[:300]}"
Virality Score: {virality_score}/100
Hook Strength: {score_breakdown['hook']}/100
Engagement: {score_breakdown['engagement']}/100

Requirements:
- 40-70 characters (optimal for social media)
- Start with powerful words or numbers
- Use emotional triggers or curiosity gaps
- Include keywords from the clip content
- Make it click-worthy but NOT clickbait
- Use title case (capitalize first letter of each major word)

Good examples:
- "The Secret Nobody Tells You About Success"
- "How I Fixed This Problem in 30 Seconds"
- "Why Everyone is Wrong About This Topic"
- "3 Simple Tricks That Changed Everything"
- "The Truth About [Main Topic] Revealed"

Respond with ONLY the title text, no quotes, no extra text:"""

        url = "https://api.groq.com/openai/v1/chat/completions"

        request_data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at creating viral social media titles. Respond with ONLY the title, no extra text or formatting."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,  # Higher temperature for creative titles
            "max_tokens": 50
        }

        # Convert to JSON bytes
        json_data = json.dumps(request_data).encode('utf-8')

        # Create request with headers
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
        )

        # Make API call
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                response_data = response.read().decode('utf-8')
                result = json.loads(response_data)
                ai_title = result['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"[Detect] Title generation API error: {str(e)}")
            return generate_fallback_title(text)

        # Clean up the title
        ai_title = ai_title.replace('"', '').replace("'", "").strip()

        # Limit length
        if len(ai_title) > 80:
            ai_title = ai_title[:77] + "..."

        print(f"[Detect] Generated title: \"{ai_title}\"")
        return ai_title

    except Exception as e:
        print(f"[Detect] Title generation failed: {str(e)}, using fallback")
        return generate_fallback_title(text)


def generate_fallback_title(text):
    """
    Generate a simple title from the clip text when AI is unavailable
    """
    # Take first meaningful sentence
    sentences = re.split(r'[.!?]+', text)

    for sentence in sentences:
        sentence = sentence.strip()
        # Find a sentence with at least 3 words
        if len(sentence.split()) >= 3:
            # Limit to 60 characters
            if len(sentence) > 60:
                sentence = sentence[:57] + "..."
            # Title case
            return sentence.title()

    # Fallback: Use first 60 characters
    title = text[:57].strip() + "..." if len(text) > 60 else text.strip()
    return title.title()
