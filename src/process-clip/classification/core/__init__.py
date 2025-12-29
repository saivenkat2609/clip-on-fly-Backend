"""
Core Plugin System Components

This module provides the foundation for the plugin-based classification system.
"""

from .plugin_metadata import (
    PluginType,
    PluginStatus,
    PluginDependency,
    PluginMetadata,
    ClassificationResult,
    VideoFeatures
)

from .plugin_interface import (
    IPlugin,
    BasePlugin,
    IFeatureExtractorPlugin,
    IClassifierPlugin,
    IProcessingStrategyPlugin,
    CircuitBreakerPlugin
)

from .plugin_registry import PluginRegistry
from .plugin_loader import PluginLoader
from .plugin_manager import PluginManager
from .orchestrator import PluginOrchestrator

__all__ = [
    # Metadata
    'PluginType',
    'PluginStatus',
    'PluginDependency',
    'PluginMetadata',
    'ClassificationResult',
    'VideoFeatures',
    # Interfaces
    'IPlugin',
    'BasePlugin',
    'IFeatureExtractorPlugin',
    'IClassifierPlugin',
    'IProcessingStrategyPlugin',
    'CircuitBreakerPlugin',
    # Registry and Management
    'PluginRegistry',
    'PluginLoader',
    'PluginManager',
    'PluginOrchestrator',
]
