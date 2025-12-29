"""
Object Detection Feature Extractor Plugin

Detects objects in video frames using YOLOv8n ONNX:
- Gaming objects (keyboard, mouse, monitor, controller)
- Cooking objects (bowl, knife, spoon, oven)
- Fitness objects (sports ball, dumbbells, equipment)
- Product review objects (cell phone, laptop, products)
- Sports objects (ball, sports equipment)
- General objects (80 COCO classes)
"""

from typing import Dict, Any, Optional, List
from classification.core import IFeatureExtractorPlugin, PluginMetadata, PluginType
import os


class ObjectDetectionExtractorPlugin(IFeatureExtractorPlugin):
    """
    Extracts object detection features from video frames

    Uses YOLOv8n (ONNX format) to detect objects in frames.
    Returns object counts, categories, and context information
    for improved classification and smart framing.

    Cost: MODERATE (100-200ms per frame, sample 5-10 frames)
    """

    # COCO class names (80 classes)
    COCO_CLASSES = [
        'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
        'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog',
        'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
        'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
        'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
        'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich',
        'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
        'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
        'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
        'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
    ]

    # Category-specific object mappings
    CATEGORY_OBJECTS = {
        'gaming': ['keyboard', 'mouse', 'tv', 'laptop', 'cell phone', 'remote'],
        'cooking': ['bowl', 'knife', 'spoon', 'fork', 'cup', 'oven', 'microwave', 'sink',
                    'refrigerator', 'dining table', 'bottle', 'wine glass'],
        'fitness': ['sports ball', 'bicycle', 'skateboard', 'surfboard', 'tennis racket',
                    'baseball bat', 'skis', 'snowboard', 'frisbee', 'bench'],
        'sports': ['sports ball', 'bicycle', 'skateboard', 'surfboard', 'tennis racket',
                   'baseball bat', 'baseball glove', 'skis', 'snowboard', 'frisbee', 'kite'],
        'product_review': ['cell phone', 'laptop', 'mouse', 'keyboard', 'remote', 'book',
                          'backpack', 'handbag', 'suitcase', 'bottle', 'clock', 'vase'],
        'dance': ['person'],  # Full body detection
        'tutorial': ['book', 'laptop', 'keyboard', 'mouse', 'tv'],
        'talking_head': ['person', 'chair', 'couch', 'potted plant'],
        'vlog': ['person', 'car', 'bicycle', 'backpack', 'cell phone'],
        'news': ['person', 'tv', 'laptop', 'book', 'chair', 'couch']
    }

    def __init__(self):
        super().__init__()
        self._metadata = PluginMetadata(
            plugin_id="object_detection_extractor_v1",
            plugin_type=PluginType.FEATURE_EXTRACTOR,
            name="Object Detection Feature Extractor",
            version="1.0.0",
            author="OpusClip Team",
            description="Detects objects in video frames using YOLOv8n ONNX for context-aware classification",
            priority=3,  # Medium-high priority (moderate cost, high value)
            cost_estimate_ms=500.0,  # ~100ms per frame × 5 frames
            provides_features=["objects"],
            tags=["objects", "detection", "yolo", "context"]
        )
        self._onnx_session = None
        self._numpy = None
        self._cv2 = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize ONNX Runtime and YOLOv8n model

        Args:
            config: Configuration dictionary

        Returns:
            True if initialization successful
        """
        self._config = config
        try:
            import onnxruntime as ort
            import numpy as np
            import cv2

            self._numpy = np
            self._cv2 = cv2

            # Look for YOLOv8n ONNX model
            model_path = config.get('object_detection_model_path',
                                   '/var/task/classification/models/yolov8n.onnx')

            # Check if model exists
            if not os.path.exists(model_path):
                # Try alternate paths
                alternate_paths = [
                    'classification/models/yolov8n.onnx',
                    'models/yolov8n.onnx',
                    'yolov8n.onnx'
                ]
                for alt_path in alternate_paths:
                    if os.path.exists(alt_path):
                        model_path = alt_path
                        break
                else:
                    print(f"[ObjectDetection] Model not found at {model_path}")
                    print(f"[ObjectDetection] Tried alternate paths: {alternate_paths}")
                    print(f"[ObjectDetection] Plugin will be disabled until model is available")
                    self._initialized = False
                    return False

            # Initialize ONNX Runtime session
            print(f"[ObjectDetection] Loading YOLOv8n model from: {model_path}")
            self._onnx_session = ort.InferenceSession(
                model_path,
                providers=['CPUExecutionProvider']  # Use CPU (Lambda doesn't have GPU)
            )

            # Get model input details
            self._input_name = self._onnx_session.get_inputs()[0].name
            self._input_shape = self._onnx_session.get_inputs()[0].shape
            self._input_height = self._input_shape[2]  # Usually 640
            self._input_width = self._input_shape[3]   # Usually 640

            self._initialized = True
            print(f"[ObjectDetection] Initialized with YOLOv8n ONNX")
            print(f"[ObjectDetection] Input shape: {self._input_shape}")
            print(f"[ObjectDetection] Detecting {len(self.COCO_CLASSES)} object classes")
            return True

        except ImportError as e:
            print(f"[ObjectDetection] Required libraries not available: {e}")
            self._initialized = False
            return False
        except Exception as e:
            print(f"[ObjectDetection] Initialization failed: {e}")
            self._initialized = False
            return False

    def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract object detection features from video

        Args:
            video_path: Path to video file
            clip_info: Clip metadata

        Returns:
            Dictionary of detected objects and categories
        """
        if not self._onnx_session:
            return self._get_fallback_features()

        try:
            # Open video
            cap = self._cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[ObjectDetection] Failed to open video: {video_path}")
                return self._get_fallback_features()

            fps = cap.get(self._cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            # Sample 5-10 frames evenly across video
            num_samples = min(10, max(5, int(duration / 5)))  # 1 frame every 5 seconds
            sample_indices = self._numpy.linspace(0, total_frames - 1, num_samples, dtype=int)

            all_detections = []

            # Process sampled frames
            for frame_idx in sample_indices:
                cap.set(self._cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret:
                    continue

                # Detect objects in frame
                detections = self._detect_objects(frame)
                all_detections.extend(detections)

            cap.release()

            # Aggregate detections across all frames
            features = self._aggregate_detections(all_detections)

            print(f"[ObjectDetection] >>> Extracted Object Features:")
            print(f"  Frames analyzed: {num_samples}")
            print(f"  Total detections: {len(all_detections)}")
            print(f"  Unique objects: {len(features['detected_objects'])}")
            print(f"  Top objects: {features['top_objects'][:5]}")
            print(f"  Category scores: {features['category_scores']}")

            return features

        except Exception as e:
            print(f"[ObjectDetection] Error during extraction: {e}")
            return self._get_fallback_features()

    def _detect_objects(self, frame: Any, confidence_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Detect objects in a single frame using YOLOv8n

        Args:
            frame: OpenCV frame (BGR)
            confidence_threshold: Minimum confidence for detection

        Returns:
            List of detections [{class, confidence, bbox}, ...]
        """
        # Preprocess frame
        input_tensor = self._preprocess_frame(frame)

        # Run inference
        outputs = self._onnx_session.run(None, {self._input_name: input_tensor})

        # Postprocess outputs
        detections = self._postprocess_outputs(outputs[0], confidence_threshold)

        return detections

    def _preprocess_frame(self, frame: Any) -> Any:
        """
        Preprocess frame for YOLOv8n input

        Args:
            frame: OpenCV frame (BGR)

        Returns:
            Preprocessed tensor (1, 3, 640, 640)
        """
        # Resize to model input size (640x640)
        resized = self._cv2.resize(frame, (self._input_width, self._input_height))

        # Convert BGR to RGB
        rgb = self._cv2.cvtColor(resized, self._cv2.COLOR_BGR2RGB)

        # Normalize to [0, 1]
        normalized = rgb.astype(self._numpy.float32) / 255.0

        # Transpose from HWC to CHW
        chw = self._numpy.transpose(normalized, (2, 0, 1))

        # Add batch dimension
        batch = self._numpy.expand_dims(chw, axis=0)

        return batch

    def _postprocess_outputs(self, output: Any, confidence_threshold: float) -> List[Dict[str, Any]]:
        """
        Postprocess YOLOv8 outputs to get detections

        Args:
            output: Model output tensor
            confidence_threshold: Minimum confidence

        Returns:
            List of detections
        """
        detections = []

        # YOLOv8 output format: (1, 84, 8400) = (batch, 4_bbox + 80_classes, num_predictions)
        # Transpose to (8400, 84) for easier processing
        predictions = output[0].transpose()  # (8400, 84)

        for pred in predictions:
            # Extract bbox and class scores
            bbox = pred[:4]  # [x_center, y_center, width, height]
            class_scores = pred[4:]  # 80 class scores

            # Get max class score and index
            class_id = self._numpy.argmax(class_scores)
            confidence = class_scores[class_id]

            if confidence >= confidence_threshold:
                detections.append({
                    'class': self.COCO_CLASSES[class_id],
                    'class_id': int(class_id),
                    'confidence': float(confidence),
                    'bbox': bbox.tolist()
                })

        return detections

    def _aggregate_detections(self, all_detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate detections across all frames

        Args:
            all_detections: List of all detections from all frames

        Returns:
            Aggregated feature dictionary
        """
        if not all_detections:
            return self._get_fallback_features()

        # Count occurrences of each object class
        object_counts = {}
        for det in all_detections:
            class_name = det['class']
            object_counts[class_name] = object_counts.get(class_name, 0) + 1

        # Sort by frequency
        sorted_objects = sorted(object_counts.items(), key=lambda x: x[1], reverse=True)

        # Calculate category scores based on detected objects
        category_scores = {}
        for category, objects in self.CATEGORY_OBJECTS.items():
            score = 0.0
            for obj in objects:
                if obj in object_counts:
                    # Weighted by frequency
                    score += object_counts[obj] / len(all_detections)

            # Normalize by number of category objects
            category_scores[category] = min(1.0, score / max(len(objects) * 0.1, 1.0))

        # Identify dominant category
        dominant_category = max(category_scores.items(), key=lambda x: x[1]) if category_scores else (None, 0.0)

        return {
            'detected_objects': object_counts,
            'top_objects': [obj for obj, _ in sorted_objects[:10]],
            'object_count': len(object_counts),
            'total_detections': len(all_detections),
            'category_scores': category_scores,
            'dominant_category': dominant_category[0],
            'dominant_category_score': dominant_category[1],
            'has_person': 'person' in object_counts,
            'person_count': object_counts.get('person', 0),
            'has_gaming_objects': any(obj in object_counts for obj in self.CATEGORY_OBJECTS['gaming']),
            'has_cooking_objects': any(obj in object_counts for obj in self.CATEGORY_OBJECTS['cooking']),
            'has_fitness_objects': any(obj in object_counts for obj in self.CATEGORY_OBJECTS['fitness']),
            'has_sports_objects': any(obj in object_counts for obj in self.CATEGORY_OBJECTS['sports'])
        }

    def _get_fallback_features(self) -> Dict[str, Any]:
        """
        Return default features when detection fails

        Returns:
            Dictionary with default values
        """
        return {
            'detected_objects': {},
            'top_objects': [],
            'object_count': 0,
            'total_detections': 0,
            'category_scores': {},
            'dominant_category': None,
            'dominant_category_score': 0.0,
            'has_person': False,
            'person_count': 0,
            'has_gaming_objects': False,
            'has_cooking_objects': False,
            'has_fitness_objects': False,
            'has_sports_objects': False
        }
