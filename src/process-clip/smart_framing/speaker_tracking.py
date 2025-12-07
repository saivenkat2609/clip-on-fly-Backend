"""
Speaker-Face Correlation Module

This module correlates detected faces with transcript timestamps to identify
which face belongs to the active speaker at any given time.

Key Features:
- Maps face detections to speaking times
- Handles multiple faces in frame
- Tracks speaker positions over time
- Provides fallback for off-screen speakers
"""

import numpy as np
from typing import List, Dict, Optional, Tuple


def correlate_faces_with_speech(
    face_timeline: List[Dict],
    transcript_segments: List[Dict],
    clip_start: float = 0
) -> List[Dict]:
    """
    Map detected faces to speaking times from transcript.

    This function identifies which face is active (speaking) during each
    transcript segment by analyzing face positions during speaking times.

    Args:
        face_timeline: Output from FaceDetector.detect_faces_in_video()
            Format: [{frame_num, timestamp, faces: [{bbox, confidence}]}]
        transcript_segments: Clip segments with word-level timestamps
            Format: [{start, end, text, words: [{word, start, end}]}]
        clip_start: Clip start time to adjust timestamps (default: 0)

    Returns:
        List of speaker activity periods:
            [{
                start: float (seconds),
                end: float (seconds),
                face_center: (x, y) tuple,
                face_bbox: (x, y, w, h) tuple,
                text: str,
                confidence: float
            }]
    """
    print(f"[SpeakerTracking] Correlating {len(face_timeline)} frames with {len(transcript_segments)} segments")

    if not face_timeline or not transcript_segments:
        print("[SpeakerTracking] Warning: Empty face timeline or transcript")
        return []

    speaker_activity = []

    for seg_idx, segment in enumerate(transcript_segments):
        # Adjust segment times relative to clip start
        seg_start = segment['start'] - clip_start
        seg_end = segment['end'] - clip_start

        # Find faces visible during this segment
        segment_faces = find_faces_in_timerange(
            face_timeline,
            seg_start,
            seg_end
        )

        if not segment_faces:
            # No faces detected during this segment - skip or use fallback
            print(f"[SpeakerTracking] Warning: No faces in segment {seg_idx} ({seg_start:.2f}s - {seg_end:.2f}s)")
            continue

        # Calculate average face position and confidence during speech
        avg_face = calculate_average_face_position(segment_faces)

        speaker_activity.append({
            'start': seg_start,
            'end': seg_end,
            'face_center': avg_face['center'],
            'face_bbox': avg_face['bbox'],
            'text': segment.get('text', ''),
            'confidence': avg_face['confidence']
        })

    print(f"[SpeakerTracking] Identified {len(speaker_activity)} speaker activity periods")
    return speaker_activity


def find_faces_in_timerange(
    face_timeline: List[Dict],
    start_time: float,
    end_time: float
) -> List[Dict]:
    """
    Extract all face detections within a time range.

    Args:
        face_timeline: Face detection timeline
        start_time: Start time in seconds
        end_time: End time in seconds

    Returns:
        List of face detections in the time range
    """
    faces_in_range = []

    for frame_data in face_timeline:
        timestamp = frame_data['timestamp']

        # Check if frame is within time range
        if start_time <= timestamp <= end_time:
            if frame_data['faces']:
                # Add all faces from this frame
                for face in frame_data['faces']:
                    faces_in_range.append({
                        'timestamp': timestamp,
                        'bbox': face['bbox'],
                        'confidence': face['confidence']
                    })

    return faces_in_range


def group_faces_by_position(faces: List[Dict], distance_threshold: int = 100) -> List[List[Dict]]:
    """
    Group faces by spatial position to identify unique individuals.

    Faces within distance_threshold pixels are considered the same person.

    Args:
        faces: List of face detections
        distance_threshold: Max distance (pixels) to group faces together

    Returns:
        List of face groups (each group = same person across frames)
    """
    if not faces:
        return []

    groups = []

    for face in faces:
        bbox = face['bbox']
        center_x = bbox['x'] + bbox['w'] // 2
        center_y = bbox['y'] + bbox['h'] // 2

        # Find which group this face belongs to
        found_group = False
        for group in groups:
            # Get center of first face in group
            first_bbox = group[0]['bbox']
            group_center_x = first_bbox['x'] + first_bbox['w'] // 2
            group_center_y = first_bbox['y'] + first_bbox['h'] // 2

            # Check distance
            distance = np.sqrt(
                (center_x - group_center_x) ** 2 +
                (center_y - group_center_y) ** 2
            )

            if distance < distance_threshold:
                group.append(face)
                found_group = True
                break

        if not found_group:
            # Create new group
            groups.append([face])

    return groups


def select_primary_face(faces: List[Dict]) -> Dict:
    """
    Select the primary face from multiple detections.

    Selection criteria (in order):
    1. Largest face (closest to camera / most prominent)
    2. Highest confidence
    3. Most centered in frame

    Args:
        faces: List of face detections

    Returns:
        The primary face detection
    """
    if not faces:
        raise ValueError("Cannot select primary face from empty list")

    if len(faces) == 1:
        return faces[0]

    # Score each face
    scored_faces = []

    for face in faces:
        bbox = face['bbox']
        area = bbox['w'] * bbox['h']
        confidence = face['confidence']

        # Score = area (70%) + confidence (30%)
        # Larger faces (closer to camera) are likely the primary speaker
        score = (area * 0.7) + (confidence * 1000 * 0.3)

        scored_faces.append((score, face))

    # Return face with highest score
    scored_faces.sort(key=lambda x: x[0], reverse=True)
    return scored_faces[0][1]


def calculate_average_face_position(faces: List[Dict]) -> Dict:
    """
    Calculate representative face position from multiple detections.

    IMPORTANT: When multiple faces are present, this selects the PRIMARY
    face (largest, most confident, most centered) rather than averaging
    all faces, which would create an invalid position between faces.

    Args:
        faces: List of face detections from find_faces_in_timerange()

    Returns:
        Dictionary with face data:
            {
                center: (x, y) tuple,
                bbox: (x, y, w, h) tuple,
                confidence: float
            }
    """
    if not faces:
        raise ValueError("Cannot calculate average from empty face list")

    # Group faces by unique positions to identify distinct people
    unique_faces = group_faces_by_position(faces)

    if len(unique_faces) == 1:
        # Single person - safe to average for stability
        face_group = unique_faces[0]
        xs = [f['bbox']['x'] for f in face_group]
        ys = [f['bbox']['y'] for f in face_group]
        ws = [f['bbox']['w'] for f in face_group]
        hs = [f['bbox']['h'] for f in face_group]
        confidences = [f['confidence'] for f in face_group]

        avg_x = int(np.mean(xs))
        avg_y = int(np.mean(ys))
        avg_w = int(np.mean(ws))
        avg_h = int(np.mean(hs))
        avg_confidence = float(np.mean(confidences))

        center_x = avg_x + avg_w // 2
        center_y = avg_y + avg_h // 2

        return {
            'center': (center_x, center_y),
            'bbox': (avg_x, avg_y, avg_w, avg_h),
            'confidence': avg_confidence
        }
    else:
        # Multiple people - select PRIMARY speaker
        # Priority: largest face (closest to camera) with good confidence
        primary_face = select_primary_face(faces)

        bbox = primary_face['bbox']
        center_x = bbox['x'] + bbox['w'] // 2
        center_y = bbox['y'] + bbox['h'] // 2

        return {
            'center': (center_x, center_y),
            'bbox': (bbox['x'], bbox['y'], bbox['w'], bbox['h']),
            'confidence': primary_face['confidence']
        }


def identify_primary_speaker(
    faces_in_frame: List[Dict],
    previous_speaker_position: Optional[Tuple[int, int]] = None
) -> Optional[Dict]:
    """
    Identify the primary speaker when multiple faces are in frame.

    Uses confidence scores and proximity to previous speaker position
    to determine which face is likely speaking.

    Args:
        faces_in_frame: List of face detections in current frame
        previous_speaker_position: (x, y) position of previous speaker

    Returns:
        The face most likely to be the active speaker, or None
    """
    if not faces_in_frame:
        return None

    if len(faces_in_frame) == 1:
        return faces_in_frame[0]

    # Multiple faces - need to pick the most likely speaker
    scored_faces = []

    for face in faces_in_frame:
        score = face['confidence']  # Start with detection confidence

        # Bonus for proximity to previous speaker (temporal continuity)
        if previous_speaker_position:
            face_center_x = face['bbox']['x'] + face['bbox']['w'] // 2
            face_center_y = face['bbox']['y'] + face['bbox']['h'] // 2

            distance = np.sqrt(
                (face_center_x - previous_speaker_position[0]) ** 2 +
                (face_center_y - previous_speaker_position[1]) ** 2
            )

            # Add proximity bonus (closer = higher score)
            proximity_bonus = max(0, 1.0 - (distance / 500.0))  # Normalize to ~500px
            score += proximity_bonus * 0.3  # 30% weight for proximity

        scored_faces.append((score, face))

    # Return face with highest score
    scored_faces.sort(key=lambda x: x[0], reverse=True)
    return scored_faces[0][1]


def detect_multi_speaker_segments(
    speaker_activity: List[Dict],
    overlap_threshold: float = 1.0
) -> List[Dict]:
    """
    Identify segments where multiple speakers are active simultaneously.

    Useful for determining when to use side-by-side or wide crop strategies.

    Args:
        speaker_activity: Output from correlate_faces_with_speech()
        overlap_threshold: Minimum overlap in seconds to consider multi-speaker

    Returns:
        List of multi-speaker segments:
            [{start, end, speakers: [speaker1_data, speaker2_data]}]
    """
    multi_speaker_segments = []

    for i, current in enumerate(speaker_activity):
        for other in speaker_activity[i+1:]:
            # Check for temporal overlap
            overlap_start = max(current['start'], other['start'])
            overlap_end = min(current['end'], other['end'])
            overlap_duration = max(0, overlap_end - overlap_start)

            if overlap_duration >= overlap_threshold:
                # Check if speakers are in different positions (not same person)
                distance = calculate_face_distance(
                    current['face_center'],
                    other['face_center']
                )

                # If faces are far apart, it's likely different speakers
                if distance > 200:  # pixels
                    multi_speaker_segments.append({
                        'start': overlap_start,
                        'end': overlap_end,
                        'duration': overlap_duration,
                        'speakers': [current, other],
                        'face_distance': distance
                    })

    print(f"[SpeakerTracking] Detected {len(multi_speaker_segments)} multi-speaker segments")
    return multi_speaker_segments


def calculate_face_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
    """
    Calculate Euclidean distance between two face positions.

    Args:
        pos1: (x, y) position of first face
        pos2: (x, y) position of second face

    Returns:
        Distance in pixels
    """
    return np.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)


def handle_missing_faces(
    speaker_activity: List[Dict],
    video_width: int,
    video_height: int
) -> List[Dict]:
    """
    Fill gaps in speaker activity with fallback positions.

    When no faces are detected during a transcript segment, use:
    1. Last known face position
    2. Center of frame (fallback)

    Args:
        speaker_activity: Speaker activity timeline (may have gaps)
        video_width: Video width in pixels
        video_height: Video height in pixels

    Returns:
        Enhanced speaker activity with gaps filled
    """
    if not speaker_activity:
        # No faces detected at all - return center position
        center_x = video_width // 2
        center_y = video_height // 2
        return [{
            'start': 0,
            'end': 999,  # Placeholder duration
            'face_center': (center_x, center_y),
            'face_bbox': (center_x - 150, center_y - 200, 300, 400),
            'text': 'No faces detected',
            'confidence': 0.0
        }]

    # Fill gaps using last known position
    last_position = speaker_activity[0]['face_center']
    last_bbox = speaker_activity[0]['face_bbox']

    for activity in speaker_activity:
        if activity['confidence'] > 0.5:
            last_position = activity['face_center']
            last_bbox = activity['face_bbox']

    return speaker_activity
