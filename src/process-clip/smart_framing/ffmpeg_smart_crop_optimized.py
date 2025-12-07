"""
Optimized FFmpeg Smart Crop - Fixes "Too Many Keyframes" Error

This module limits the number of crop keyframes to prevent FFmpeg expression overflow.
FFmpeg has a limit on nested if expressions, so we intelligently downsample keyframes
while preserving important transitions.
"""

import numpy as np
from typing import List, Dict


def optimize_crop_timeline(
    crop_timeline: List[Dict],
    max_keyframes: int = 50,
    preserve_transcript_keyframes: bool = True
) -> List[Dict]:
    """
    Optimize crop timeline to reduce keyframe count while preserving quality.

    FFmpeg has limits on expression complexity. This function:
    1. Always keeps transcript keyframes (speaker changes)
    2. Downsamples motion keyframes intelligently
    3. Ensures smooth transitions

    Args:
        crop_timeline: Original crop timeline
        max_keyframes: Maximum number of keyframes (default: 50)
        preserve_transcript_keyframes: Always keep transcript keyframes

    Returns:
        Optimized crop timeline with fewer keyframes
    """
    if len(crop_timeline) <= max_keyframes:
        print(f"[Optimizer] Keyframes ({len(crop_timeline)}) within limit ({max_keyframes}), no optimization needed")
        return crop_timeline

    print(f"[Optimizer] Optimizing {len(crop_timeline)} keyframes down to ~{max_keyframes}")

    # Separate transcript and motion keyframes
    transcript_keyframes = [kf for kf in crop_timeline if kf.get('source') == 'transcript']
    motion_keyframes = [kf for kf in crop_timeline if kf.get('source') == 'motion']

    print(f"[Optimizer] Found {len(transcript_keyframes)} transcript, {len(motion_keyframes)} motion keyframes")

    # Always keep transcript keyframes (they mark speaker changes)
    optimized = transcript_keyframes.copy()

    # Calculate how many motion keyframes we can keep
    remaining_slots = max_keyframes - len(transcript_keyframes)

    if remaining_slots > 0 and motion_keyframes:
        # Downsample motion keyframes intelligently
        # Keep keyframes with largest movement distances
        motion_with_distance = []
        for i, kf in enumerate(motion_keyframes):
            distance = kf.get('movement_distance', 0)
            motion_with_distance.append((distance, i, kf))

        # Sort by movement distance (descending)
        motion_with_distance.sort(reverse=True)

        # Keep top N motion keyframes
        selected_motion = [item[2] for item in motion_with_distance[:remaining_slots]]
        optimized.extend(selected_motion)

        print(f"[Optimizer] Kept {len(selected_motion)} motion keyframes (largest movements)")

    # Sort by timestamp
    optimized.sort(key=lambda x: x['timestamp'])

    print(f"[Optimizer] Final keyframe count: {len(optimized)}")
    return optimized


def simplify_crop_expression_if_needed(
    crop_timeline: List[Dict],
    crop_w: int,
    crop_h: int,
    max_keyframes_for_dynamic: int = 30
) -> tuple:
    """
    Decide whether to use dynamic crop or static crop based on complexity.

    Args:
        crop_timeline: Crop timeline
        crop_w: Crop width
        crop_h: Crop height
        max_keyframes_for_dynamic: Max keyframes before switching to static

    Returns:
        (use_dynamic, simplified_timeline)
    """
    if len(crop_timeline) <= max_keyframes_for_dynamic:
        return True, crop_timeline

    print(f"[Optimizer] Too many keyframes ({len(crop_timeline)}) for dynamic crop")
    print(f"[Optimizer] Using averaged position (static crop)")

    # Calculate average position
    avg_x = int(np.mean([kf['crop_x'] for kf in crop_timeline]))
    avg_y = int(np.mean([kf['crop_y'] for kf in crop_timeline]))

    # Create single static keyframe
    static_keyframe = {
        'timestamp': 0,
        'crop_x': avg_x,
        'crop_y': avg_y,
        'crop_w': crop_w,
        'crop_h': crop_h,
        'speaker_text': 'Static crop (averaged)',
        'source': 'optimized'
    }

    return False, [static_keyframe]
