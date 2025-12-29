"""
Video Classification System with Plugin Architecture

A flexible, extensible system for classifying videos and determining
optimal processing strategies.

Quick Start:
    from classification import get_classification_service

    # Initialize service
    service = get_classification_service()
    service.initialize()

    # Classify video
    classification, strategy = service.classify_video(
        video_path="/path/to/video.mp4",
        clip_info={"clip": {...}}
    )
"""

from .classification_service import (
    ClassificationService,
    get_classification_service
)

from .core.plugin_metadata import (
    PluginType,
    PluginStatus,
    PluginMetadata,
    ClassificationResult,
    VideoFeatures
)

from .core.plugin_interface import (
    IPlugin,
    BasePlugin,
    IFeatureExtractorPlugin,
    IClassifierPlugin,
    IProcessingStrategyPlugin
)

from .core.plugin_registry import PluginRegistry
from .core.plugin_loader import PluginLoader
from .core.plugin_manager import PluginManager
from .core.orchestrator import PluginOrchestrator

__version__ = "1.0.0"
__all__ = [
    # Main service
    'ClassificationService',
    'get_classification_service',
    # Metadata
    'PluginType',
    'PluginStatus',
    'PluginMetadata',
    'ClassificationResult',
    'VideoFeatures',
    # Interfaces
    'IPlugin',
    'BasePlugin',
    'IFeatureExtractorPlugin',
    'IClassifierPlugin',
    'IProcessingStrategyPlugin',
    # Management
    'PluginRegistry',
    'PluginLoader',
    'PluginManager',
    'PluginOrchestrator',
]
