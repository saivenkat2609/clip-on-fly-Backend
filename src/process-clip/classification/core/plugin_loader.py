"""
Plugin Loader System
Auto-discovers and loads plugins from directories
"""

import os
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, List, Optional

from .plugin_interface import IPlugin, BasePlugin, IFeatureExtractorPlugin, IClassifierPlugin, IProcessingStrategyPlugin
from .plugin_registry import PluginRegistry


class PluginLoader:
    """
    Auto-discovers and loads plugins from directories

    This is what makes the system "plug and play" - just drop
    a Python file with a plugin class into the plugins directory
    and it will be automatically discovered and loaded.
    """

    def __init__(self, registry: PluginRegistry):
        """
        Initialize plugin loader

        Args:
            registry: Plugin registry to register discovered plugins
        """
        self.registry = registry
        self.plugin_dirs: List[Path] = []

    def add_plugin_directory(self, directory: str):
        """
        Add a directory to search for plugins

        Args:
            directory: Path to directory containing plugin files
        """
        path = Path(directory)
        if path.exists() and path.is_dir():
            self.plugin_dirs.append(path)
            print(f"[PluginLoader] Added plugin directory: {path}")
        else:
            print(f"[PluginLoader] Warning: Directory not found: {path}")

    def discover_and_load_all(self) -> Dict[str, bool]:
        """
        Discover and load all plugins from registered directories

        Scans all registered directories for Python files,
        finds plugin classes, instantiates them, and registers them.

        Returns:
            Dictionary of plugin_id -> success/failure
        """
        results = {}

        for plugin_dir in self.plugin_dirs:
            print(f"[PluginLoader] Scanning directory: {plugin_dir}")

            # Find all Python files
            for py_file in plugin_dir.glob("**/*.py"):
                if py_file.name.startswith("_"):
                    continue  # Skip private modules like __init__.py

                try:
                    plugins = self._load_plugins_from_file(py_file)
                    for plugin in plugins:
                        metadata = plugin.get_metadata()
                        success = self.registry.register(plugin)
                        results[metadata.plugin_id] = success
                except Exception as e:
                    print(f"[PluginLoader] Failed to load {py_file}: {e}")
                    results[str(py_file)] = False

        success_count = sum(results.values())
        total_count = len(results)
        print(f"[PluginLoader] Loaded {success_count}/{total_count} plugins")
        return results

    def _load_plugins_from_file(self, filepath: Path) -> List[IPlugin]:
        """
        Load all plugin classes from a Python file

        Args:
            filepath: Path to Python file

        Returns:
            List of instantiated plugin objects
        """
        plugins = []

        # Load module dynamically
        spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
        if spec is None or spec.loader is None:
            return plugins

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find all plugin classes in module
        for name, obj in inspect.getmembers(module):
            if self._is_plugin_class(obj):
                try:
                    # Instantiate plugin
                    plugin_instance = obj()
                    plugins.append(plugin_instance)
                    print(
                        f"[PluginLoader] Found plugin: "
                        f"{plugin_instance.get_metadata().plugin_id}"
                    )
                except Exception as e:
                    print(f"[PluginLoader] Failed to instantiate {name}: {e}")

        return plugins

    def _is_plugin_class(self, obj) -> bool:
        """
        Check if an object is a plugin class

        Args:
            obj: Object to check

        Returns:
            True if obj is a plugin class (not a base class)
        """
        # Must be a class
        if not inspect.isclass(obj):
            return False

        # Must be a subclass of IPlugin
        if not issubclass(obj, IPlugin):
            return False

        # Must not be a base class itself
        base_classes = [
            IPlugin,
            BasePlugin,
            IFeatureExtractorPlugin,
            IClassifierPlugin,
            IProcessingStrategyPlugin
        ]
        if obj in base_classes:
            return False

        return True

    def reload_plugin(self, plugin_id: str) -> bool:
        """
        Hot-reload a plugin (unregister and reload from file)

        Useful for development - update plugin code and reload
        without restarting the entire system.

        Args:
            plugin_id: ID of plugin to reload

        Returns:
            True if successful, False otherwise
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            print(f"[PluginLoader] Plugin {plugin_id} not found")
            return False

        # Find source file
        module = inspect.getmodule(plugin.__class__)
        if not module or not hasattr(module, '__file__'):
            print(f"[PluginLoader] Cannot find source file for {plugin_id}")
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

    def load_plugin_from_class(self, plugin_class) -> bool:
        """
        Load a plugin from a class directly (useful for testing)

        Args:
            plugin_class: Plugin class to instantiate and register

        Returns:
            True if successful, False otherwise
        """
        try:
            plugin_instance = plugin_class()
            return self.registry.register(plugin_instance)
        except Exception as e:
            print(f"[PluginLoader] Failed to load plugin class: {e}")
            return False
