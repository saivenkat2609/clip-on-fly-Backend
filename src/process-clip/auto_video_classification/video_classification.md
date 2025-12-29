
  Video Classification System for Social Media Content

  Classification Framework

  I'll create a multi-factor analysis system that examines:
  1. Movement patterns (face, camera, overall)
  2. Audio characteristics (speech density, music, silence)
  3. Visual features (face detection, scene changes)
  4. Content structure (speaking patterns, pauses)

  ---
  Video Categories & Clipping Strategies

  1. TALKING HEAD / PODCAST / INTERVIEW

  Characteristics:
  - Minimal face movement (< 30px/frame avg)
  - High speech density (> 70% audio with voice)
  - 1-2 faces detected consistently
  - Low scene change rate
  - Stationary camera

  Detection signals:
  {
      'face_movement': < 30,
      'speech_density': > 0.7,
      'face_count_avg': 1-2,
      'scene_changes_per_min': < 2,
      'camera_motion': 'minimal'
  }

  Clipping Strategy:
  - ✅ Smart framing with small dead zone (150px)
  - ✅ Word-level karaoke subtitles
  - ✅ Focus on 9:16 vertical (Shorts/Reels)
  - ✅ Clip detection: Look for complete thoughts/stories (30-60s)
  - ✅ Prioritize emotional peaks, laughs, "hot takes"
  - Transitions: Hard cuts between clips (no motion blur needed)

  ---
  2. TUTORIAL / HOW-TO / EDUCATIONAL

  Characteristics:
  - Moderate face movement (30-80px/frame)
  - Medium speech density (50-70%)
  - 1 face, but hands/objects also visible
  - Demonstrates steps/processes
  - Some camera zooms/pans

  Detection signals:
  {
      'face_movement': 30-80,
      'speech_density': 0.5-0.7,
      'face_count_avg': 1,
      'hands_detected': True,
      'scene_changes_per_min': 3-8,
      'keywords': ['first', 'next', 'step', 'how to', 'show you']
  }

  Clipping Strategy:
  - ⚠️ Hybrid: Smart framing for talking, center-crop for demonstrations
  - ✅ Simple subtitles (not karaoke - less distracting)
  - ✅ 16:9 OR 9:16 depending on demo (horizontal if showing screen/workspace)
  - ✅ Clip detection: Complete tutorial steps (15-45s per step)
  - ✅ Look for phrases: "Here's how...", "The trick is...", "Pro tip..."
  - Transitions: Smooth transitions between steps

  Special handling:
  if 'screen_recording_detected' or 'hands_working_detected':
      use_center_crop = True
      add_zoom_to_important_areas = True

  ---
  3. VLOG / WALK-AND-TALK

  Characteristics:
  - High face movement (80-150px/frame)
  - High speech density (> 70%)
  - 1 face, moving through environments
  - Lots of camera movement (handheld, selfie stick)
  - Background changes frequently

  Detection signals:
  {
      'face_movement': 80-150,
      'speech_density': > 0.7,
      'camera_motion': 'high',
      'background_variance': 'high',
      'face_size_variance': 'high'  # Gets closer/farther from camera
  }

  Clipping Strategy:
  - ❌ NO smart framing (too much camera motion)
  - ✅ CENTER CROP always
  - ✅ Stabilization if available
  - ✅ Karaoke subtitles (helps with shaky footage)
  - ✅ 9:16 vertical priority
  - ✅ Clip detection: Emotional moments, interesting observations (20-45s)
  - ⚠️ Be careful with motion: Avoid clips with too much shake

  ---
  4. SPORTS / ACTION / FAST MOVEMENT

  Characteristics:
  - Very high movement (> 200px/frame)
  - Low speech density (< 30%, mostly ambient/crowd noise)
  - Multiple faces or no faces
  - Very high scene change rate
  - Athletic activity detected

  Detection signals:
  {
      'face_movement': > 200,
      'overall_motion': > 150,  # Optical flow magnitude
      'speech_density': < 0.3,
      'face_count_variance': 'high',
      'scene_changes_per_min': > 15
  }

  Clipping Strategy:
  - ❌ NO smart framing
  - ✅ CENTER CROP only
  - ❌ NO subtitles (distracting from action)
  - ✅ 1:1 square OR 16:9 horizontal (need full frame for action)
  - ✅ Clip detection: Key moments (goals, tricks, fails) - 10-20s
  - ✅ Look for crowd reactions, replays
  - Special: Slow-motion detection - don't re-slow
  - Avoid: Mid-action cuts (cut at peaks or resolutions)

  ---
  5. DANCE / CHOREOGRAPHY / PERFORMANCE

  Characteristics:
  - Very high full-body movement
  - Low speech (< 20%, mostly music)
  - 1 or more people in synchronized motion
  - Music beat synchronization
  - Full body must be visible

  Detection signals:
  {
      'face_movement': > 150,
      'full_body_movement': > 200,
      'speech_density': < 0.2,
      'music_beat_detected': True,
      'body_pose_detected': True,
      'rhythmic_motion': True
  }

  Clipping Strategy:
  - ❌ NO smart framing
  - ❌ NO face-focused crop (need full body!)
  - ✅ CENTER CROP with body-aware framing
  - ❌ NO subtitles
  - ✅ 9:16 vertical (full body fits well)
  - ✅ Clip detection: Complete choreography sections (15-30s)
  - ✅ Sync to music beats for cuts
  - ✅ Preserve full moves (don't cut mid-spin)

  Special: Detect body pose keypoints (shoulders, hips) instead of face

  ---
  6. GAMING / SCREEN RECORDING + COMMENTARY

  Characteristics:
  - Screen content (static or moving)
  - Face in corner (PIP) or no face
  - Medium-high speech density (commentary)
  - Gameplay action on screen

  Detection signals:
  {
      'screen_recording': True,
      'face_position': 'corner' or 'pip',
      'face_size': 'small' (< 15% of frame),
      'ui_elements_detected': True,
      'speech_density': 0.5-0.8,
      'keywords': ['let\'s go', 'GG', 'clutch', 'nice']
  }

  Clipping Strategy:
  - ❌ NO smart framing (would crop game UI)
  - ✅ CENTER CROP or INTELLIGENT CROP (keep UI elements visible)
  - ✅ Simple subtitles (karaoke distracts from gameplay)
  - ✅ 9:16 vertical (crop to action area + face cam)
  - ✅ Clip detection: Epic plays, funny moments, reactions (15-45s)
  - ✅ Look for excitement peaks (voice volume spikes)

  Special handling:
  # Detect UI-safe zones (minimap, health bars, etc.)
  safe_zones = detect_game_ui_elements(frame)
  crop_position = avoid_cropping_ui(safe_zones)

  ---
  7. PRODUCT REVIEW / UNBOXING

  Characteristics:
  - Moderate movement (showing products)
  - Medium speech density (explaining)
  - Mix of face close-ups and product close-ups
  - Camera zooms/pans to products

  Detection signals:
  {
      'face_movement': 40-100,
      'object_focus_shifts': True,
      'speech_density': 0.5-0.7,
      'zoom_events': > 5,
      'keywords': ['review', 'unboxing', 'check out', 'features']
  }

  Clipping Strategy:
  - ⚠️ Hybrid: Smart framing for talking, center-crop for product demos
  - ✅ Simple subtitles
  - ✅ 9:16 OR 1:1 (depends on product shape)
  - ✅ Clip detection: Product highlights, key features (20-40s)
  - ✅ Look for "wow moments", first impressions

  ---
  8. COOKING / RECIPE

  Characteristics:
  - Overhead or side view of workspace
  - Hands doing work (not face-focused)
  - Medium speech density (instructions)
  - Process-oriented (sequential steps)

  Detection signals:
  {
      'face_visibility': < 30% of time,
      'hands_detected': > 70% of time,
      'overhead_angle': True,
      'speech_density': 0.4-0.6,
      'keywords': ['add', 'mix', 'cook', 'minutes', 'ingredients']
  }

  Clipping Strategy:
  - ❌ NO face-based smart framing
  - ✅ CENTER CROP or HANDS-FOCUSED crop
  - ✅ Simple subtitles with ingredients highlighted
  - ✅ 1:1 square (Instagram) OR 9:16 (Reels)
  - ✅ Clip detection: Individual recipe steps (15-30s)
  - ✅ Look for satisfying moments (sizzle, flip, final reveal)

  ---
  9. REACTION VIDEO

  Characteristics:
  - Minimal to moderate face movement
  - Split screen or PIP layout
  - High emotional expressions
  - Speech mixed with pauses (watching content)

  Detection signals:
  {
      'face_movement': 20-60,
      'emotion_variance': 'high',
      'split_screen_detected': True,
      'speech_pattern': 'bursts',  # Talk, pause, react, talk
      'keywords': ['oh my god', 'what', 'no way', 'wow']
  }

  Clipping Strategy:
  - ✅ Smart framing on reactor face (main content)
  - ✅ Karaoke subtitles for reactions
  - ✅ 9:16 vertical (stack reactor above content OR side-by-side)
  - ✅ Clip detection: Peak emotional reactions (10-30s)
  - ✅ Look for: gasps, laughs, shocked expressions
  - Special: Preserve context (show what they're reacting to)

  ---
  10. NEWS / COMMENTARY / ANALYSIS

  Characteristics:
  - Minimal face movement (anchor desk setup)
  - Very high speech density (> 80%)
  - Professional lighting/setup
  - Serious tone, formal speech patterns

  Detection signals:
  {
      'face_movement': < 20,
      'speech_density': > 0.8,
      'professional_setup': True,
      'lighting_quality': 'high',
      'speech_pace': 'measured',
      'keywords': ['according to', 'reported', 'statement', 'breaking']
  }

  Clipping Strategy:
  - ✅ Smart framing with tiny dead zone (100px)
  - ✅ Word-level subtitles
  - ✅ 9:16 AND 16:9 (dual output for different platforms)
  - ✅ Clip detection: Complete statements/arguments (30-60s)
  - ✅ Look for key quotes, strong statements, summaries

  ---
  11. FITNESS / WORKOUT

  Characteristics:
  - High full-body movement
  - Medium speech (instructions between exercises)
  - Need to see full body form
  - Repetitive motions

  Detection signals:
  {
      'full_body_movement': > 150,
      'repetitive_motion': True,
      'body_pose_detected': True,
      'speech_density': 0.3-0.5,
      'keywords': ['reps', 'sets', 'exercise', 'form', 'squeeze']
  }

  Clipping Strategy:
  - ❌ NO face framing
  - ✅ FULL BODY CENTER CROP
  - ✅ Simple subtitles (exercise names, rep counts)
  - ✅ 9:16 vertical (shows full body well)
  - ✅ Clip detection: Single exercises or short circuits (20-45s)
  - ✅ Sync to exercise rhythm (don't cut mid-rep)

  