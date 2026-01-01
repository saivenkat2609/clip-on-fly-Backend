"""
Plugin Manager
Handles plugin lifecycle: initialization, health checks, configuration
"""

import time
import json
from typing import Dict, Any, Optional, Tuple, List

from .plugin_registry import PluginRegistry
from .plugin_loader import PluginLoader
from .plugin_metadata import PluginStatus


class PluginManager:
    """
    High-level plugin management

    Handles:
    - Configuration loading
    - Plugin initialization
    - Health monitoring
    - Lifecycle management
    """

    def __init__(self, registry: PluginRegistry, loader: PluginLoader):
        """
        Initialize plugin manager

        Args:
            registry: Plugin registry instance
            loader: Plugin loader instance
        """
        self.registry = registry
        self.loader = loader
        self.config: Dict[str, Dict[str, Any]] = {}  # plugin_id -> config

    def load_config(self, config_path: str):
        """
        Load plugin configuration from JSON file

        Config file format:
        {
            "plugin_id": {
                "enabled": true,
                "custom_param": "value"
            }
        }

        Args:
            config_path: Path to JSON config file
        """
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            print(
                f"[PluginManager] Loaded config for {len(self.config)} plugins"
            )
        except FileNotFoundError:
            print(f"[PluginManager] Config file not found: {config_path}")
        except json.JSONDecodeError as e:
            print(f"[PluginManager] Invalid JSON in config: {e}")

    def load_config_dict(self, config: Dict[str, Dict[str, Any]]):
        """
        Load plugin configuration from dictionary

        Args:
            config: Configuration dictionary
        """
        self.config = config
        print(f"[PluginManager] Loaded config for {len(self.config)} plugins")

    def initialize_all_plugins(self) -> Dict[str, bool]:
        """
        Initialize all registered plugins

        Calls initialize() on each plugin with its configuration.
        Updates plugin status based on initialization result.

        Returns:
            Dictionary of plugin_id -> success/failure
        """
        results = {}

        for plugin in self.registry.get_all_plugins():
            metadata = plugin.get_metadata()
            plugin_id = metadata.plugin_id

            # Get config for this plugin
            plugin_config = self.config.get(plugin_id, metadata.default_config)

            # Check if disabled in config
            if not plugin_config.get('enabled', metadata.enabled):
                print(
                    f"[PluginManager] Plugin {plugin_id} is disabled, skipping"
                )
                self.registry.update_plugin_status(
                    plugin_id,
                    PluginStatus.DISABLED
                )
                results[plugin_id] = False
                continue

            # Initialize
            success = plugin.initialize(plugin_config)

            if success:
                self.registry.update_plugin_status(
                    plugin_id,
                    PluginStatus.ACTIVE
                )
                results[plugin_id] = True
            else:
                self.registry.update_plugin_status(
                    plugin_id,
                    PluginStatus.ERROR,
                    "Initialization failed"
                )
                results[plugin_id] = False

        active_count = sum(results.values())
        print(
            f"[PluginManager] Initialized {active_count}/{len(results)} plugins"
        )
        return results

    def run_health_checks(self) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Run health checks on all plugins

        Calls health_check() on each plugin and updates status.

        Returns:
            Dictionary of plugin_id -> (is_healthy, error_message)
        """
        results = {}

        for plugin in self.registry.get_all_plugins():
            metadata = plugin.get_metadata()
            plugin_id = metadata.plugin_id

            if metadata.status == PluginStatus.DISABLED:
                continue

            is_healthy, error_msg = plugin.health_check()
            results[plugin_id] = (is_healthy, error_msg)

            if is_healthy:
                self.registry.update_plugin_status(
                    plugin_id,
                    PluginStatus.ACTIVE
                )
            else:
                self.registry.update_plugin_status(
                    plugin_id,
                    PluginStatus.ERROR,
                    error_msg
                )
                print(
                    f"[PluginManager] Plugin {plugin_id} unhealthy: {error_msg}"
                )

        return results

    def get_plugin_stats(self) -> Dict[str, Any]:
        """
        Get statistics about all plugins

        Returns:
            Dictionary with comprehensive plugin statistics
        """
        return self.registry.get_plugin_stats()

    def shutdown_all_plugins(self):
        """
        Clean shutdown of all plugins

        Calls cleanup() on each plugin.
        """
        print("[PluginManager] Shutting down all plugins...")
        for plugin in self.registry.get_all_plugins():
            try:
                plugin.cleanup()
            except Exception as e:
                print(
                    f"[PluginManager] Error cleaning up "
                    f"{plugin.get_metadata().plugin_id}: {e}"
                )

    def enable_plugin(self, plugin_id: str) -> bool:
        """
        Enable a disabled plugin

        Args:
            plugin_id: Plugin to enable

        Returns:
            True if successful
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            return False

        metadata = plugin.get_metadata()
        if metadata.status != PluginStatus.DISABLED:
            print(f"[PluginManager] Plugin {plugin_id} is not disabled")
            return False

        # Initialize plugin
        plugin_config = self.config.get(plugin_id, metadata.default_config)
        success = plugin.initialize(plugin_config)

        if success:
            self.registry.update_plugin_status(plugin_id, PluginStatus.ACTIVE)
            print(f"[PluginManager] Enabled plugin: {plugin_id}")
            return True
        else:
            self.registry.update_plugin_status(
                plugin_id,
                PluginStatus.ERROR,
                "Failed to initialize"
            )
            return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """
        Disable an active plugin

        Args:
            plugin_id: Plugin to disable

        Returns:
            True if successful
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            return False

        try:
            plugin.cleanup()
            self.registry.update_plugin_status(plugin_id, PluginStatus.DISABLED)
            print(f"[PluginManager] Disabled plugin: {plugin_id}")
            return True
        except Exception as e:
            print(f"[PluginManager] Error disabling plugin {plugin_id}: {e}")
            return False

    def get_plugin_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a plugin

        Args:
            plugin_id: Plugin to query

        Returns:
            Dictionary with plugin information or None if not found
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            return None

        metadata = plugin.get_metadata()
        return metadata.to_dict()

    def list_all_plugins(self) -> List[Dict[str, Any]]:
        """
        List all registered plugins with their metadata

        Returns:
            List of plugin information dictionaries
        """
        return [
            plugin.get_metadata().to_dict()
            for plugin in self.registry.get_all_plugins()
        ]
