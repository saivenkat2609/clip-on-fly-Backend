"""
Plugin Registry System
Manages registration, discovery, and access to all plugins
"""

from typing import Dict, List, Optional
import threading
import time

from .plugin_interface import IPlugin
from .plugin_metadata import PluginType, PluginStatus


class PluginRegistry:
    """
    Thread-safe registry for all plugins

    This is the central catalog of available plugins.
    It manages plugin lifecycle and provides query methods.

    Thread-safe: Multiple threads can access the registry simultaneously.
    """

    def __init__(self):
        self._plugins: Dict[str, IPlugin] = {}  # plugin_id -> plugin instance
        self._plugins_by_type: Dict[PluginType, List[str]] = {
            ptype: [] for ptype in PluginType
        }
        self._lock = threading.RLock()  # Reentrant lock for thread safety

    def register(self, plugin: IPlugin) -> bool:
        """
        Register a plugin

        Args:
            plugin: Plugin instance to register

        Returns:
            True if successful, False if duplicate plugin_id
        """
        with self._lock:
            metadata = plugin.get_metadata()
            plugin_id = metadata.plugin_id

            if plugin_id in self._plugins:
                print(
                    f"[Registry] Plugin '{plugin_id}' already registered, skipping"
                )
                return False

            self._plugins[plugin_id] = plugin
            self._plugins_by_type[metadata.plugin_type].append(plugin_id)

            print(
                f"[Registry] Registered plugin: {plugin_id} "
                f"(type: {metadata.plugin_type.value})"
            )
            return True

    def unregister(self, plugin_id: str) -> bool:
        """
        Unregister a plugin

        Args:
            plugin_id: ID of plugin to unregister

        Returns:
            True if successful, False if plugin not found
        """
        with self._lock:
            if plugin_id not in self._plugins:
                return False

            plugin = self._plugins[plugin_id]
            metadata = plugin.get_metadata()

            # Cleanup
            try:
                plugin.cleanup()
            except Exception as e:
                print(f"[Registry] Error cleaning up {plugin_id}: {e}")

            # Remove from registry
            del self._plugins[plugin_id]
            self._plugins_by_type[metadata.plugin_type].remove(plugin_id)

            print(f"[Registry] Unregistered plugin: {plugin_id}")
            return True

    def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """
        Get plugin by ID

        Args:
            plugin_id: Plugin identifier

        Returns:
            Plugin instance or None if not found
        """
        with self._lock:
            return self._plugins.get(plugin_id)

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
        """
        Get all plugins of a specific type

        Args:
            plugin_type: Type of plugins to retrieve

        Returns:
            List of plugin instances
        """
        with self._lock:
            plugin_ids = self._plugins_by_type.get(plugin_type, [])
            return [
                self._plugins[pid]
                for pid in plugin_ids
                if pid in self._plugins
            ]

    def get_active_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
        """
        Get all ACTIVE plugins of a specific type

        Active means:
        - Status is ACTIVE
        - Enabled is True

        Args:
            plugin_type: Type of plugins to retrieve

        Returns:
            List of active plugin instances
        """
        plugins = self.get_plugins_by_type(plugin_type)
        return [
            p for p in plugins
            if p.get_metadata().status == PluginStatus.ACTIVE
            and p.get_metadata().enabled
        ]

    def get_all_plugins(self) -> List[IPlugin]:
        """
        Get all registered plugins

        Returns:
            List of all plugin instances
        """
        with self._lock:
            return list(self._plugins.values())

    def update_plugin_status(
        self,
        plugin_id: str,
        status: PluginStatus,
        error_message: Optional[str] = None
    ):
        """
        Update plugin status

        Args:
            plugin_id: Plugin to update
            status: New status
            error_message: Optional error message if status is ERROR
        """
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin:
                metadata = plugin.get_metadata()
                metadata.status = status
                metadata.error_message = error_message
                metadata.last_health_check = time.time()

    def get_plugin_count(self) -> int:
        """
        Get total number of registered plugins

        Returns:
            Number of plugins
        """
        with self._lock:
            return len(self._plugins)

    def get_plugin_count_by_type(self, plugin_type: PluginType) -> int:
        """
        Get number of plugins of a specific type

        Args:
            plugin_type: Plugin type

        Returns:
            Count of plugins of that type
        """
        with self._lock:
            return len(self._plugins_by_type.get(plugin_type, []))

    def get_plugin_stats(self) -> Dict[str, any]:
        """
        Get statistics about registered plugins

        Returns:
            Dictionary with plugin statistics:
            {
                'total': int,
                'by_type': {type: count},
                'by_status': {status: count},
                'active': int,
                'error': int
            }
        """
        with self._lock:
            stats = {
                'total': len(self._plugins),
                'by_type': {},
                'by_status': {},
                'active': 0,
                'error': 0
            }

            for plugin in self._plugins.values():
                metadata = plugin.get_metadata()

                # Count by type
                ptype = metadata.plugin_type.value
                stats['by_type'][ptype] = stats['by_type'].get(ptype, 0) + 1

                # Count by status
                status = metadata.status.value
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

                # Count active and error
                if metadata.status == PluginStatus.ACTIVE:
                    stats['active'] += 1
                elif metadata.status == PluginStatus.ERROR:
                    stats['error'] += 1

            return stats

    def clear(self):
        """
        Clear all plugins (useful for testing)

        Cleans up and removes all plugins from registry.
        """
        with self._lock:
            # Cleanup all plugins
            for plugin in list(self._plugins.values()):
                try:
                    plugin.cleanup()
                except Exception as e:
                    print(f"[Registry] Error during cleanup: {e}")

            # Clear dictionaries
            self._plugins.clear()
            for ptype in PluginType:
                self._plugins_by_type[ptype].clear()

            print("[Registry] Cleared all plugins")
