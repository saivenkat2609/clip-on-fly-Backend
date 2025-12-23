"""
Improved MediaPipe Face Detection Module

This module enhances the original MediaPipe implementation with:
- Better configuration (full-range model)
- Validation layer to filter false positives
- Temporal consistency checks
- Face quality scoring

Use this if you want to stick with MediaPipe but need better accuracy.
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import List, Dict, Tuple, Optional


class ImprovedMediaPipeFaceDetector:
    """
    Enhanced MediaPipe face detector with validation and filtering.

    Improvements over original:
    - Uses full-range detection model (model_selection=1)
    - Adds validation layer to filter false positives
    - Configurable size and aspect ratio filters
    - Temporal consistency tracking
    - Face quality scoring
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        min_face_size: int = 30,
        max_face_size: int = None,
        use_full_range_model: bool = True
    ):
        """
        Initialize improved MediaPipe detector.

        Args:
            confidence_threshold: Minimum confidence for detection (default: 0.7)
                                Higher = fewer false positives
            min_face_size: Minimum face size in pixels (default: 30)
            max_face_size: Maximum face size in pixels (default: None = auto)
            use_full_range_model: Use full-range model vs short-range (default: True)
                                 Full-range (model=1) better for distant faces
                                 Short-range (model=0) better for close-up faces
        """
        self.confidence_threshold = confidence_threshold
        self.min_face_size = min_face_size
        self.max_face_size = max_face_size

        # Initialize MediaPipe
        self.mp_face = mp.solutions.face_detection

        # model_selection: 0 = short-range (< 2m), 1 = full-range (> 2m)
        model_selection = 1 if use_full_range_model else 0

        self.detector = self.mp_face.FaceDetection(
            model_selection=model_selection,
            min_detection_confidence=confidence_threshold
        )

        print(f"[ImprovedMediaPipe] Initialized with:")
        print(f"  - Model: {'Full-range (1)' if use_full_range_model else 'Short-range (0)'}")
        print(f"  - Confidence threshold: {confidence_threshold}")
        print(f"  - Min face size: {min_face_size}px")
        print(f"  - Max face size: {max_face_size if max_face_size else 'auto'}")

        # Temporal consistency tracking
        self.previous_faces = []

    def detect_faces_in_video(
        self,
        video_path: str,
        start_sec: float = 0,
        end_sec: Optional[float] = None,
        sample_rate: int = 2,
        enable_temporal_filtering: bool = True
    ) -> List[Dict]:
        """
        Detect faces in video with enhanced validation.

        Args:
            video_path: Path to video file
            start_sec: Start time in seconds
            end_sec: End time in seconds (None = end of video)
            sample_rate: Process every Nth frame
            enable_temporal_filtering: Filter detections based on temporal consistency

        Returns:
            List of detections with format matching original FaceDetector
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Cannot open video file: {video_path}")
        except Exception as e:
            raise FileNotFoundError(f"Video file error: {video_path} - {str(e)}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        print(f"[ImprovedMediaPipe] Video: {video_path}")
        print(f"[ImprovedMediaPipe] Resolution: {width}x{height}, FPS: {fps:.2f}, Duration: {duration:.2f}s")

        # Auto-set max face size if not specified
        if self.max_face_size is None:
            self.max_face_size = int(min(width, height) * 0.8)

        if end_sec is None or end_sec > duration:
            end_sec = duration

        print(f"[ImprovedMediaPipe] Processing from {start_sec:.2f}s to {end_sec:.2f}s")
        print(f"[ImprovedMediaPipe] Sample rate: every {sample_rate} frame(s)")

        # Seek to start
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)

        frame_results = []
        frame_count = 0
        current_time = 0  # Use relative timestamps (0.00s = clip start)
        faces_detected_count = 0
        false_positives_filtered = 0

        # Reset temporal tracking
        self.previous_faces = []

        while start_sec + current_time < end_sec:
            ret, frame = cap.read()
            if not ret:
                print(f"[ImprovedMediaPipe] End of video at frame {frame_count}")
                break

            if frame_count % sample_rate == 0:
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Detect faces
                results = self.detector.process(rgb_frame)

                faces = []
                if results.detections:
                    h, w = frame.shape[:2]
                    for detection in results.detections:
                        bbox_data = detection.location_data.relative_bounding_box

                        # Convert to pixel coordinates
                        x = int(bbox_data.xmin * w)
                        y = int(bbox_data.ymin * h)
                        width_px = int(bbox_data.width * w)
                        height_px = int(bbox_data.height * h)

                        # Ensure within bounds
                        x = max(0, min(x, w - 1))
                        y = max(0, min(y, h - 1))
                        width_px = min(width_px, w - x)
                        height_px = min(height_px, h - y)

                        face = {
                            'bbox': {
                                'x': x,
                                'y': y,
                                'w': width_px,
                                'h': height_px
                            },
                            'confidence': detection.score[0]
                        }

                        faces.append(face)

                # Validate faces
                before_validation = len(faces)
                faces = self._validate_faces(faces, w, h)

                # Apply temporal filtering if enabled
                if enable_temporal_filtering and self.previous_faces:
                    faces = self._filter_temporal_consistency(faces, self.previous_faces)

                after_validation = len(faces)
                false_positives_filtered += (before_validation - after_validation)
                faces_detected_count += len(faces)

                # Update temporal tracking
                self.previous_faces = faces

                frame_results.append({
                    'frame_num': frame_count,
                    'timestamp': current_time,
                    'faces': faces
                })

            frame_count += 1
            current_time = frame_count / fps  # Relative time from clip start

        cap.release()

        print(f"[ImprovedMediaPipe] Processed {len(frame_results)} frames")
        print(f"[ImprovedMediaPipe] Detected {faces_detected_count} valid faces")
        print(f"[ImprovedMediaPipe] Filtered {false_positives_filtered} false positives")

        return frame_results

    def _validate_faces(
        self,
        faces: List[Dict],
        frame_width: int,
        frame_height: int
    ) -> List[Dict]:
        """
        Validate detected faces to filter false positives.

        Validation checks:
        1. Size constraints (min/max)
        2. Aspect ratio (faces should be roughly square)
        3. Position (within frame bounds)
        4. Area relative to frame
        """
        valid_faces = []

        for face in faces:
            bbox = face['bbox']
            w, h = bbox['w'], bbox['h']
            x, y = bbox['x'], bbox['y']

            # 1. Size validation
            if w < self.min_face_size or h < self.min_face_size:
                continue

            if self.max_face_size and (w > self.max_face_size or h > self.max_face_size):
                continue

            # 2. Aspect ratio validation (0.5 to 2.0)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                continue

            # 3. Position validation
            if x < 0 or y < 0 or x + w > frame_width or y + h > frame_height:
                continue

            # 4. Area validation (shouldn't take up more than 80% of frame)
            face_area = w * h
            frame_area = frame_width * frame_height
            area_ratio = face_area / frame_area

            if area_ratio > 0.8:
                continue

            valid_faces.append(face)

        return valid_faces

    def _filter_temporal_consistency(
        self,
        current_faces: List[Dict],
        previous_faces: List[Dict],
        max_movement: int = 200
    ) -> List[Dict]:
        """
        Filter faces based on temporal consistency.

        Removes faces that appear suddenly without corresponding detection
        in previous frame (likely false positives).

        Args:
            current_faces: Faces in current frame
            previous_faces: Faces in previous frame
            max_movement: Maximum pixel movement between frames

        Returns:
            Filtered list of consistent faces
        """
        if not previous_faces:
            return current_faces

        consistent_faces = []

        for curr_face in current_faces:
            curr_bbox = curr_face['bbox']
            curr_center = (
                curr_bbox['x'] + curr_bbox['w'] // 2,
                curr_bbox['y'] + curr_bbox['h'] // 2
            )

            # Check if this face is close to any previous face
            is_consistent = False
            for prev_face in previous_faces:
                prev_bbox = prev_face['bbox']
                prev_center = (
                    prev_bbox['x'] + prev_bbox['w'] // 2,
                    prev_bbox['y'] + prev_bbox['h'] // 2
                )

                # Calculate distance
                distance = np.sqrt(
                    (curr_center[0] - prev_center[0]) ** 2 +
                    (curr_center[1] - prev_center[1]) ** 2
                )

                if distance < max_movement:
                    is_consistent = True
                    break

            # On first appearance, accept face if confidence is high
            if not is_consistent and curr_face['confidence'] >= 0.85:
                is_consistent = True

            if is_consistent:
                consistent_faces.append(curr_face)

        return consistent_faces

    def get_face_statistics(self, detections: List[Dict]) -> Dict:
        """Calculate face detection statistics."""
        total_frames = len(detections)
        frames_with_faces = sum(1 for d in detections if d['faces'])
        total_faces = sum(len(d['faces']) for d in detections)

        all_confidences = [face['confidence'] for d in detections for face in d['faces']]
        avg_confidence = np.mean(all_confidences) if all_confidences else 0.0

        all_face_sizes = []
        for d in detections:
            for face in d['faces']:
                bbox = face['bbox']
                face_area = bbox['w'] * bbox['h']
                all_face_sizes.append(face_area)

        avg_face_size = np.mean(all_face_sizes) if all_face_sizes else 0.0
        coverage_percent = (frames_with_faces / total_frames * 100) if total_frames > 0 else 0.0

        return {
            'total_frames': total_frames,
            'frames_with_faces': frames_with_faces,
            'total_faces': total_faces,
            'avg_faces_per_frame': total_faces / frames_with_faces if frames_with_faces > 0 else 0.0,
            'avg_confidence': float(avg_confidence),
            'avg_face_size_px': float(avg_face_size),
            'coverage_percent': float(coverage_percent)
        }

    def __del__(self):
        """Clean up MediaPipe resources."""
        if hasattr(self, 'detector'):
            self.detector.close()
