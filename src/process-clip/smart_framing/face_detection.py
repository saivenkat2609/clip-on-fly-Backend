"""
Face Detection Module using MediaPipe

This module provides face detection capabilities optimized for CPU execution
in AWS Lambda environment. Uses Google's MediaPipe for accurate, fast detection.

Key Features:
- CPU-optimized (no GPU required)
- Configurable confidence thresholds
- Frame sampling for performance
- Visualization support for debugging
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import List, Dict, Tuple, Optional


class FaceDetector:
    """
    Face detector using MediaPipe Face Detection.

    Optimized for detecting faces in video clips for smart cropping.
    Processes video segments with configurable frame sampling.

    Attributes:
        confidence_threshold (float): Minimum confidence for face detection (0.0 - 1.0)
        mp_face: MediaPipe face detection solution
        detector: MediaPipe face detection model instance
    """

    def __init__(self, confidence_threshold: float = 0.6):
        """
        Initialize face detector with MediaPipe.

        Args:
            confidence_threshold: Minimum confidence for valid detection (default: 0.6)
        """
        self.confidence_threshold = confidence_threshold
        self.mp_face = mp.solutions.face_detection
        self.detector = self.mp_face.FaceDetection(
            model_selection=0,  # 0 = short-range (< 2m), 1 = full-range (> 2m)
            min_detection_confidence=confidence_threshold
        )
        print(f"[FaceDetector] Initialized with confidence threshold: {confidence_threshold}")

    def detect_faces_in_video(
        self,
        video_path: str,
        start_sec: float = 0,
        end_sec: Optional[float] = None,
        sample_rate: int = 2
    ) -> List[Dict]:
        """
        Detect faces in a video clip.

        Args:
            video_path: Path to video file
            start_sec: Start time in seconds (default: 0)
            end_sec: End time in seconds (default: None = end of video)
            sample_rate: Process every Nth frame (default: 2 = every other frame)

        Returns:
            List of detections, each containing:
                {
                    'frame_num': int,
                    'timestamp': float (seconds),
                    'faces': [
                        {
                            'bbox': {'x': int, 'y': int, 'w': int, 'h': int},
                            'confidence': float
                        },
                        ...
                    ]
                }

        Raises:
            FileNotFoundError: If video file doesn't exist
            ValueError: If video cannot be opened
        """
        # Validate video file
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Cannot open video file: {video_path}")
        except Exception as e:
            raise FileNotFoundError(f"Video file error: {video_path} - {str(e)}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        print(f"[FaceDetector] Video: {video_path}")
        print(f"[FaceDetector] FPS: {fps:.2f}, Total frames: {total_frames}, Duration: {duration:.2f}s")

        # Set end time to video duration if not specified
        if end_sec is None or end_sec > duration:
            end_sec = duration

        print(f"[FaceDetector] Processing from {start_sec:.2f}s to {end_sec:.2f}s")
        print(f"[FaceDetector] Sample rate: every {sample_rate} frame(s)")

        # Seek to start position
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)

        frame_results = []
        frame_count = 0
        current_time = start_sec
        faces_detected_count = 0

        while current_time < end_sec:
            ret, frame = cap.read()
            if not ret:
                print(f"[FaceDetector] End of video reached at frame {frame_count}")
                break

            # Sample frames (process every Nth frame)
            if frame_count % sample_rate == 0:
                # Convert BGR to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Run face detection
                results = self.detector.process(rgb_frame)

                faces = []
                if results.detections:
                    h, w = frame.shape[:2]
                    for detection in results.detections:
                        # Get bounding box (normalized coordinates)
                        bbox = detection.location_data.relative_bounding_box

                        # Convert to pixel coordinates
                        x = int(bbox.xmin * w)
                        y = int(bbox.ymin * h)
                        width = int(bbox.width * w)
                        height = int(bbox.height * h)

                        # Ensure bbox is within frame bounds
                        x = max(0, min(x, w - 1))
                        y = max(0, min(y, h - 1))
                        width = min(width, w - x)
                        height = min(height, h - y)

                        faces.append({
                            'bbox': {
                                'x': x,
                                'y': y,
                                'w': width,
                                'h': height
                            },
                            'confidence': detection.score[0]
                        })
                        faces_detected_count += 1

                frame_results.append({
                    'frame_num': frame_count,
                    'timestamp': current_time,
                    'faces': faces
                })

            frame_count += 1
            current_time = start_sec + (frame_count / fps)

        cap.release()

        print(f"[FaceDetector] Processed {len(frame_results)} frames")
        print(f"[FaceDetector] Detected {faces_detected_count} faces total")

        return frame_results

    def visualize_detections(
        self,
        video_path: str,
        detections: List[Dict],
        output_path: str,
        start_sec: float = 0,
        end_sec: Optional[float] = None
    ) -> str:
        """
        Create annotated video with bounding boxes around detected faces.

        Useful for debugging and verifying detection quality.

        Args:
            video_path: Original video file path
            detections: Output from detect_faces_in_video()
            output_path: Path to save annotated video
            start_sec: Start time in seconds (default: 0)
            end_sec: End time in seconds (default: None = entire video)

        Returns:
            Path to saved annotated video

        Raises:
            ValueError: If video cannot be opened or written
        """
        print(f"[FaceDetector] Creating annotated video...")

        # Open original video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video for visualization: {video_path}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # Set end time to video duration if not specified
        if end_sec is None or end_sec > duration:
            end_sec = duration

        # Calculate frame range to process
        start_frame = int(start_sec * fps)
        end_frame = int(end_sec * fps)

        print(f"[FaceDetector] Output video will contain frames {start_frame} to {end_frame}")
        print(f"[FaceDetector] Time range: {start_sec:.2f}s to {end_sec:.2f}s")

        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not out.isOpened():
            raise ValueError(f"Cannot create output video: {output_path}")

        # Create lookup dict for faster access
        detections_by_frame = {d['frame_num']: d['faces'] for d in detections}

        # Seek to start position
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        frame_num = start_frame
        frames_with_faces = 0

        while frame_num < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            # Draw bounding boxes if faces detected in this frame
            if frame_num in detections_by_frame:
                faces = detections_by_frame[frame_num]
                if faces:
                    frames_with_faces += 1
                    for face in faces:
                        bbox = face['bbox']
                        confidence = face['confidence']

                        # Draw rectangle
                        cv2.rectangle(
                            frame,
                            (bbox['x'], bbox['y']),
                            (bbox['x'] + bbox['w'], bbox['y'] + bbox['h']),
                            (0, 255, 0),  # Green
                            2
                        )

                        # Add confidence label
                        label = f"{confidence:.2f}"
                        label_y = max(bbox['y'] - 10, 20)
                        cv2.putText(
                            frame,
                            label,
                            (bbox['x'], label_y),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 255, 0),
                            2
                        )

            # Add frame info
            info_text = f"Frame: {frame_num} | Faces: {len(detections_by_frame.get(frame_num, []))}"
            cv2.putText(
                frame,
                info_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            out.write(frame)
            frame_num += 1

        cap.release()
        out.release()

        frames_processed = frame_num - start_frame
        print(f"[FaceDetector] Annotated video saved to: {output_path}")
        print(f"[FaceDetector] Output contains {frames_processed} frames ({end_sec - start_sec:.2f}s)")
        print(f"[FaceDetector] {frames_with_faces} frames had face detections")

        return output_path

    def get_face_statistics(self, detections: List[Dict]) -> Dict:
        """
        Calculate statistics about detected faces.

        Useful for understanding detection quality and coverage.

        Args:
            detections: Output from detect_faces_in_video()

        Returns:
            Dictionary with statistics:
                {
                    'total_frames': int,
                    'frames_with_faces': int,
                    'total_faces': int,
                    'avg_faces_per_frame': float,
                    'avg_confidence': float,
                    'coverage_percent': float
                }
        """
        total_frames = len(detections)
        frames_with_faces = sum(1 for d in detections if d['faces'])
        total_faces = sum(len(d['faces']) for d in detections)

        # Calculate average confidence
        all_confidences = [face['confidence'] for d in detections for face in d['faces']]
        avg_confidence = np.mean(all_confidences) if all_confidences else 0.0

        # Calculate average faces per frame (only frames with faces)
        avg_faces_per_frame = total_faces / frames_with_faces if frames_with_faces > 0 else 0.0

        # Calculate coverage (percentage of frames with at least one face)
        coverage_percent = (frames_with_faces / total_frames * 100) if total_frames > 0 else 0.0

        return {
            'total_frames': total_frames,
            'frames_with_faces': frames_with_faces,
            'total_faces': total_faces,
            'avg_faces_per_frame': avg_faces_per_frame,
            'avg_confidence': avg_confidence,
            'coverage_percent': coverage_percent
        }

    def __del__(self):
        """Clean up MediaPipe resources."""
        if hasattr(self, 'detector'):
            self.detector.close()
