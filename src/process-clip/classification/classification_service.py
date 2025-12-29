"""
Classification Service

Main facade for video classification system.
Provides simple interface for classifying videos and getting processing strategies.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .core import (
    PluginRegistry,
    PluginLoader,
    PluginManager,
    PluginOrchestrator,
    ClassificationResult
)


class ClassificationService:
    """
    Main service for video classification

    This is the primary interface that external code (like Lambda) uses.
    It hides all the complexity of the plugin system behind a simple API.

    Usage:
        service = ClassificationService()
        service.initialize()

        result, strategy = service.classify_video(
            video_path="/path/to/video.mp4",
            clip_info={"clip": {...}, ...}
        )
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize classification service

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

        # Core components
        self.registry = PluginRegistry()
        self.loader = PluginLoader(self.registry)
        self.manager = PluginManager(self.registry, self.loader)
        self.orchestrator = PluginOrchestrator(self.registry)

        self._initialized = False

    def initialize(self, plugin_config: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        """
        Initialize the classification system

        Discovers and loads all plugins, runs health checks.

        Args:
            plugin_config: Optional plugin-specific configuration

        Returns:
            True if initialization successful
        """
        if self._initialized:
            print("[ClassificationService] Already initialized")
            return True

        print("[ClassificationService] Initializing plugin system...")

        # Set plugin directories
        current_dir = Path(__file__).parent
        plugin_dirs = [
            current_dir / "plugins" / "extractors",
            current_dir / "plugins" / "classifiers",
            current_dir / "plugins" / "strategies"
        ]

        for plugin_dir in plugin_dirs:
            if plugin_dir.exists():
                self.loader.add_plugin_directory(str(plugin_dir))

        # Discover and load plugins
        discovery_results = self.loader.discover_and_load_all()
        total_loaded = sum(discovery_results.values())

        print(f"[ClassificationService] Discovered {total_loaded} plugins")

        # Load plugin configuration
        if plugin_config:
            self.manager.load_config_dict(plugin_config)

        # Initialize all plugins
        init_results = self.manager.initialize_all_plugins()
        active_count = sum(init_results.values())

        print(f"[ClassificationService] {active_count}/{len(init_results)} plugins active")

        # Run health checks
        health_results = self.manager.run_health_checks()
        healthy_count = sum(1 for is_healthy, _ in health_results.values() if is_healthy)

        print(f"[ClassificationService] {healthy_count}/{len(health_results)} plugins healthy")

        self._initialized = True
        return active_count > 0

    def classify_video(
        self,
        video_path: str,
        clip_info: Dict[str, Any],
        max_cost_ms: float = 1000.0
    ) -> Tuple[Optional[ClassificationResult], Dict[str, Any]]:
        """
        Classify video and get processing strategy

        This is the main entry point for classification.

        Args:
            video_path: Path to video file
            clip_info: Clip metadata including transcript
            max_cost_ms: Maximum computation budget in milliseconds

        Returns:
            Tuple of (classification_result, processing_strategy)

        Raises:
            RuntimeError: If service not initialized
        """
        if not self._initialized:
            raise RuntimeError(
                "ClassificationService not initialized. Call initialize() first."
            )

        print(f"[ClassificationService] Classifying video: {video_path}")

        # Use orchestrator to run complete pipeline
        classification, strategy = self.orchestrator.classify_and_get_strategy(
            video_path=video_path,
            clip_info=clip_info,
            max_cost_ms=max_cost_ms
        )

        if classification:
            print(
                f"[ClassificationService] Classification: {classification.category} "
                f"(confidence: {classification.confidence:.2f})"
            )
        else:
            print("[ClassificationService] No classification matched")

        return classification, strategy

    def classify_quick(
        self,
        clip_info: Dict[str, Any]
    ) -> Tuple[Optional[ClassificationResult], Dict[str, Any]]:
        """
        Quick classification using only transcript (no video processing)

        Use this for fast classification when video processing is expensive.

        Args:
            clip_info: Clip metadata including transcript

        Returns:
            Tuple of (classification_result, processing_strategy)
        """
        if not self._initialized:
            raise RuntimeError(
                "ClassificationService not initialized. Call initialize() first."
            )

        print("[ClassificationService] Quick classification (transcript only)")

        # Extract only transcript features (free!)
        features = self.orchestrator.extract_features(
            video_path="",  # Not needed for transcript
            clip_info=clip_info,
            required_features=["transcript"],
            max_cost_ms=0.0  # Only free features
        )

        # Classify with limited features
        classification = self.orchestrator.classify(features)

        # Get strategy
        if classification:
            strategy = self.orchestrator.get_processing_strategy(classification.category)
        else:
            strategy = self.orchestrator._get_default_strategy()

        return classification, strategy

    def get_plugin_stats(self) -> Dict[str, Any]:
        """
        Get statistics about plugin system

        Returns:
            Dictionary with plugin statistics
        """
        return self.manager.get_plugin_stats()

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics

        Returns:
            Dictionary with execution statistics
        """
        return self.orchestrator.get_execution_stats()

    def enable_plugin(self, plugin_id: str) -> bool:
        """
        Enable a disabled plugin

        Args:
            plugin_id: Plugin to enable

        Returns:
            True if successful
        """
        return self.manager.enable_plugin(plugin_id)

    def disable_plugin(self, plugin_id: str) -> bool:
        """
        Disable an active plugin

        Args:
            plugin_id: Plugin to disable

        Returns:
            True if successful
        """
        return self.manager.disable_plugin(plugin_id)

    def list_plugins(self) -> list:
        """
        List all registered plugins

        Returns:
            List of plugin information dictionaries
        """
        return self.manager.list_all_plugins()

    def shutdown(self):
        """
        Shutdown classification service

        Cleans up all plugins and resources.
        """
        print("[ClassificationService] Shutting down...")
        self.manager.shutdown_all_plugins()
        self._initialized = False


# Singleton instance for easy access
_service_instance: Optional[ClassificationService] = None


def get_classification_service(
    config: Optional[Dict[str, Any]] = None,
    force_new: bool = False
) -> ClassificationService:
    """
    Get or create classification service singleton

    Args:
        config: Optional configuration
        force_new: Force creation of new instance

    Returns:
        ClassificationService instance
    """
    global _service_instance

    if force_new or _service_instance is None:
        _service_instance = ClassificationService(config)

    return _service_instance
