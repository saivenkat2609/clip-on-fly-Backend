"""
Smart Crop Calculator Module V2 - Sticky Speaker Tracking

This module implements a "sticky speaker" approach that locks onto one speaker
and only switches when another speaker shows significantly more movement.

Key Features:
- Locks onto one speaker when multiple faces detected
- Only switches speakers based on movement comparison (not random switching)
- Prevents jarring rapid switches between speakers
- Applies minimal smoothing for natural movement tracking
- Movement threshold: 100px to trigger switch consideration
"""

import numpy as np
from scipy.ndimage import gaussian_filter1d
from typing import List, Dict, Tuple, Optional


# Common aspect ratios and their dimensions
ASPECT_RATIOS = {
    '9:16': (1080, 1920),   # Vertical (TikTok, Reels, Shorts)
    '16:9': (1920, 1080),   # Horizontal (YouTube)
    '1:1': (1080, 1080),    # Square (Instagram)
    '4:5': (1080, 1350),    # Instagram portrait
}


def calculate_smart_crop(
    speaker_activity: List[Dict],
    video_width: int,
    video_height: int,
    target_aspect: str = '9:16',
    padding_ratio: float = 0.15,
    smoothing_sigma: float = 0.5,
    face_timeline: List[Dict] = None,
    enable_motion_keyframes: bool = True,
    motion_threshold: int = 100,
    max_keyframe_interval: float = 3.0
) -> Tuple[List[Dict], Tuple[int, int]]:
    """
    Calculate dynamic crop coordinates to follow active speaker.

    This is the main function that generates a timeline of crop positions
    based on speaker activity. The crop follows the speaker while maintaining
    the target aspect ratio.

    Args:
        speaker_activity: Output from correlate_faces_with_speech()
        video_width: Source video width in pixels
        video_height: Source video height in pixels
        target_aspect: Target aspect ratio ('9:16', '16:9', '1:1', '4:5')
        padding_ratio: Extra padding around face (0.15 = 15%)
        smoothing_sigma: Gaussian smoothing strength (higher = smoother)
        face_timeline: Face detection timeline (for motion tracking)
        enable_motion_keyframes: Enable motion-based keyframe generation
        motion_threshold: Minimum face movement (pixels) to create keyframe
        max_keyframe_interval: Maximum time (seconds) between keyframes

    Returns:
        Tuple of:
            - Crop timeline: [{timestamp, crop_x, crop_y, crop_w, crop_h}]
            - Crop dimensions: (crop_width, crop_height)
    """
    print(f"[SmartCrop] Calculating smart crop for {len(speaker_activity)} segments")
    print(f"[SmartCrop] Video: {video_width}x{video_height}, Target: {target_aspect}")
    if enable_motion_keyframes:
        print(f"[SmartCrop] Motion tracking enabled: threshold={motion_threshold}px, interval={max_keyframe_interval}s")

    if not speaker_activity:
        # No speaker activity - use center crop
        print("[SmartCrop] No speaker activity, using center crop")
        return calculate_center_crop(video_width, video_height, target_aspect)

    # Get target dimensions
    target_w, target_h = ASPECT_RATIOS.get(target_aspect, ASPECT_RATIOS['9:16'])
    target_ratio = target_w / target_h

    # Calculate crop dimensions that fit within video
    crop_w, crop_h = calculate_crop_dimensions(
        video_width,
        video_height,
        target_ratio
    )

    print(f"[SmartCrop] Crop dimensions: {crop_w}x{crop_h}")

    # Generate crop coordinates for each speaker segment
    crop_timeline = []

    for activity in speaker_activity:
        face_center_x, face_center_y = activity['face_center']
        face_x, face_y, face_w, face_h = activity['face_bbox']

        # Calculate crop position to center on face
        crop_x, crop_y = calculate_crop_position(
            face_center_x,
            face_center_y,
            face_w,
            face_h,
            crop_w,
            crop_h,
            video_width,
            video_height,
            padding_ratio
        )

        crop_timeline.append({
            'timestamp': activity['start'],
            'crop_x': crop_x,
            'crop_y': crop_y,
            'crop_w': crop_w,
            'crop_h': crop_h,
            'speaker_text': activity.get('text', '')[:50],  # First 50 chars
            'source': 'transcript',  # Mark source
            'face_center': activity['face_center'],  # Store for debugging
            'face_bbox': activity['face_bbox']  # Store for debugging
        })

    initial_count = len(crop_timeline)

    # Add motion-based keyframes if enabled
    if enable_motion_keyframes and face_timeline:
        motion_keyframes = generate_motion_keyframes(
            speaker_activity,
            face_timeline,
            crop_w,
            crop_h,
            video_width,
            video_height,
            padding_ratio,
            motion_threshold,
            max_keyframe_interval
        )
        crop_timeline.extend(motion_keyframes)

        # Sort by timestamp
        crop_timeline.sort(key=lambda x: x['timestamp'])

        print(f"[SmartCrop] Added {len(motion_keyframes)} motion-based keyframes ({initial_count} → {len(crop_timeline)})")

    # Apply smoothing to reduce jarring transitions
    if len(crop_timeline) > 2:
        crop_timeline = smooth_crop_transitions(crop_timeline, smoothing_sigma)
        print(f"[SmartCrop] Applied smoothing with sigma={smoothing_sigma}")

    print(f"[SmartCrop] Generated {len(crop_timeline)} total crop keyframes")
    return crop_timeline, (crop_w, crop_h)


def calculate_crop_dimensions(
    video_width: int,
    video_height: int,
    target_ratio: float
) -> Tuple[int, int]:
    """
    Calculate crop dimensions that fit within video while maintaining aspect ratio.

    Args:
        video_width: Source video width
        video_height: Source video height
        target_ratio: Target aspect ratio (width/height)

    Returns:
        (crop_width, crop_height) tuple
    """
    # Start with full height and calculate width
    crop_h = video_height
    crop_w = int(crop_h * target_ratio)

    # If crop width exceeds video width, constrain by width instead
    if crop_w > video_width:
        crop_w = video_width
        crop_h = int(crop_w / target_ratio)

    return crop_w, crop_h


def calculate_crop_position(
    face_center_x: int,
    face_center_y: int,
    face_w: int,
    face_h: int,
    crop_w: int,
    crop_h: int,
    video_width: int,
    video_height: int,
    padding_ratio: float
) -> Tuple[int, int]:
    """
    Calculate crop position to center on face with padding.

    Args:
        face_center_x, face_center_y: Face center coordinates
        face_w, face_h: Face dimensions
        crop_w, crop_h: Crop dimensions
        video_width, video_height: Video dimensions
        padding_ratio: Extra padding around face

    Returns:
        (crop_x, crop_y) top-left corner of crop region
    """
    # Calculate crop position to center face
    crop_x = int(face_center_x - crop_w / 2)
    crop_y = int(face_center_y - crop_h / 2)

    # Apply vertical bias - prefer face in upper third for vertical videos
    # This leaves room for subtitles at bottom
    if crop_h > crop_w:  # Vertical video
        # Move face up slightly (toward upper third)
        crop_y = int(face_center_y - crop_h * 0.35)  # 35% from top instead of 50%

    # Constrain crop to video bounds
    crop_x = max(0, min(crop_x, video_width - crop_w))
    crop_y = max(0, min(crop_y, video_height - crop_h))

    return crop_x, crop_y


def smooth_crop_transitions(
    crop_timeline: List[Dict],
    sigma: float = 0.5
) -> List[Dict]:
    """
    Apply smoothing within speaker segments with hard cuts at boundaries.

    SPEECH-FIRST APPROACH:
    - Transcript keyframes (speaker changes) are NEVER smoothed
    - Creates hard cuts at speaker boundaries (no interpolation between speakers)
    - Applies light smoothing only within same-speaker segments (motion keyframes)
    - This prevents the "box between speakers" averaging problem

    Args:
        crop_timeline: List of crop keyframes
        sigma: Smoothing strength for within-segment motion (default 0.5 = light)

    Returns:
        Crop timeline with smoothed motion but hard speaker transitions
    """
    if len(crop_timeline) < 3:
        return crop_timeline

    # Extract position arrays
    crop_x = np.array([c['crop_x'] for c in crop_timeline])
    crop_y = np.array([c['crop_y'] for c in crop_timeline])

    # Identify speaker segment boundaries (transcript keyframes)
    # Each transcript keyframe marks a speaker change or segment start
    transcript_indices = [i for i, c in enumerate(crop_timeline) if c['source'] == 'transcript']

    if not transcript_indices:
        # No transcript keyframes - just smooth everything
        print("[SmartCrop] No transcript boundaries, applying global smoothing")
        smooth_x = gaussian_filter1d(crop_x, sigma=sigma, mode='nearest')
        smooth_y = gaussian_filter1d(crop_y, sigma=sigma, mode='nearest')
    else:
        # Create segments: each segment runs from one transcript keyframe to the next
        # Segments contain: [transcript_kf, motion_kf1, motion_kf2, ..., next_transcript_kf]
        segments = []
        for i in range(len(transcript_indices)):
            start = transcript_indices[i]
            end = transcript_indices[i+1] if i+1 < len(transcript_indices) else len(crop_timeline)
            segment_indices = list(range(start, end))
            segments.append(segment_indices)

        print(f"[SmartCrop] Speech-First Smoothing: {len(segments)} speaker segments (hard cuts at boundaries)")

        # Apply smoothing ONLY within each segment, preserving transcript keyframes
        smooth_x = crop_x.copy()
        smooth_y = crop_y.copy()

        for seg_idx, segment in enumerate(segments):
            if len(segment) >= 3:  # Need at least 3 points to smooth
                seg_x = crop_x[segment]
                seg_y = crop_y[segment]

                # Smooth within this segment
                seg_smooth_x = gaussian_filter1d(seg_x, sigma=sigma, mode='nearest')
                seg_smooth_y = gaussian_filter1d(seg_y, sigma=sigma, mode='nearest')

                # Update arrays, BUT preserve the first point (transcript keyframe) exactly
                # This ensures hard cuts at speaker boundaries
                for i, idx in enumerate(segment):
                    if i == 0:
                        # Keep transcript keyframe position EXACT (no smoothing)
                        continue
                    else:
                        # Smooth motion keyframes within segment
                        smooth_x[idx] = seg_smooth_x[i]
                        smooth_y[idx] = seg_smooth_y[i]

                if seg_idx < 3:  # Debug first few segments
                    motion_count = len(segment) - 1
                    print(f"   Segment {seg_idx}: {motion_count} motion keyframes smoothed, "
                          f"transcript KF at t={crop_timeline[segment[0]]['timestamp']:.2f}s preserved")

    # Build smoothed timeline
    smoothed_timeline = []
    for i, crop in enumerate(crop_timeline):
        smoothed_timeline.append({
            'timestamp': crop['timestamp'],
            'crop_x': int(smooth_x[i]),
            'crop_y': int(smooth_y[i]),
            'crop_w': crop['crop_w'],
            'crop_h': crop['crop_h'],
            'speaker_text': crop.get('speaker_text', ''),
            'source': crop.get('source', 'transcript'),
            'face_center': crop.get('face_center'),
            'face_bbox': crop.get('face_bbox')
        })

    return smoothed_timeline


def match_face_to_speaker(face: Dict, speakers: Dict, proximity_threshold: float = 150.0) -> Optional[int]:
    """
    Match a detected face to an existing tracked speaker based on proximity.

    Args:
        face: Face detection with 'bbox'
        speakers: Dict of {speaker_id: {'center': (x,y), 'baseline': (x,y), ...}}
        proximity_threshold: Max distance to consider same speaker

    Returns:
        speaker_id if matched, None otherwise
    """
    face_center = (
        face['bbox']['x'] + face['bbox']['w'] // 2,
        face['bbox']['y'] + face['bbox']['h'] // 2
    )

    best_match = None
    min_distance = proximity_threshold

    for speaker_id, speaker_data in speakers.items():
        speaker_center = speaker_data['center']
        distance = np.sqrt(
            (face_center[0] - speaker_center[0]) ** 2 +
            (face_center[1] - speaker_center[1]) ** 2
        )

        if distance < min_distance:
            min_distance = distance
            best_match = speaker_id

    return best_match


def generate_motion_keyframes(
    speaker_activity: List[Dict],
    face_timeline: List[Dict],
    crop_w: int,
    crop_h: int,
    video_width: int,
    video_height: int,
    padding_ratio: float,
    motion_threshold: int,
    max_keyframe_interval: float
) -> List[Dict]:
    """
    Generate keyframes using STICKY SPEAKER TRACKING approach.

    KEY BEHAVIOR:
    1. Locks onto one speaker when multiple faces present
    2. Only switches speakers if another speaker:
       - Moves >100px from their baseline position
       - AND is moving MORE than the current tracked speaker
    3. If nobody moves, stays locked to current speaker

    Args:
        speaker_activity: Speaker activity periods
        face_timeline: Face detection timeline from FaceDetector
        crop_w, crop_h: Crop dimensions
        video_width, video_height: Video dimensions
        padding_ratio: Padding around face
        motion_threshold: Movement threshold for switch consideration (100px)
        max_keyframe_interval: Maximum time between keyframes (seconds)

    Returns:
        List of motion-based keyframes
    """
    motion_keyframes = []

    # Get all faces at each timestamp (not just primary)
    faces_by_time = {}
    for detection in face_timeline:
        if detection['faces']:
            faces_by_time[detection['timestamp']] = detection['faces']

    if not faces_by_time:
        print("[StickyTracking] No faces found in face timeline")
        return []

    print(f"[StickyTracking] Analyzing {len(speaker_activity)} segments with sticky speaker approach")

    for seg_idx, activity in enumerate(speaker_activity):
        seg_start = activity['start']
        seg_end = activity['end']
        seg_duration = seg_end - seg_start

        # Skip very short segments
        if seg_duration < 1.0:
            continue

        # Find all face detections within this segment
        segment_detections = []
        for timestamp in sorted(faces_by_time.keys()):
            if seg_start <= timestamp <= seg_end:
                segment_detections.append((timestamp, faces_by_time[timestamp]))

        if len(segment_detections) < 2:
            continue

        # Initialize speaker tracking for this segment
        tracked_speakers = {}  # {speaker_id: {'center': (x,y), 'baseline': (x,y), 'total_movement': float, 'face': dict}}
        next_speaker_id = 0
        locked_speaker_id = None  # Currently tracked speaker
        last_keyframe_time = seg_start

        print(f"[StickyTracking] Segment {seg_idx}: {seg_duration:.1f}s, starting sticky tracking")

        for timestamp, faces in segment_detections:
            # Update tracked speakers with current detections
            current_frame_speakers = {}

            for face in faces:
                face_center = (
                    face['bbox']['x'] + face['bbox']['w'] // 2,
                    face['bbox']['y'] + face['bbox']['h'] // 2
                )

                # Try to match to existing speaker
                matched_id = match_face_to_speaker(face, tracked_speakers)

                if matched_id is not None:
                    # Update existing speaker
                    speaker_id = matched_id
                    old_center = tracked_speakers[speaker_id]['center']
                    movement = np.sqrt(
                        (face_center[0] - old_center[0]) ** 2 +
                        (face_center[1] - old_center[1]) ** 2
                    )
                    tracked_speakers[speaker_id]['total_movement'] += movement
                    tracked_speakers[speaker_id]['center'] = face_center
                    tracked_speakers[speaker_id]['face'] = face
                else:
                    # New speaker detected
                    speaker_id = next_speaker_id
                    next_speaker_id += 1
                    tracked_speakers[speaker_id] = {
                        'center': face_center,
                        'baseline': face_center,
                        'total_movement': 0.0,
                        'face': face
                    }

                current_frame_speakers[speaker_id] = tracked_speakers[speaker_id]

            # Lock onto a speaker if not locked yet
            if locked_speaker_id is None and current_frame_speakers:
                # Use primary face logic to select initial speaker
                from .speaker_tracking import select_primary_face
                primary = select_primary_face([s['face'] for s in current_frame_speakers.values()])

                # Find which speaker this is
                for sid, sdata in current_frame_speakers.items():
                    if sdata['face'] == primary:
                        locked_speaker_id = sid
                        print(f"   Locked onto speaker {locked_speaker_id} at t={timestamp:.2f}s")
                        break

            # Check if we should switch speakers
            if locked_speaker_id is not None and len(current_frame_speakers) > 1:
                locked_speaker = current_frame_speakers.get(locked_speaker_id)

                if locked_speaker is None:
                    # Locked speaker disappeared, pick a new one
                    locked_speaker_id = list(current_frame_speakers.keys())[0]
                    print(f"   Speaker disappeared, switching to speaker {locked_speaker_id} at t={timestamp:.2f}s")
                else:
                    # Check if another speaker should take precedence
                    for speaker_id, speaker_data in current_frame_speakers.items():
                        if speaker_id == locked_speaker_id:
                            continue

                        # Calculate movement from baseline
                        baseline = speaker_data['baseline']
                        current_pos = speaker_data['center']
                        movement_from_baseline = np.sqrt(
                            (current_pos[0] - baseline[0]) ** 2 +
                            (current_pos[1] - baseline[1]) ** 2
                        )

                        # Switch conditions:
                        # 1. Other speaker moved >motion_threshold from baseline
                        # 2. Other speaker's total movement > locked speaker's total movement
                        if (movement_from_baseline > motion_threshold and
                            speaker_data['total_movement'] > locked_speaker['total_movement']):
                            print(f"   Switching from speaker {locked_speaker_id} to {speaker_id} at t={timestamp:.2f}s "
                                  f"(movement: {movement_from_baseline:.0f}px vs threshold {motion_threshold}px)")
                            locked_speaker_id = speaker_id
                            break

            # Generate keyframe for locked speaker
            if locked_speaker_id is not None and locked_speaker_id in current_frame_speakers:
                locked_speaker = current_frame_speakers[locked_speaker_id]
                time_since_last = timestamp - last_keyframe_time

                # Create keyframe based on motion OR time interval
                should_create_keyframe = (
                    locked_speaker['total_movement'] >= motion_threshold or
                    time_since_last >= max_keyframe_interval
                )

                if should_create_keyframe:
                    face = locked_speaker['face']
                    bbox = face['bbox']
                    face_center = locked_speaker['center']

                    # Calculate crop position
                    crop_x, crop_y = calculate_crop_position(
                        face_center[0],
                        face_center[1],
                        bbox['w'],
                        bbox['h'],
                        crop_w,
                        crop_h,
                        video_width,
                        video_height,
                        padding_ratio
                    )

                    motion_keyframes.append({
                        'timestamp': timestamp,
                        'crop_x': crop_x,
                        'crop_y': crop_y,
                        'crop_w': crop_w,
                        'crop_h': crop_h,
                        'speaker_text': f'Speaker {locked_speaker_id}',
                        'source': 'motion',
                        'speaker_id': locked_speaker_id,
                        'face_center': face_center,
                        'face_bbox': (bbox['x'], bbox['y'], bbox['w'], bbox['h'])
                    })

                    # Reset movement counter after keyframe
                    locked_speaker['total_movement'] = 0.0
                    last_keyframe_time = timestamp

    print(f"[StickyTracking] Generated {len(motion_keyframes)} motion keyframes with sticky speaker logic")
    return motion_keyframes


def calculate_center_crop(
    video_width: int,
    video_height: int,
    target_aspect: str
) -> Tuple[List[Dict], Tuple[int, int]]:
    """
    Calculate static center crop as fallback when no faces detected.

    Args:
        video_width: Video width
        video_height: Video height
        target_aspect: Target aspect ratio

    Returns:
        Tuple of (crop_timeline, crop_dimensions)
    """
    target_w, target_h = ASPECT_RATIOS.get(target_aspect, ASPECT_RATIOS['9:16'])
    target_ratio = target_w / target_h

    crop_w, crop_h = calculate_crop_dimensions(video_width, video_height, target_ratio)

    # Center crop position
    crop_x = (video_width - crop_w) // 2
    crop_y = (video_height - crop_h) // 2

    crop_timeline = [{
        'timestamp': 0,
        'crop_x': crop_x,
        'crop_y': crop_y,
        'crop_w': crop_w,
        'crop_h': crop_h,
        'speaker_text': 'Center crop (no faces)'
    }]

    print(f"[SmartCrop] Center crop: x={crop_x}, y={crop_y}, {crop_w}x{crop_h}")
    return crop_timeline, (crop_w, crop_h)


def interpolate_crop_timeline(
    crop_timeline: List[Dict],
    fps: float = 30.0,
    duration: float = None
) -> List[Dict]:
    """
    Interpolate crop positions for every frame (optional enhancement).

    This creates a crop keyframe for every video frame by interpolating
    between speaker segments.

    Args:
        crop_timeline: Sparse crop timeline (one per segment)
        fps: Video frames per second
        duration: Video duration in seconds (optional)

    Returns:
        Dense crop timeline (one per frame)
    """
    if not crop_timeline:
        return []

    if len(crop_timeline) == 1:
        # Only one keyframe - no interpolation needed
        return crop_timeline

    # Determine duration
    if duration is None:
        duration = crop_timeline[-1]['timestamp'] + 5.0  # Add 5s buffer

    # Create frame timestamps
    num_frames = int(duration * fps)
    frame_timestamps = np.linspace(0, duration, num_frames)

    # Extract keyframe data
    keyframe_times = np.array([c['timestamp'] for c in crop_timeline])
    keyframe_x = np.array([c['crop_x'] for c in crop_timeline])
    keyframe_y = np.array([c['crop_y'] for c in crop_timeline])

    # Interpolate
    interp_x = np.interp(frame_timestamps, keyframe_times, keyframe_x)
    interp_y = np.interp(frame_timestamps, keyframe_times, keyframe_y)

    # Build dense timeline
    crop_w = crop_timeline[0]['crop_w']
    crop_h = crop_timeline[0]['crop_h']

    dense_timeline = []
    for i, t in enumerate(frame_timestamps):
        dense_timeline.append({
            'timestamp': float(t),
            'crop_x': int(interp_x[i]),
            'crop_y': int(interp_y[i]),
            'crop_w': crop_w,
            'crop_h': crop_h
        })

    return dense_timeline


def generate_multi_speaker_crop(
    speakers: List[Dict],
    video_width: int,
    video_height: int,
    target_aspect: str = '9:16'
) -> Tuple[List[Dict], Tuple[int, int]]:
    """
    Generate side-by-side crop for multiple simultaneous speakers.

    For 2 speakers in a 9:16 video:
    - Split frame into two 540px sections
    - Crop each speaker into their section

    Args:
        speakers: List of speaker data from speaker_activity
        video_width: Video width
        video_height: Video height
        target_aspect: Target aspect ratio

    Returns:
        Tuple of (crop_timeline, crop_dimensions) for multi-speaker layout
    """
    if len(speakers) != 2:
        # For now, only handle 2 speakers - fallback to wide crop for others
        print(f"[SmartCrop] Multi-speaker ({len(speakers)} speakers) - using wide crop")
        return calculate_wide_crop_for_speakers(speakers, video_width, video_height, target_aspect)

    print("[SmartCrop] Generating side-by-side crop for 2 speakers")

    # For 9:16, split into two 540x1920 sections
    target_w, target_h = ASPECT_RATIOS.get(target_aspect, ASPECT_RATIOS['9:16'])

    # This is complex for FFmpeg - for now, return wide crop that includes both
    # TODO: Implement true side-by-side with FFmpeg hstack filter in Phase 4
    return calculate_wide_crop_for_speakers(speakers, video_width, video_height, target_aspect)


def calculate_wide_crop_for_speakers(
    speakers: List[Dict],
    video_width: int,
    video_height: int,
    target_aspect: str
) -> Tuple[List[Dict], Tuple[int, int]]:
    """
    Calculate a wide crop that includes all speakers.

    Args:
        speakers: List of speaker data
        video_width: Video width
        video_height: Video height
        target_aspect: Target aspect ratio

    Returns:
        Crop that encompasses all speakers
    """
    # Find bounding box that includes all speakers
    all_x = [s['face_center'][0] for s in speakers]
    all_y = [s['face_center'][1] for s in speakers]

    min_x = min(all_x)
    max_x = max(all_x)
    center_x = (min_x + max_x) // 2
    center_y = int(np.mean(all_y))

    # Calculate crop around this center
    target_w, target_h = ASPECT_RATIOS.get(target_aspect, ASPECT_RATIOS['9:16'])
    target_ratio = target_w / target_h
    crop_w, crop_h = calculate_crop_dimensions(video_width, video_height, target_ratio)

    crop_x = max(0, min(center_x - crop_w // 2, video_width - crop_w))
    crop_y = max(0, min(center_y - crop_h // 2, video_height - crop_h))

    crop_timeline = [{
        'timestamp': speakers[0].get('start', 0),
        'crop_x': crop_x,
        'crop_y': crop_y,
        'crop_w': crop_w,
        'crop_h': crop_h,
        'speaker_text': f'Multi-speaker ({len(speakers)} speakers)'
    }]

    return crop_timeline, (crop_w, crop_h)
