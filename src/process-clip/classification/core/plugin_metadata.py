"""
Plugin Metadata and Type Definitions
Defines metadata structure for all plugins in the system
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class PluginType(Enum):
    """Types of plugins supported in the system"""
    FEATURE_EXTRACTOR = "feature_extractor"
    CLASSIFIER = "classifier"
    PROCESSING_STRATEGY = "processing_strategy"


class PluginStatus(Enum):
    """Plugin health status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginDependency:
    """Specification for a plugin dependency"""
    name: str
    version_constraint: str  # e.g., ">=1.0.0,<2.0.0"
    optional: bool = False


@dataclass
class PluginMetadata:
    """
    Metadata for a plugin - makes plugins self-describing

    This is what enables plugins to be auto-discovered and loaded
    without modifying core code.
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'plugin_id': self.plugin_id,
            'plugin_type': self.plugin_type.value,
            'name': self.name,
            'version': self.version,
            'author': self.author,
            'description': self.description,
            'priority': self.priority,
            'enabled': self.enabled,
            'cost_estimate_ms': self.cost_estimate_ms,
            'requires_features': self.requires_features,
            'provides_features': self.provides_features,
            'status': self.status.value,
            'error_message': self.error_message,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'target_category': self.target_category,
            'confidence_threshold': self.confidence_threshold,
            'tags': self.tags
        }


@dataclass
class ClassificationResult:
    """Result of video classification"""
    category: str
    confidence: float  # 0.0 to 1.0
    reasoning: Dict[str, Any]  # Explain why this category
    alternative_categories: List[tuple[str, float]] = field(default_factory=list)  # Other possibilities
    features_used: List[str] = field(default_factory=list)  # Which features contributed
    processing_time_ms: float = 0.0
    classifier_id: Optional[str] = None  # Which plugin classified it

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'category': self.category,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'alternative_categories': self.alternative_categories,
            'features_used': self.features_used,
            'processing_time_ms': self.processing_time_ms,
            'classifier_id': self.classifier_id
        }


@dataclass
class VideoFeatures:
    """Container for all extracted features"""
    transcript: Optional[Dict[str, Any]] = None
    visual: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    objects: Optional[Dict[str, Any]] = None

    def has_feature(self, feature_name: str) -> bool:
        """Check if a feature is available"""
        return getattr(self, feature_name, None) is not None

    def get_feature(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get feature by name"""
        return getattr(self, feature_name, None)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'transcript': self.transcript,
            'visual': self.visual,
            'audio': self.audio,
            'objects': self.objects
        }
