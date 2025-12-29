 ---
  Plugin-Based Video Classification System

  🎯 Design Philosophy

  ┌─────────────────────────────────────────────────────────────────┐
  │                      MICROKERNEL CORE                            │
  │  (Minimal, stable, never changes)                                │
  │  - Plugin loader                                                 │
  │  - Registry                                                      │
  │  - Orchestrator                                                  │
  └─────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────┐
  │                     PLUGIN ECOSYSTEM                             │
  │  (Everything is a plugin - add/remove/update independently)      │
  │                                                                  │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
  │  │  Extractor   │  │  Classifier  │  │  Strategy    │         │
  │  │   Plugins    │  │   Plugins    │  │   Plugins    │         │
  │  └──────────────┘  └──────────────┘  └──────────────┘         │
  │                                                                  │
  │  Each plugin:                                                    │
  │  - Self-contained                                                │
  │  - Auto-discovered                                               │
  │  - Isolated failures                                             │
  │  - Hot-reloadable                                                │
  └─────────────────────────────────────────────────────────────────┘

  Key Principles:
  - ✅ Add plugin = drop file in folder
  - ✅ Remove plugin = delete file
  - ✅ Plugin crashes = system continues
  - ✅ No core code changes needed
  - ✅ Configuration-driven
  - ✅ Zero coupling between plugins

  ---
  🏗️ Complete Architecture

  1. Plugin Metadata & Discovery

  # ============================================================================
  # FILE: classification/core/plugin_metadata.py
  # ============================================================================

  from dataclasses import dataclass, field
  from typing import Dict, List, Optional, Any, Callable
  from enum import Enum
  import semver

  class PluginType(Enum):
      """Types of plugins supported"""
      FEATURE_EXTRACTOR = "feature_extractor"
      CLASSIFIER = "classifier"
      PROCESSING_STRATEGY = "processing_strategy"
      DETECTOR = "detector"  # Low-level detectors (face, object, etc.)


  class PluginStatus(Enum):
      """Plugin health status"""
      ACTIVE = "active"
      INACTIVE = "inactive"
      ERROR = "error"
      DISABLED = "disabled"


  @dataclass
  class PluginDependency:
      """Plugin dependency specification"""
      name: str
      version_constraint: str  # e.g., ">=1.0.0,<2.0.0"
      optional: bool = False


  @dataclass
  class PluginMetadata:
      """
      Metadata for a plugin - defines what the plugin does
      This is what makes plugins self-describing
      """
      # Identity
      plugin_id: str  # Unique identifier (e.g., "talking_head_classifier_v1")
      plugin_type: PluginType
      name: str  # Human-readable name
      version: str  # Semantic version (e.g., "1.2.0")
      author: str
      description: str

      # Technical specs
      priority: int = 50  # Lower = runs earlier (0-100)
      enabled: bool = True
      cost_estimate_ms: float = 0.0  # Estimated computation cost

      # Dependencies
      dependencies: List[PluginDependency] = field(default_factory=list)
      requires_features: List[str] = field(default_factory=list)  # e.g., ["transcript", "visual"]
      provides_features: List[str] = field(default_factory=list)  # e.g., ["transcript"]

      # Configuration
      config_schema: Optional[Dict[str, Any]] = None  # JSON schema for config
      default_config: Dict[str, Any] = field(default_factory=dict)

      # Runtime info
      status: PluginStatus = PluginStatus.INACTIVE
      error_message: Optional[str] = None
      last_health_check: Optional[float] = None
      success_count: int = 0
      failure_count: int = 0

      # Categorization (for classifiers)
      target_category: Optional[str] = None  # e.g., "talking_head"
      confidence_threshold: float = 0.7

      # Tags for filtering
      tags: List[str] = field(default_factory=list)  # e.g., ["cheap", "reliable", "beta"]


  # ============================================================================
  # FILE: classification/core/plugin_interface.py
  # ============================================================================

  from abc import ABC, abstractmethod
  import traceback

  class IPlugin(ABC):
      """
      Base interface for ALL plugins
      This is the contract that makes something a "plugin"
      """

      @abstractmethod
      def get_metadata(self) -> PluginMetadata:
          """Return plugin metadata"""
          pass

      @abstractmethod
      def initialize(self, config: Dict[str, Any]) -> bool:
          """
          Initialize plugin with configuration
          Returns: True if successful, False otherwise
          """
          pass

      @abstractmethod
      def health_check(self) -> tuple[bool, Optional[str]]:
          """
          Check if plugin is healthy
          Returns: (is_healthy, error_message)
          """
          pass

      @abstractmethod
      def cleanup(self):
          """Clean up resources (called on shutdown)"""
          pass


  class BasePlugin(IPlugin):
      """
      Base implementation with common functionality
      Plugins can inherit from this for convenience
      """

      def __init__(self):
          self._metadata: Optional[PluginMetadata] = None
          self._config: Dict[str, Any] = {}
          self._initialized = False

      def get_metadata(self) -> PluginMetadata:
          """Default metadata - should be overridden"""
          if self._metadata is None:
              raise NotImplementedError("Plugin must define metadata")
          return self._metadata

      def initialize(self, config: Dict[str, Any]) -> bool:
          """Default initialization"""
          try:
              self._config = config
              self._initialized = True
              print(f"[Plugin:{self.get_metadata().plugin_id}] Initialized")
              return True
          except Exception as e:
              print(f"[Plugin:{self.get_metadata().plugin_id}] Init failed: {e}")
              return False

      def health_check(self) -> tuple[bool, Optional[str]]:
          """Default health check"""
          if not self._initialized:
              return False, "Not initialized"
          return True, None

      def cleanup(self):
          """Default cleanup"""
          self._initialized = False
          print(f"[Plugin:{self.get_metadata().plugin_id}] Cleaned up")

      def safe_execute(self, func: Callable, *args, **kwargs) -> tuple[Any, Optional[Exception]]:
          """
          Execute function with error isolation
          Returns: (result, exception)
          """
          try:
              result = func(*args, **kwargs)
              return result, None
          except Exception as e:
              error_trace = traceback.format_exc()
              print(f"[Plugin:{self.get_metadata().plugin_id}] Error: {error_trace}")
              return None, e


  # ============================================================================
  # Specific Plugin Interfaces
  # ============================================================================

  class IFeatureExtractorPlugin(BasePlugin):
      """Interface for feature extractor plugins"""

      @abstractmethod
      def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Any:
          """Extract features from video"""
          pass


  class IClassifierPlugin(BasePlugin):
      """Interface for classifier plugins"""

      @abstractmethod
      def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
          """
          Classify video based on features
          Returns: {
              'category': str,
              'confidence': float,
              'reasoning': dict,
              'metadata': dict
          } or None if can't classify
          """
          pass


  class IProcessingStrategyPlugin(BasePlugin):
      """Interface for processing strategy plugins"""

      @abstractmethod
      def get_processing_config(self) -> Dict[str, Any]:
          """
          Return processing configuration
          Returns: {
              'smart_framing': bool,
              'subtitle_mode': str,
              'aspect_ratios': list,
              'crop_strategy': str,
              'stabilization': bool,
              'clip_length_range': tuple,
              'additional_config': dict
          }
          """
          pass


  class IDetectorPlugin(BasePlugin):
      """Interface for low-level detector plugins (face, object, etc.)"""

      @abstractmethod
      def detect(self, frames: List[Any]) -> Dict[str, Any]:
          """
          Detect features in frames
          Returns detector-specific results
          """
          pass

  ---
  2. Plugin Registry & Manager

  # ============================================================================
  # FILE: classification/core/plugin_registry.py
  # ============================================================================

  from typing import Dict, List, Type, Optional
  import threading

  class PluginRegistry:
      """
      Thread-safe registry for all plugins
      This is the central catalog of available plugins
      """

      def __init__(self):
          self._plugins: Dict[str, IPlugin] = {}  # plugin_id -> plugin instance
          self._plugins_by_type: Dict[PluginType, List[str]] = {
              ptype: [] for ptype in PluginType
          }
          self._lock = threading.RLock()

      def register(self, plugin: IPlugin) -> bool:
          """
          Register a plugin
          Returns: True if successful, False if duplicate
          """
          with self._lock:
              metadata = plugin.get_metadata()
              plugin_id = metadata.plugin_id

              if plugin_id in self._plugins:
                  print(f"[Registry] Plugin '{plugin_id}' already registered, skipping")
                  return False

              self._plugins[plugin_id] = plugin
              self._plugins_by_type[metadata.plugin_type].append(plugin_id)

              print(f"[Registry] Registered plugin: {plugin_id} (type: {metadata.plugin_type.value})")
              return True

      def unregister(self, plugin_id: str) -> bool:
          """Unregister a plugin"""
          with self._lock:
              if plugin_id not in self._plugins:
                  return False

              plugin = self._plugins[plugin_id]
              metadata = plugin.get_metadata()

              # Cleanup
              plugin.cleanup()

              # Remove from registry
              del self._plugins[plugin_id]
              self._plugins_by_type[metadata.plugin_type].remove(plugin_id)

              print(f"[Registry] Unregistered plugin: {plugin_id}")
              return True

      def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
          """Get plugin by ID"""
          with self._lock:
              return self._plugins.get(plugin_id)

      def get_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
          """Get all plugins of a specific type"""
          with self._lock:
              plugin_ids = self._plugins_by_type.get(plugin_type, [])
              return [self._plugins[pid] for pid in plugin_ids if pid in self._plugins]

      def get_active_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
          """Get all active plugins of a specific type"""
          plugins = self.get_plugins_by_type(plugin_type)
          return [
              p for p in plugins
              if p.get_metadata().status == PluginStatus.ACTIVE
              and p.get_metadata().enabled
          ]

      def get_all_plugins(self) -> List[IPlugin]:
          """Get all registered plugins"""
          with self._lock:
              return list(self._plugins.values())

      def update_plugin_status(
          self,
          plugin_id: str,
          status: PluginStatus,
          error_message: Optional[str] = None
      ):
          """Update plugin status"""
          with self._lock:
              plugin = self._plugins.get(plugin_id)
              if plugin:
                  metadata = plugin.get_metadata()
                  metadata.status = status
                  metadata.error_message = error_message
                  metadata.last_health_check = time.time()


  # ============================================================================
  # FILE: classification/core/plugin_loader.py
  # ============================================================================

  import os
  import importlib.util
  import inspect
  from pathlib import Path

  class PluginLoader:
      """
      Auto-discovers and loads plugins from directories
      This is what makes it "plug and play"
      """

      def __init__(self, registry: PluginRegistry):
          self.registry = registry
          self.plugin_dirs: List[Path] = []

      def add_plugin_directory(self, directory: str):
          """Add a directory to search for plugins"""
          path = Path(directory)
          if path.exists() and path.is_dir():
              self.plugin_dirs.append(path)
              print(f"[PluginLoader] Added plugin directory: {path}")
          else:
              print(f"[PluginLoader] Warning: Directory not found: {path}")

      def discover_and_load_all(self) -> Dict[str, bool]:
          """
          Discover and load all plugins from registered directories
          Returns: Dict of plugin_id -> success/failure
          """
          results = {}

          for plugin_dir in self.plugin_dirs:
              print(f"[PluginLoader] Scanning directory: {plugin_dir}")

              # Find all Python files
              for py_file in plugin_dir.glob("**/*.py"):
                  if py_file.name.startswith("_"):
                      continue  # Skip private modules

                  try:
                      plugins = self._load_plugins_from_file(py_file)
                      for plugin in plugins:
                          metadata = plugin.get_metadata()
                          success = self.registry.register(plugin)
                          results[metadata.plugin_id] = success
                  except Exception as e:
                      print(f"[PluginLoader] Failed to load {py_file}: {e}")
                      results[str(py_file)] = False

          print(f"[PluginLoader] Loaded {sum(results.values())}/{len(results)} plugins")
          return results

      def _load_plugins_from_file(self, filepath: Path) -> List[IPlugin]:
          """Load all plugin classes from a Python file"""
          plugins = []

          # Load module dynamically
          spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
          if spec is None or spec.loader is None:
              return plugins

          module = importlib.util.module_from_spec(spec)
          spec.loader.exec_module(module)

          # Find all plugin classes in module
          for name, obj in inspect.getmembers(module):
              if (inspect.isclass(obj) and
                  issubclass(obj, IPlugin) and
                  obj not in [IPlugin, BasePlugin, IFeatureExtractorPlugin,
                             IClassifierPlugin, IProcessingStrategyPlugin, IDetectorPlugin]):

                  try:
                      # Instantiate plugin
                      plugin_instance = obj()
                      plugins.append(plugin_instance)
                      print(f"[PluginLoader] Found plugin: {plugin_instance.get_metadata().plugin_id}")
                  except Exception as e:
                      print(f"[PluginLoader] Failed to instantiate {name}: {e}")

          return plugins

      def reload_plugin(self, plugin_id: str) -> bool:
          """
          Hot-reload a plugin (unregister and reload)
          Useful for development
          """
          plugin = self.registry.get_plugin(plugin_id)
          if not plugin:
              return False

          # Find source file
          module = inspect.getmodule(plugin.__class__)
          if not module or not hasattr(module, '__file__'):
              return False

          filepath = Path(module.__file__)

          # Unregister old plugin
          self.registry.unregister(plugin_id)

          # Reload from file
          try:
              plugins = self._load_plugins_from_file(filepath)
              for new_plugin in plugins:
                  if new_plugin.get_metadata().plugin_id == plugin_id:
                      self.registry.register(new_plugin)
                      print(f"[PluginLoader] Reloaded plugin: {plugin_id}")
                      return True
          except Exception as e:
              print(f"[PluginLoader] Failed to reload {plugin_id}: {e}")

          return False


  # ============================================================================
  # FILE: classification/core/plugin_manager.py
  # ============================================================================

  import time

  class PluginManager:
      """
      High-level plugin management
      Handles initialization, health checks, and lifecycle
      """

      def __init__(self, registry: PluginRegistry, loader: PluginLoader):
          self.registry = registry
          self.loader = loader
          self.config: Dict[str, Dict[str, Any]] = {}  # plugin_id -> config

      def load_config(self, config_path: str):
          """Load plugin configuration from JSON/YAML"""
          import json
          with open(config_path, 'r') as f:
              self.config = json.load(f)
          print(f"[PluginManager] Loaded config for {len(self.config)} plugins")

      def initialize_all_plugins(self) -> Dict[str, bool]:
          """Initialize all registered plugins"""
          results = {}

          for plugin in self.registry.get_all_plugins():
              metadata = plugin.get_metadata()
              plugin_id = metadata.plugin_id

              # Get config for this plugin
              plugin_config = self.config.get(plugin_id, metadata.default_config)

              # Check if disabled in config
              if not plugin_config.get('enabled', metadata.enabled):
                  print(f"[PluginManager] Plugin {plugin_id} is disabled, skipping")
                  self.registry.update_plugin_status(plugin_id, PluginStatus.DISABLED)
                  results[plugin_id] = False
                  continue

              # Initialize
              success = plugin.initialize(plugin_config)

              if success:
                  self.registry.update_plugin_status(plugin_id, PluginStatus.ACTIVE)
                  results[plugin_id] = True
              else:
                  self.registry.update_plugin_status(
                      plugin_id,
                      PluginStatus.ERROR,
                      "Initialization failed"
                  )
                  results[plugin_id] = False

          active_count = sum(results.values())
          print(f"[PluginManager] Initialized {active_count}/{len(results)} plugins")
          return results

      def run_health_checks(self) -> Dict[str, tuple[bool, Optional[str]]]:
          """Run health checks on all plugins"""
          results = {}

          for plugin in self.registry.get_all_plugins():
              metadata = plugin.get_metadata()
              plugin_id = metadata.plugin_id

              if metadata.status == PluginStatus.DISABLED:
                  continue

              is_healthy, error_msg = plugin.health_check()
              results[plugin_id] = (is_healthy, error_msg)

              if is_healthy:
                  self.registry.update_plugin_status(plugin_id, PluginStatus.ACTIVE)
              else:
                  self.registry.update_plugin_status(
                      plugin_id,
                      PluginStatus.ERROR,
                      error_msg
                  )
                  print(f"[PluginManager] Plugin {plugin_id} unhealthy: {error_msg}")

          return results

      def get_plugin_stats(self) -> Dict[str, Any]:
          """Get statistics about all plugins"""
          plugins = self.registry.get_all_plugins()

          stats = {
              'total': len(plugins),
              'by_type': {},
              'by_status': {},
              'active': 0,
              'error': 0
          }

          for plugin in plugins:
              metadata = plugin.get_metadata()

              # Count by type
              ptype = metadata.plugin_type.value
              stats['by_type'][ptype] = stats['by_type'].get(ptype, 0) + 1

              # Count by status
              status = metadata.status.value
              stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

              if metadata.status == PluginStatus.ACTIVE:
                  stats['active'] += 1
              elif metadata.status == PluginStatus.ERROR:
                  stats['error'] += 1

          return stats

      def shutdown_all_plugins(self):
          """Clean shutdown of all plugins"""
          print("[PluginManager] Shutting down all plugins...")
          for plugin in self.registry.get_all_plugins():
              try:
                  plugin.cleanup()
              except Exception as e:
                  print(f"[PluginManager] Error cleaning up {plugin.get_metadata().plugin_id}: {e}")

  ---
  3. Plugin Orchestrator (The Brain)

  # ============================================================================
  # FILE: classification/core/orchestrator.py
  # ============================================================================

  class PluginOrchestrator:
      """
      Orchestrates plugin execution with error isolation
      This is the "brain" that coordinates everything
      """

      def __init__(self, registry: PluginRegistry):
          self.registry = registry
          self.execution_history: List[Dict[str, Any]] = []

      def extract_features(
          self,
          video_path: str,
          clip_info: Dict[str, Any],
          required_features: Optional[List[str]] = None,
          max_cost_ms: float = 1000.0
      ) -> Dict[str, Any]:
          """
          Extract features using available extractor plugins
          With error isolation - if one fails, others continue
          """
          features = {}
          total_cost = 0.0

          # Get all active extractor plugins
          extractors = self.registry.get_active_plugins_by_type(
              PluginType.FEATURE_EXTRACTOR
          )

          # Sort by priority (cost)
          extractors.sort(key=lambda p: p.get_metadata().cost_estimate_ms)

          for extractor in extractors:
              metadata = extractor.get_metadata()
              plugin_id = metadata.plugin_id

              # Check if we need this feature
              provided_features = metadata.provides_features
              if required_features and not any(f in required_features for f in provided_features):
                  continue  # Skip if not needed

              # Check cost budget
              if total_cost + metadata.cost_estimate_ms > max_cost_ms:
                  print(f"[Orchestrator] Skipping {plugin_id} - exceeds budget")
                  continue

              # Execute with error isolation
              start_time = time.time()
              result, error = extractor.safe_execute(
                  extractor.extract,
                  video_path,
                  clip_info
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
                  print(f"[Orchestrator] Extractor {plugin_id} failed: {error}")
                  continue

              # Success - store features
              metadata.success_count += 1
              total_cost += elapsed_ms

              for feature_name in provided_features:
                  features[feature_name] = result

              print(f"[Orchestrator] Extracted {provided_features} using {plugin_id} ({elapsed_ms:.1f}ms)")

          return features

      def classify(
          self,
          features: Dict[str, Any],
          max_confidence: float = 0.95
      ) -> Optional[Dict[str, Any]]:
          """
          Classify video using available classifier plugins
          Try in priority order, stop when confident enough
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
              if not all(f in features for f in required_features):
                  print(f"[Orchestrator] Skipping {plugin_id} - missing features: {required_features}")
                  continue

              # Execute with error isolation
              start_time = time.time()
              result, error = classifier.safe_execute(
                  classifier.classify,
                  features
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
                  print(f"[Orchestrator] Classifier {plugin_id} failed: {error}")
                  continue

              # Check result
              if result is None:
                  continue  # Classifier couldn't classify

              metadata.success_count += 1
              confidence = result.get('confidence', 0.0)

              print(f"[Orchestrator] {plugin_id} classified as '{result.get('category')}' "
                    f"with confidence {confidence:.2f} ({elapsed_ms:.1f}ms)")

              # Track best result
              if confidence > best_confidence:
                  best_result = result
                  best_confidence = confidence

              # Stop if confident enough
              if confidence >= max_confidence:
                  print(f"[Orchestrator] High confidence reached, stopping classification")
                  break

          return best_result

      def get_processing_strategy(
          self,
          category: str
      ) -> Optional[Dict[str, Any]]:
          """Get processing strategy for a category"""
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
                      print(f"[Orchestrator] Strategy {metadata.plugin_id} failed: {error}")
                      continue
                  return result

          # Fallback to default
          print(f"[Orchestrator] No strategy found for '{category}', using default")
          return self._get_default_strategy()

      def _get_default_strategy(self) -> Dict[str, Any]:
          """Safe default strategy"""
          return {
              'smart_framing': False,
              'subtitle_mode': 'simple',
              'aspect_ratios': ['9:16'],
              'crop_strategy': 'center',
              'stabilization': False,
              'clip_length_range': (20.0, 45.0),
              'additional_config': {}
          }

  ---
  4. Example Plugins (Drop-in Files)

  # ============================================================================
  # FILE: plugins/extractors/transcript_extractor.py
  # Drop this file in plugins/extractors/ - it auto-loads!
  # ============================================================================

  from classification.core.plugin_interface import IFeatureExtractorPlugin
  from classification.core.plugin_metadata import PluginMetadata, PluginType, PluginStatus

  class TranscriptExtractorPlugin(IFeatureExtractorPlugin):
      """
      Extracts features from transcript
      This is a complete, self-contained plugin
      """

      def __init__(self):
          super().__init__()
          self._metadata = PluginMetadata(
              plugin_id="transcript_extractor_v1",
              plugin_type=PluginType.FEATURE_EXTRACTOR,
              name="Transcript Feature Extractor",
              version="1.0.0",
              author="Your Team",
              description="Extracts speech density, patterns, and keywords from transcript",
              priority=1,  # High priority (cheap!)
              cost_estimate_ms=0.0,  # Free!
              provides_features=["transcript"],
              tags=["cheap", "reliable", "core"]
          )

      def extract(self, video_path: str, clip_info: Dict[str, Any]) -> Dict[str, Any]:
          """Extract transcript features"""
          clip = clip_info.get('clip', {})
          segments = clip.get('segments', [])
          duration = clip.get('duration', 0)

          # Calculate speech density
          speech_time = sum(
              word['end'] - word['start']
              for seg in segments
              for word in seg.get('words', [])
          )
          speech_density = speech_time / duration if duration > 0 else 0

          # Detect speech pattern
          speech_pattern = self._detect_pattern(segments, duration)

          # Extract keywords
          text = clip.get('text', '').lower()
          keywords = self._extract_keywords(text)

          return {
              'speech_density': speech_density,
              'speech_pattern': speech_pattern,
              'keywords': keywords,
              'word_count': len(text.split()),
              'total_speaking_time': speech_time,
              'total_silence_time': duration - speech_time
          }

      def _detect_pattern(self, segments, duration):
          """Detect speech pattern"""
          if not segments:
              return 'unknown'

          # Calculate pauses
          pauses = []
          for i in range(len(segments) - 1):
              pause = segments[i+1]['start'] - segments[i]['end']
              if pause > 0:
                  pauses.append(pause)

          if not pauses:
              return 'continuous'

          avg_pause = sum(pauses) / len(pauses)

          if avg_pause < 0.5:
              return 'continuous'
          elif avg_pause < 3.0:
              return 'bursts'
          else:
              return 'sparse'

      def _extract_keywords(self, text):
          """Extract category keywords"""
          keyword_sets = {
              'gaming': ['mortal', 'gg', 'clutch', 'lets go', 'nice'],
              'cooking': ['add', 'mix', 'cook', 'ingredients', 'recipe'],
              'tutorial': ['first', 'next', 'step', 'how to', 'show you'],
              'fitness': ['reps', 'sets', 'exercise', 'form', 'squeeze'],
              'reaction': ['oh my god', 'what', 'no way', 'bro']
          }

          found = []
          for category, keywords in keyword_sets.items():
              if any(kw in text for kw in keywords):
                  found.append(category)

          return found


  # ============================================================================
  # FILE: plugins/classifiers/talking_head_classifier.py
  # Drop this file in plugins/classifiers/ - it auto-loads!
  # ============================================================================

  from classification.core.plugin_interface import IClassifierPlugin
  from classification.core.plugin_metadata import PluginMetadata, PluginType

  class TalkingHeadClassifierPlugin(IClassifierPlugin):
      """
      Classifies talking head / podcast / interview videos
      Complete self-contained plugin
      """

      def __init__(self):
          super().__init__()
          self._metadata = PluginMetadata(
              plugin_id="talking_head_classifier_v1",
              plugin_type=PluginType.CLASSIFIER,
              name="Talking Head Classifier",
              version="1.0.0",
              author="Your Team",
              description="Detects talking head, podcast, and interview content",
              priority=10,  # High priority (uses cheap features)
              requires_features=["transcript", "visual"],
              target_category="talking_head",
              confidence_threshold=0.7,
              tags=["reliable", "fast", "core"]
          )

      def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
          """Classify based on speech + minimal movement"""
          transcript = features.get('transcript')
          visual = features.get('visual')

          if not transcript or not visual:
              return None

          score = 0.0
          reasoning = {}

          # High speech density
          if transcript['speech_density'] > 0.7:
              score += 0.3
              reasoning['speech_density'] = f"high ({transcript['speech_density']:.2f})"

          # Minimal face movement
          if visual.get('face_movement_avg', 999) < 30:
              score += 0.3
              reasoning['face_movement'] = f"minimal ({visual['face_movement_avg']:.1f}px)"

          # Stationary camera
          if visual.get('camera_motion') == 'minimal':
              score += 0.2
              reasoning['camera_motion'] = 'stationary'

          # 1-2 faces
          face_count = visual.get('face_count_avg', 0)
          if 0.8 <= face_count <= 2.2:
              score += 0.2
              reasoning['face_count'] = f'{face_count:.1f}'

          if score >= self._metadata.confidence_threshold:
              return {
                  'category': 'talking_head',
                  'confidence': score,
                  'reasoning': reasoning,
                  'metadata': {
                      'classifier': self._metadata.plugin_id,
                      'version': self._metadata.version
                  }
              }

          return None


  # ============================================================================
  # FILE: plugins/classifiers/cooking_classifier.py
  # Drop this file in plugins/classifiers/ - it auto-loads!
  # This one requires object detection (expensive feature)
  # ============================================================================

  class CookingClassifierPlugin(IClassifierPlugin):
      """Classifies cooking videos - requires object detection"""

      def __init__(self):
          super().__init__()
          self._metadata = PluginMetadata(
              plugin_id="cooking_classifier_v1",
              plugin_type=PluginType.CLASSIFIER,
              name="Cooking Classifier",
              version="1.0.0",
              author="Your Team",
              description="Detects cooking and recipe content",
              priority=50,  # Lower priority (uses expensive features)
              requires_features=["objects", "visual"],  # Needs object detection!
              target_category="cooking",
              confidence_threshold=0.6,
              tags=["expensive", "accurate"]
          )

      def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
          """Classify based on kitchen objects"""
          objects = features.get('objects')
          visual = features.get('visual')

          if not objects or not visual:
              return None

          score = 0.0
          reasoning = {}

          # Kitchen objects detected
          kitchen_objects = ['knife', 'pot', 'pan', 'bowl', 'cutting_board']
          detected = objects.get('detected_objects', {})
          kitchen_count = sum(1 for obj in kitchen_objects if obj in detected)

          if kitchen_count >= 2:
              score += 0.4
              reasoning['kitchen_objects'] = f'{kitchen_count} detected'

          # Kitchen scene
          if objects.get('scene_type') == 'kitchen':
              score += 0.3
              reasoning['scene'] = 'kitchen'

          # Low face visibility
          if visual.get('face_count_avg', 1.0) < 0.5:
              score += 0.2
              reasoning['face_visibility'] = 'low'

          # Check keywords if available
          transcript = features.get('transcript')
          if transcript and 'cooking' in transcript.get('keywords', []):
              score += 0.1
              reasoning['keywords'] = 'cooking'

          if score >= self._metadata.confidence_threshold:
              return {
                  'category': 'cooking',
                  'confidence': score,
                  'reasoning': reasoning,
                  'metadata': {
                      'classifier': self._metadata.plugin_id,
                      'version': self._metadata.version,
                      'objects_detected': list(detected.keys())
                  }
              }

          return None


  # ============================================================================
  # FILE: plugins/strategies/talking_head_strategy.py
  # Drop this file in plugins/strategies/ - it auto-loads!
  # ============================================================================

  from classification.core.plugin_interface import IProcessingStrategyPlugin
  from classification.core.plugin_metadata import PluginMetadata, PluginType

  class TalkingHeadStrategyPlugin(IProcessingStrategyPlugin):
      """Processing strategy for talking head videos"""

      def __init__(self):
          super().__init__()
          self._metadata = PluginMetadata(
              plugin_id="talking_head_strategy_v1",
              plugin_type=PluginType.PROCESSING_STRATEGY,
              name="Talking Head Processing Strategy",
              version="1.0.0",
              author="Your Team",
              description="Optimal processing for talking head content",
              target_category="talking_head",
              tags=["core"]
          )

      def get_processing_config(self) -> Dict[str, Any]:
          """Return processing configuration"""
          return {
              'smart_framing': True,
              'subtitle_mode': 'karaoke',
              'aspect_ratios': ['9:16'],
              'crop_strategy': 'smart',
              'stabilization': False,
              'clip_length_range': (30.0, 60.0),
              'additional_config': {
                  'dead_zone_radius': 150,
                  'smoothing_sigma': 0.5
              }
          }


  # ============================================================================
  # FILE: plugins/strategies/cooking_strategy.py
  # ============================================================================

  class CookingStrategyPlugin(IProcessingStrategyPlugin):
      """Processing strategy for cooking videos"""

      def __init__(self):
          super().__init__()
          self._metadata = PluginMetadata(
              plugin_id="cooking_strategy_v1",
              plugin_type=PluginType.PROCESSING_STRATEGY,
              name="Cooking Processing Strategy",
              version="1.0.0",
              author="Your Team",
              description="Optimal processing for cooking content",
              target_category="cooking",
              tags=["core"]
          )

      def get_processing_config(self) -> Dict[str, Any]:
          """Return processing configuration"""
          return {
              'smart_framing': False,  # No face framing
              'subtitle_mode': 'simple',
              'aspect_ratios': ['1:1', '9:16'],
              'crop_strategy': 'hands_focus',
              'stabilization': False,
              'clip_length_range': (15.0, 30.0),
              'additional_config': {
                  'focus_lower_half': True
              }
          }

  ---
  5. Configuration System

  // ============================================================================
  // FILE: config/plugins.json
  // Configuration for all plugins
  // ============================================================================

  {
    "transcript_extractor_v1": {
      "enabled": true,
      "priority": 1
    },
    "visual_extractor_v1": {
      "enabled": true,
      "priority": 10,
      "sample_rate": 10
    },
    "object_extractor_v1": {
      "enabled": false,  // Disabled by default (expensive!)
      "priority": 50,
      "sample_rate": 30,
      "detector_type": "yolo"
    },
    "talking_head_classifier_v1": {
      "enabled": true,
      "confidence_threshold": 0.7
    },
    "cooking_classifier_v1": {
      "enabled": true,
      "confidence_threshold": 0.6
    },
    "talking_head_strategy_v1": {
      "enabled": true
    },
    "cooking_strategy_v1": {
      "enabled": true
    }
  }

  ---
  6. Main Service (Ties Everything Together)

  # ============================================================================
  # FILE: classification/service.py
  # The main service that uses the plugin system
  # ============================================================================

  class VideoClassificationService:
      """
      Main service using plugin architecture
      This is the only code that needs to know about the plugin system
      """

      def __init__(self, plugin_dirs: List[str], config_path: str):
          """Initialize service with plugin directories"""
          # Create core components
          self.registry = PluginRegistry()
          self.loader = PluginLoader(self.registry)
          self.manager = PluginManager(self.registry, self.loader)
          self.orchestrator = PluginOrchestrator(self.registry)

          # Add plugin directories
          for directory in plugin_dirs:
              self.loader.add_plugin_directory(directory)

          # Load configuration
          if os.path.exists(config_path):
              self.manager.load_config(config_path)

          # Discover and load all plugins
          print("[Service] Discovering plugins...")
          self.loader.discover_and_load_all()

          # Initialize all plugins
          print("[Service] Initializing plugins...")
          self.manager.initialize_all_plugins()

          # Run health checks
          print("[Service] Running health checks...")
          self.manager.run_health_checks()

          # Print stats
          stats = self.manager.get_plugin_stats()
          print(f"[Service] Ready! {stats['active']}/{stats['total']} plugins active")
          print(f"[Service] Plugin breakdown: {stats['by_type']}")

      def classify_and_get_strategy(
          self,
          video_path: str,
          clip_info: Dict[str, Any],
          max_cost_ms: float = 1000.0
      ) -> tuple[Dict[str, Any], Dict[str, Any]]:
          """
          Main entry point: Classify video and get processing strategy

          Returns:
              (classification_result, processing_strategy)
          """
          # Extract features
          print(f"[Service] Extracting features (budget: {max_cost_ms}ms)...")
          features = self.orchestrator.extract_features(
              video_path,
              clip_info,
              max_cost_ms=max_cost_ms
          )

          # Classify
          print(f"[Service] Classifying video...")
          classification = self.orchestrator.classify(features)

          if not classification:
              print("[Service] Could not classify video, using default")
              return self._get_default_result(), self.orchestrator._get_default_strategy()

          # Get strategy
          category = classification['category']
          strategy = self.orchestrator.get_processing_strategy(category)

          return classification, strategy

      def _get_default_result(self):
          """Default classification when nothing matches"""
          return {
              'category': 'unknown',
              'confidence': 0.0,
              'reasoning': {'error': 'no_classifier_matched'},
              'metadata': {}
          }

      def reload_plugin(self, plugin_id: str) -> bool:
          """Hot-reload a plugin"""
          return self.loader.reload_plugin(plugin_id)

      def get_plugin_stats(self) -> Dict[str, Any]:
          """Get current plugin statistics"""
          return self.manager.get_plugin_stats()

      def shutdown(self):
          """Clean shutdown"""
          self.manager.shutdown_all_plugins()


  # ============================================================================
  # FILE: lambda_function.py
  # Modified lambda handler
  # ============================================================================

  # Global service instance (Lambda warm start)
  _classification_service = None

  def get_classification_service():
      """Lazy initialization"""
      global _classification_service
      if _classification_service is None:
          plugin_dirs = [
              '/var/task/plugins/extractors',
              '/var/task/plugins/classifiers',
              '/var/task/plugins/strategies'
          ]
          config_path = '/var/task/config/plugins.json'

          _classification_service = VideoClassificationService(
              plugin_dirs=plugin_dirs,
              config_path=config_path
          )
      return _classification_service


  def lambda_handler(event, context):
      """Enhanced lambda handler with plugin-based classification"""

      # ... download video ...

      # Classify using plugin system
      service = get_classification_service()
      classification, strategy = service.classify_and_get_strategy(
          video_path=local_video_path,
          clip_info=event,
          max_cost_ms=500.0
      )

      print(f"[Lambda] Category: {classification['category']}")
      print(f"[Lambda] Confidence: {classification['confidence']:.2f}")
      print(f"[Lambda] Strategy: {strategy}")

      # Process with strategy
      # ... apply strategy settings ...

      return {
          'statusCode': 200,
          'classification': classification,
          'processing_strategy': strategy,
          # ... other data ...
      }

  ---
  📁 Complete File Structure

  opus-clip/src/process-clip/
  ├── lambda_function.py                      # Main Lambda handler
  ├── config/
  │   └── plugins.json                        # Plugin configuration
  │
  ├── classification/                         # Core plugin system (never changes!)
  │   ├── __init__.py
  │   └── core/
  │       ├── __init__.py
  │       ├── plugin_metadata.py              # PluginMetadata, PluginType, etc.
  │       ├── plugin_interface.py             # IPlugin, BasePlugin, etc.
  │       ├── plugin_registry.py              # PluginRegistry
  │       ├── plugin_loader.py                # PluginLoader (auto-discovery)
  │       ├── plugin_manager.py               # PluginManager (lifecycle)
  │       ├── orchestrator.py                 # PluginOrchestrator (execution)
  │       └── service.py                      # VideoClassificationService
  │
  ├── plugins/                                # Plugin files (add/remove freely!)
  │   ├── extractors/                         # Feature extractor plugins
  │   │   ├── __init__.py
  │   │   ├── transcript_extractor.py         # ✅ Drop and go!
  │   │   ├── visual_extractor.py             # ✅ Drop and go!
  │   │   ├── audio_extractor.py              # ✅ Drop and go!
  │   │   └── object_extractor.py             # ✅ Drop and go!
  │   │
  │   ├── classifiers/                        # Classifier plugins
  │   │   ├── __init__.py
  │   │   ├── talking_head_classifier.py      # ✅ Drop and go!
  │   │   ├── vlog_classifier.py              # ✅ Drop and go!
  │   │   ├── cooking_classifier.py           # ✅ Drop and go!
  │   │   ├── gaming_classifier.py            # ✅ Drop and go!
  │   │   ├── fitness_classifier.py           # ✅ Drop and go!
  │   │   ├── sports_classifier.py            # ✅ Drop and go!
  │   │   └── ... (add more as needed)
  │   │
  │   └── strategies/                         # Processing strategy plugins
  │       ├── __init__.py
  │       ├── talking_head_strategy.py        # ✅ Drop and go!
  │       ├── vlog_strategy.py                # ✅ Drop and go!
  │       ├── cooking_strategy.py             # ✅ Drop and go!
  │       └── ... (add more as needed)
  │
  ├── processing/                             # Existing processing code
  │   ├── smart_framing.py
  │   ├── karaoke_subtitles.py
  │   └── ...
  │
  └── tests/
      ├── test_plugin_system.py               # Test core system
      ├── test_extractors/                    # Test each extractor
      ├── test_classifiers/                   # Test each classifier
      └── test_strategies/                    # Test each strategy

  ---
  🚀 Usage Examples

  Adding a New Classifier (Zero Core Changes!)

  # ============================================================================
  # FILE: plugins/classifiers/dance_classifier.py
  # Just drop this file - it auto-loads!
  # ============================================================================

  from classification.core.plugin_interface import IClassifierPlugin
  from classification.core.plugin_metadata import PluginMetadata, PluginType

  class DanceClassifierPlugin(IClassifierPlugin):
      """New dance classifier - just drop and go!"""

      def __init__(self):
          super().__init__()
          self._metadata = PluginMetadata(
              plugin_id="dance_classifier_v1",
              plugin_type=PluginType.CLASSIFIER,
              name="Dance Classifier",
              version="1.0.0",
              author="Me",
              description="Detects dance and choreography",
              priority=40,
              requires_features=["visual", "audio"],
              target_category="dance",
              confidence_threshold=0.65,
              tags=["new", "beta"]
          )

      def classify(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
          visual = features.get('visual')
          audio = features.get('audio')

          if not visual or not audio:
              return None

          score = 0.0
          reasoning = {}

          # High body movement
          if visual.get('full_body_movement', 0) > 150:
              score += 0.4
              reasoning['movement'] = 'high'

          # Music detected
          if audio.get('music_detected'):
              score += 0.3
              reasoning['music'] = 'detected'

          # Low speech
          transcript = features.get('transcript')
          if transcript and transcript['speech_density'] < 0.2:
              score += 0.2
              reasoning['speech'] = 'minimal'

          if score >= 0.65:
              return {
                  'category': 'dance',
                  'confidence': score,
                  'reasoning': reasoning,
                  'metadata': {'classifier': 'dance_classifier_v1'}
              }

          return None

  That's it! Drop the file, restart Lambda (or hot-reload), and it works!

  ---
  Testing a New Plugin Locally

  # test_new_plugin.py

  from classification.service import VideoClassificationService

  # Initialize service
  service = VideoClassificationService(
      plugin_dirs=['./plugins/extractors', './plugins/classifiers', './plugins/strategies'],
      config_path='./config/plugins.json'
  )

  # Check plugin loaded
  stats = service.get_plugin_stats()
  print(f"Loaded {stats['active']} plugins")
  print(f"Classifiers: {stats['by_type']['classifier']}")

  # Test classification
  classification, strategy = service.classify_and_get_strategy(
      video_path='test_video.mp4',
      clip_info={'clip': {...}},
      max_cost_ms=1000.0
  )

  print(f"Category: {classification['category']}")
  print(f"Confidence: {classification['confidence']}")

  ---
  Disabling a Broken Plugin

  // config/plugins.json
  {
    "buggy_classifier_v1": {
      "enabled": false  // <-- Just set to false, no code changes!
    }
  }

  ---
  Hot-Reloading a Plugin (Dev Mode)

  # In Lambda or local dev
  service = get_classification_service()
  service.reload_plugin('dance_classifier_v1')  # Reload without restart!

  ---
  ✨ Key Benefits

  | Feature        | How It Works                                                 |
  |----------------|--------------------------------------------------------------|
  | Add Plugin     | Drop file in plugins/ folder → Auto-discovered → Auto-loaded |
  | Remove Plugin  | Delete file → Plugin gone (no core changes)                  |
  | Plugin Crashes | Error isolated → Other plugins continue → Stats tracked      |
  | Disable Plugin | Set enabled: false in config → Skipped at runtime            |
  | Update Plugin  | Replace file → Hot-reload (or restart)                       |
  | Test Plugin    | Independent unit tests → Mock dependencies                   |
  | Version Plugin | Semantic versioning → Multiple versions can coexist          |
  | Monitor Plugin | Health checks → Success/failure stats → Status tracking      |

  ---
  🎯 What This Achieves

  ✅ Zero coupling - Plugins don't know about each other
  ✅ Fault isolation - One plugin fails, others continue
  ✅ Easy testing - Test each plugin independently
  ✅ Hot reload - Update plugins without full restart
  ✅ Configuration-driven - Enable/disable via config
  ✅ Auto-discovery - Drop file and it loads
  ✅ Cost-aware - Only runs expensive plugins when needed
  ✅ Prioritized execution - Cheap plugins first
  ✅ Graceful degradation - Missing features → skip gracefully
  ✅ Observable - Track success/failure rates per plugin

  ---
  This is a true plugin architecture! Want me to help implement any specific part or create more example plugins?