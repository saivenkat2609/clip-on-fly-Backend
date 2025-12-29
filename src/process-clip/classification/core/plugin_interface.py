"""
Plugin Interfaces and Base Classes
Defines the contract that all plugins must follow
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Tuple
import traceback
import time

from .plugin_metadata import PluginMetadata, PluginStatus


class IPlugin(ABC):
    """
    Base interface for ALL plugins
    This is the contract that makes something a "plugin"

    Every plugin must implement these methods to be discovered and used.
    """

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """
        Return plugin metadata

        This is called during plugin discovery to understand
        what the plugin does and how to use it.
        """
        pass

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize plugin with configuration

        Args:
            config: Configuration dictionary for this plugin

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    def health_check(self) -> Tuple[bool, Optional[str]]:
        """
        Check if plugin is healthy and ready to use

        Returns:
            Tuple of (is_healthy, error_message)
            - is_healthy: True if plugin is working correctly
            - error_message: Error description if unhealthy, None otherwise
        """
        pass

    @abstractmethod
    def cleanup(self):
        """
        Clean up resources (called on shutdown)

        This should release any resources held by the plugin
        (file handles, network connections, etc.)
        """
        pass


class BasePlugin(IPlugin):
    """
    Base implementation with common functionality

    Plugins can inherit from this for convenience rather than
    implementing IPlugin directly.

    Provides:
    - Default metadata handling
    - Config management
    - Initialization tracking
    - Safe execution with error isolation
    - Basic health checking
    """

    def __init__(self):
        self._metadata: Optional[PluginMetadata] = None
        self._config: Dict[str, Any] = {}
        self._initialized = False

    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata

        Subclasses should set self._metadata in their __init__
        """
        if self._metadata is None:
            raise NotImplementedError(
                f"Plugin {self.__class__.__name__} must define metadata"
            )
        return self._metadata

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Default initialization

        Stores config and marks plugin as initialized.
        Subclasses can override for custom initialization.
        """
        try:
            self._config = config
            self._initialized = True
            print(f"[Plugin:{self.get_metadata().plugin_id}] Initialized")
            return True
        except Exception as e:
            print(f"[Plugin:{self.get_metadata().plugin_id}] Init failed: {e}")
            return False

    def health_check(self) -> Tuple[bool, Optional[str]]:
        """
        Default health check

        Checks if plugin is initialized.
        Subclasses can override for custom health checks.
        """
        if not self._initialized:
            return False, "Not initialized"
        return True, None

    def cleanup(self):
        """
        Default cleanup

        Marks plugin as not initialized.
        Subclasses can override for custom cleanup.
        """
        self._initialized = False
        print(f"[Plugin:{self.get_metadata().plugin_id}] Cleaned up")

    def safe_execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, Optional[Exception]]:
        """
        Execute function with error isolation

        This ensures that if a plugin fails, it doesn't crash
        the entire system. The error is caught and returned.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tuple of (result, exception)
            - result: Function result if successful, None if failed
            - exception: Exception if failed, None if successful
        """
        try:
            result = func(*args, **kwargs)
            return result, None
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"[Plugin:{self.get_metadata().plugin_id}] Error: {error_trace}")
            return None, e


class IFeatureExtractorPlugin(BasePlugin):
    """
    Interface for feature extractor plugins

    Feature extractors analyze video/audio/transcript and
    extract structured features for classification.

    Example extractors:
    - Transcript → speech density, keywords
    - Visual → face movement, scene changes
    - Audio → music detection, audio classification
    """

    @abstractmethod
    def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract features from video

        Args:
            video_path: Path to video file
            clip_info: Clip metadata including transcript

        Returns:
            Dictionary of extracted features
        """
        pass


class IClassifierPlugin(BasePlugin):
    """
    Interface for classifier plugins

    Classifiers analyze features and determine video category
    (e.g., talking_head, cooking, gaming, etc.)

    Each classifier specializes in detecting one category.
    """

    @abstractmethod
    def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify video based on features

        Args:
            features: Dictionary of all extracted features

        Returns:
            Dictionary with classification result if confident enough:
            {
                'category': str,
                'confidence': float,
                'reasoning': dict,
                'metadata': dict
            }
            Or None if can't classify with confidence
        """
        pass


class IProcessingStrategyPlugin(BasePlugin):
    """
    Interface for processing strategy plugins

    Processing strategies define how to process a video
    based on its category.

    Example strategies:
    - Talking head → smart framing + karaoke subs
    - Cooking → center crop + simple subs
    - Sports → center crop + no subs
    """

    @abstractmethod
    def get_processing_config(self) -> Dict[str, Any]:
        """
        Return processing configuration for this category

        Returns:
            Dictionary with processing parameters:
            {
                'smart_framing': bool,
                'subtitle_mode': str,  # 'karaoke', 'simple', 'none'
                'aspect_ratios': list,
                'crop_strategy': str,
                'stabilization': bool,
                'clip_length_range': tuple,
                'additional_config': dict
            }
        """
        pass


class CircuitBreakerPlugin(BasePlugin):
    """
    Plugin wrapper with circuit breaker pattern

    Prevents repeatedly calling a failing plugin.
    After N failures, the plugin is "opened" and skipped
    until a timeout period passes.

    This is optional - plugins can inherit from this for
    automatic circuit breaker functionality.
    """

    def __init__(self):
        super().__init__()
        self.failure_count = 0
        self.failure_threshold = 5
        self.circuit_open = False
        self.last_failure_time = None
        self.reset_timeout = 60  # seconds

    def execute_with_circuit_breaker(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """
        Execute function with circuit breaker

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result or None if circuit is open
        """
        # Check if circuit should close
        if self.circuit_open:
            if time.time() - self.last_failure_time > self.reset_timeout:
                print(
                    f"[CircuitBreaker] Attempting to close circuit for "
                    f"{self.get_metadata().plugin_id}"
                )
                self.circuit_open = False
                self.failure_count = 0
            else:
                print(
                    f"[CircuitBreaker] Circuit open, skipping "
                    f"{self.get_metadata().plugin_id}"
                )
                return None  # Skip execution

        try:
            result = func(*args, **kwargs)
            self.failure_count = 0  # Reset on success
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.circuit_open = True
                print(
                    f"[CircuitBreaker] Opening circuit for "
                    f"{self.get_metadata().plugin_id} "
                    f"after {self.failure_count} failures"
                )

            raise  # Re-raise exception
