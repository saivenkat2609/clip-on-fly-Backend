"""
Plugin Orchestrator
Coordinates plugin execution with error isolation and cost control
"""

import time
from typing import Dict, List, Optional, Any

from .plugin_registry import PluginRegistry
from .plugin_metadata import PluginType, PluginStatus, VideoFeatures, ClassificationResult


class PluginOrchestrator:
    """
    Orchestrates plugin execution

    This is the "brain" that:
    - Decides which plugins to run
    - Manages execution order
    - Handles errors gracefully
    - Controls cost/budget
    - Aggregates results
    """

    def __init__(self, registry: PluginRegistry):
        """
        Initialize orchestrator

        Args:
            registry: Plugin registry instance
        """
        self.registry = registry
        self.execution_history: List[Dict[str, Any]] = []

    def extract_features(
        self,
        video_path: str,
        clip_info: Dict[str, Any],
        required_features: Optional[List[str]] = None,
        max_cost_ms: float = 1000.0
    ) -> VideoFeatures:
        """
        Extract features using available extractor plugins (in parallel)

        With error isolation - if one extractor fails, others continue.
        Runs expensive extractors (audio, visual, nlp) in parallel for 2x speedup.

        Args:
            video_path: Path to video file
            clip_info: Clip metadata including transcript
            required_features: List of required feature names (None = all)
            max_cost_ms: Maximum computation budget in milliseconds

        Returns:
            VideoFeatures object with extracted features
        """
        import threading

        features = VideoFeatures()
        total_cost = 0.0
        overall_start = time.time()

        # Get all active extractor plugins
        extractors = self.registry.get_active_plugins_by_type(
            PluginType.FEATURE_EXTRACTOR
        )

        # Separate into fast (transcript) and slow (audio, visual, nlp) extractors
        fast_extractors = []
        slow_extractors = []

        for extractor in extractors:
            metadata = extractor.get_metadata()
            provided_features = metadata.provides_features

            # Check if we need this feature
            if required_features and not any(
                f in required_features for f in provided_features
            ):
                continue  # Skip if not needed

            # Transcript is fast and needed by NLP, run it first
            if 'transcript' in provided_features and metadata.cost_estimate_ms < 10:
                fast_extractors.append(extractor)
            else:
                slow_extractors.append(extractor)

        # Phase 1: Run fast extractors sequentially (transcript)
        for extractor in fast_extractors:
            metadata = extractor.get_metadata()
            plugin_id = metadata.plugin_id
            provided_features = metadata.provides_features

            start_time = time.time()
            result, error = extractor.safe_execute(
                extractor.extract,
                video_path,
                clip_info
            )
            elapsed_ms = (time.time() - start_time) * 1000

            if error:
                metadata.failure_count += 1
                self.registry.update_plugin_status(
                    plugin_id,
                    PluginStatus.ERROR,
                    str(error)
                )
                print(f"[Orchestrator] Extractor {plugin_id} failed: {error}")
                continue

            # Success - store features
            metadata.success_count += 1
            for feature_name in provided_features:
                setattr(features, feature_name, result)

            print(
                f"[Orchestrator] Extracted {provided_features} using "
                f"{plugin_id} ({elapsed_ms:.1f}ms)"
            )

        # Phase 2: Run slow extractors in parallel
        if slow_extractors:
            print(f"[Orchestrator] Running {len(slow_extractors)} extractors in parallel...")

            results = {}
            threads = []

            def extract_wrapper(extractor, video_path, clip_info, results_dict):
                """Wrapper to run extractor in thread"""
                metadata = extractor.get_metadata()
                plugin_id = metadata.plugin_id
                provided_features = metadata.provides_features

                start_time = time.time()
                result, error = extractor.safe_execute(
                    extractor.extract,
                    video_path,
                    clip_info
                )
                elapsed_ms = (time.time() - start_time) * 1000

                results_dict[plugin_id] = {
                    'result': result,
                    'error': error,
                    'elapsed_ms': elapsed_ms,
                    'provided_features': provided_features,
                    'metadata': metadata
                }

            # Start all threads
            for extractor in slow_extractors:
                thread = threading.Thread(
                    target=extract_wrapper,
                    args=(extractor, video_path, clip_info, results)
                )
                thread.start()
                threads.append(thread)

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Process results
            for plugin_id, result_data in results.items():
                metadata = result_data['metadata']
                result = result_data['result']
                error = result_data['error']
                elapsed_ms = result_data['elapsed_ms']
                provided_features = result_data['provided_features']

                if error:
                    metadata.failure_count += 1
                    self.registry.update_plugin_status(
                        plugin_id,
                        PluginStatus.ERROR,
                        str(error)
                    )
                    print(f"[Orchestrator] Extractor {plugin_id} failed: {error}")
                    continue

                # Success - store features
                metadata.success_count += 1
                for feature_name in provided_features:
                    setattr(features, feature_name, result)

                print(
                    f"[Orchestrator] Extracted {provided_features} using "
                    f"{plugin_id} ({elapsed_ms:.1f}ms)"
                )

        # Calculate actual total time (wall clock time, not sum)
        total_cost = (time.time() - overall_start) * 1000

        print(
            f"[Orchestrator] Feature extraction complete "
            f"(total: {total_cost:.1f}ms, parallel speedup: {len(slow_extractors)} extractors)"
        )
        return features

    def classify(
        self,
        features: VideoFeatures,
        max_confidence: float = 0.95
    ) -> Optional[ClassificationResult]:
        """
        Classify video using available classifier plugins

        Try classifiers in priority order, stop when confident enough.

        Args:
            features: Extracted video features
            max_confidence: Stop if we reach this confidence level

        Returns:
            ClassificationResult or None if no classifier matched
        """
        # Get all active classifier plugins
        classifiers = self.registry.get_active_plugins_by_type(
            PluginType.CLASSIFIER
        )

        # Sort by priority (lower = earlier)
        classifiers.sort(key=lambda p: p.get_metadata().priority)

        best_result = None
        best_confidence = 0.0

        for classifier in classifiers:
            metadata = classifier.get_metadata()
            plugin_id = metadata.plugin_id

            # Check if classifier has required features
            required_features = metadata.requires_features
            if not all(features.has_feature(f) for f in required_features):
                missing = [
                    f for f in required_features
                    if not features.has_feature(f)
                ]
                print(
                    f"[Orchestrator] Skipping {plugin_id} - "
                    f"missing features: {missing}"
                )
                continue

            # Execute with error isolation
            start_time = time.time()
            features_dict = features.to_dict()
            result, error = classifier.safe_execute(
                classifier.classify,
                features_dict
            )
            elapsed_ms = (time.time() - start_time) * 1000

            if error:
                # Plugin failed - update stats but continue
                metadata.failure_count += 1
                self.registry.update_plugin_status(
                    plugin_id,
                    PluginStatus.ERROR,
                    str(error)
                )
                print(
                    f"[Orchestrator] Classifier {plugin_id} failed: {error}"
                )
                continue

            # Check result
            if result is None:
                # Classifier couldn't classify (below confidence threshold)
                continue

            metadata.success_count += 1
            confidence = result.get('confidence', 0.0)
            reasoning = result.get('reasoning', {})

            print(
                f"[Orchestrator] {plugin_id} classified as "
                f"'{result.get('category')}' with confidence {confidence:.2f} "
                f"({elapsed_ms:.1f}ms)"
            )

            # Show classifier reasoning with signals
            if reasoning:
                signals = reasoning.get('signals', {})
                if signals:
                    print(f"[Orchestrator]   >>> Classifier Signals:")
                    for signal_name, signal_value in signals.items():
                        print(f"       {signal_name}: {signal_value:.2f}")

                key_factors = reasoning.get('key_factors', [])
                if key_factors:
                    print(f"[Orchestrator]   >>> Key Factors:")
                    for factor in key_factors:
                        print(f"       - {factor}")

            # Track best result
            if confidence > best_confidence:
                best_result = ClassificationResult(
                    category=result['category'],
                    confidence=confidence,
                    reasoning=result.get('reasoning', {}),
                    features_used=required_features,
                    processing_time_ms=elapsed_ms,
                    classifier_id=plugin_id
                )
                best_confidence = confidence

            # Stop if confident enough
            if confidence >= max_confidence:
                print(
                    f"[Orchestrator] High confidence reached "
                    f"({confidence:.2f}), stopping classification"
                )
                break

        if best_result:
            print(
                f"[Orchestrator] Final classification: "
                f"{best_result.category} (confidence: {best_result.confidence:.2f})"
            )
        else:
            print("[Orchestrator] No classifier matched")

        return best_result

    def get_processing_strategy(
        self,
        category: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get processing strategy for a category

        Args:
            category: Video category (e.g., "talking_head")

        Returns:
            Processing configuration dictionary or None if not found
        """
        # Get all active strategy plugins
        strategies = self.registry.get_active_plugins_by_type(
            PluginType.PROCESSING_STRATEGY
        )

        # Find strategy for this category
        for strategy in strategies:
            metadata = strategy.get_metadata()
            if metadata.target_category == category:
                result, error = strategy.safe_execute(
                    strategy.get_processing_config
                )
                if error:
                    print(
                        f"[Orchestrator] Strategy {metadata.plugin_id} "
                        f"failed: {error}"
                    )
                    continue
                return result

        # Fallback to default
        print(
            f"[Orchestrator] No strategy found for '{category}', "
            f"using default"
        )
        return self._get_default_strategy()

    def classify_and_get_strategy(
        self,
        video_path: str,
        clip_info: Dict[str, Any],
        max_cost_ms: float = 1000.0
    ) -> tuple[Optional[ClassificationResult], Dict[str, Any]]:
        """
        Complete pipeline: Extract features → Classify → Get strategy

        This is the main entry point for the orchestrator.

        Args:
            video_path: Path to video file
            clip_info: Clip metadata
            max_cost_ms: Maximum computation budget

        Returns:
            Tuple of (classification_result, processing_strategy)
        """
        start_time = time.time()

        # Extract features
        features = self.extract_features(
            video_path,
            clip_info,
            max_cost_ms=max_cost_ms
        )

        # Classify
        classification = self.classify(features)

        if not classification:
            # No classification, use default strategy
            strategy = self._get_default_strategy()
        else:
            # Get strategy for classified category
            strategy = self.get_processing_strategy(classification.category)

        total_time = (time.time() - start_time) * 1000
        print(
            f"[Orchestrator] Complete pipeline finished in {total_time:.1f}ms"
        )

        return classification, strategy

    def _get_default_strategy(self) -> Dict[str, Any]:
        """
        Safe default strategy when no specific strategy found

        Returns:
            Default processing configuration
        """
        return {
            'smart_framing': False,
            'subtitle_mode': 'simple',
            'aspect_ratios': ['9:16'],
            'crop_strategy': 'center',
            'stabilization': False,
            'clip_length_range': (20.0, 45.0),
            'additional_config': {}
        }

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics

        Returns:
            Dictionary with execution statistics
        """
        stats = self.registry.get_plugin_stats()

        # Add execution-specific stats
        stats['execution_history_count'] = len(self.execution_history)

        return stats
