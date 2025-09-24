"""
Strategy plugin manager for dynamic loading, versioning, and lifecycle management.
"""

import os
import sys
import json
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
import structlog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib
import semver

from .strategy_interface import IStrategy, StrategyConfig, StrategyStatus

logger = structlog.get_logger()

@dataclass
class PluginMetadata:
    """Metadata for a strategy plugin."""
    name: str
    version: str
    author: str
    description: str
    dependencies: List[str]
    entry_point: str
    config_schema: Dict[str, Any]
    created_at: datetime
    file_path: str
    file_hash: str

@dataclass
class PluginInstance:
    """Running instance of a strategy plugin."""
    metadata: PluginMetadata
    strategy: IStrategy
    config: StrategyConfig
    status: StrategyStatus
    load_time: datetime
    error_count: int = 0
    last_error: Optional[str] = None

class StrategyFileHandler(FileSystemEventHandler):
    """File system watcher for hot-reloading strategies."""

    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager

    def on_modified(self, event):
        if event.is_directory:
            return

        if event.src_path.endswith('.py'):
            plugin_name = Path(event.src_path).stem
            logger.info("Strategy file modified", file=event.src_path, plugin=plugin_name)
            asyncio.create_task(self.plugin_manager.reload_plugin(plugin_name))

class PluginManager:
    """
    Manages strategy plugin lifecycle including loading, versioning, and hot-reloading.
    """

    def __init__(self, plugins_directory: str = "plugins", registry_file: str = "strategy_registry.json"):
        self.plugins_directory = Path(plugins_directory)
        self.registry_file = registry_file
        self.plugins: Dict[str, PluginInstance] = {}
        self.registry: Dict[str, PluginMetadata] = {}
        self.observer: Optional[Observer] = None

        # Ensure plugins directory exists
        self.plugins_directory.mkdir(exist_ok=True)

    async def initialize(self):
        """Initialize the plugin manager."""
        logger.info("Initializing plugin manager", directory=str(self.plugins_directory))

        # Load plugin registry
        await self._load_registry()

        # Discover and load plugins
        await self._discover_plugins()

        # Start file watcher for hot-reload
        await self._start_file_watcher()

    async def shutdown(self):
        """Shutdown the plugin manager."""
        logger.info("Shutting down plugin manager")

        # Stop file watcher
        if self.observer:
            self.observer.stop()
            self.observer.join()

        # Unload all plugins
        for plugin_name in list(self.plugins.keys()):
            await self.unload_plugin(plugin_name)

        # Save registry
        await self._save_registry()

    async def _load_registry(self):
        """Load plugin registry from disk."""
        registry_path = Path(self.registry_file)
        if registry_path.exists():
            try:
                with open(registry_path, 'r') as f:
                    data = json.load(f)
                    for name, metadata_dict in data.items():
                        # Convert string timestamps back to datetime
                        metadata_dict['created_at'] = datetime.fromisoformat(metadata_dict['created_at'])
                        self.registry[name] = PluginMetadata(**metadata_dict)
                logger.info("Registry loaded", plugins=len(self.registry))
            except Exception as e:
                logger.error("Failed to load registry", error=str(e))

    async def _save_registry(self):
        """Save plugin registry to disk."""
        try:
            data = {}
            for name, metadata in self.registry.items():
                metadata_dict = asdict(metadata)
                # Convert datetime to string for JSON serialization
                metadata_dict['created_at'] = metadata.created_at.isoformat()
                data[name] = metadata_dict

            with open(self.registry_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Registry saved", plugins=len(self.registry))
        except Exception as e:
            logger.error("Failed to save registry", error=str(e))

    async def _discover_plugins(self):
        """Discover all strategy plugins in the plugins directory."""
        logger.info("Discovering plugins", directory=str(self.plugins_directory))

        for py_file in self.plugins_directory.glob("*.py"):
            if py_file.name.startswith("__"):
                continue

            plugin_name = py_file.stem
            await self._register_plugin(plugin_name, str(py_file))

    async def _register_plugin(self, plugin_name: str, file_path: str):
        """Register a plugin in the registry."""
        try:
            # Calculate file hash
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            # Check if plugin is already registered with same hash
            if plugin_name in self.registry and self.registry[plugin_name].file_hash == file_hash:
                logger.debug("Plugin already registered with same hash", plugin=plugin_name)
                return

            # Extract metadata from plugin file
            metadata = await self._extract_plugin_metadata(plugin_name, file_path, file_hash)
            if metadata:
                self.registry[plugin_name] = metadata
                logger.info("Plugin registered", plugin=plugin_name, version=metadata.version)

        except Exception as e:
            logger.error("Failed to register plugin", plugin=plugin_name, error=str(e))

    async def _extract_plugin_metadata(self, plugin_name: str, file_path: str, file_hash: str) -> Optional[PluginMetadata]:
        """Extract metadata from plugin file."""
        try:
            # Load the module temporarily to extract metadata
            spec = importlib.util.spec_from_file_location(plugin_name, file_path)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for metadata attributes
            metadata = PluginMetadata(
                name=getattr(module, '__plugin_name__', plugin_name),
                version=getattr(module, '__version__', '1.0.0'),
                author=getattr(module, '__author__', 'Unknown'),
                description=getattr(module, '__description__', ''),
                dependencies=getattr(module, '__dependencies__', []),
                entry_point=getattr(module, '__entry_point__', 'StrategyPlugin'),
                config_schema=getattr(module, '__config_schema__', {}),
                created_at=datetime.utcnow(),
                file_path=file_path,
                file_hash=file_hash
            )

            # Validate version format
            try:
                semver.VersionInfo.parse(metadata.version)
            except ValueError:
                logger.warning("Invalid version format", plugin=plugin_name, version=metadata.version)
                metadata.version = '1.0.0'

            return metadata

        except Exception as e:
            logger.error("Failed to extract plugin metadata", plugin=plugin_name, error=str(e))
            return None

    async def _start_file_watcher(self):
        """Start file system watcher for hot-reloading."""
        try:
            self.observer = Observer()
            event_handler = StrategyFileHandler(self)
            self.observer.schedule(event_handler, str(self.plugins_directory), recursive=False)
            self.observer.start()
            logger.info("File watcher started", directory=str(self.plugins_directory))
        except Exception as e:
            logger.error("Failed to start file watcher", error=str(e))

    async def load_plugin(self, plugin_name: str, config: StrategyConfig) -> bool:
        """Load and instantiate a strategy plugin."""
        try:
            if plugin_name in self.plugins:
                logger.warning("Plugin already loaded", plugin=plugin_name)
                return False

            if plugin_name not in self.registry:
                logger.error("Plugin not found in registry", plugin=plugin_name)
                return False

            metadata = self.registry[plugin_name]

            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_name, metadata.file_path)
            if not spec or not spec.loader:
                logger.error("Failed to create module spec", plugin=plugin_name)
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the strategy class
            strategy_class = getattr(module, metadata.entry_point)
            if not issubclass(strategy_class, IStrategy):
                logger.error("Strategy class does not implement IStrategy", plugin=plugin_name)
                return False

            # Instantiate strategy
            strategy = strategy_class(config)

            # Initialize strategy
            if not await strategy.initialize():
                logger.error("Strategy initialization failed", plugin=plugin_name)
                return False

            # Create plugin instance
            instance = PluginInstance(
                metadata=metadata,
                strategy=strategy,
                config=config,
                status=StrategyStatus.INACTIVE,
                load_time=datetime.utcnow()
            )

            self.plugins[plugin_name] = instance
            logger.info("Plugin loaded successfully", plugin=plugin_name, version=metadata.version)
            return True

        except Exception as e:
            logger.error("Failed to load plugin", plugin=plugin_name, error=str(e))
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a strategy plugin."""
        try:
            if plugin_name not in self.plugins:
                logger.warning("Plugin not loaded", plugin=plugin_name)
                return False

            instance = self.plugins[plugin_name]

            # Stop strategy if running
            if instance.status == StrategyStatus.ACTIVE:
                await instance.strategy.on_stop()

            # Cleanup strategy
            await instance.strategy.cleanup()

            # Remove from plugins
            del self.plugins[plugin_name]

            # Remove module from sys.modules to allow reload
            module_name = f"strategy_{plugin_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

            logger.info("Plugin unloaded", plugin=plugin_name)
            return True

        except Exception as e:
            logger.error("Failed to unload plugin", plugin=plugin_name, error=str(e))
            return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a strategy plugin (hot-reload)."""
        try:
            if plugin_name not in self.plugins:
                logger.info("Plugin not loaded, attempting to discover and load", plugin=plugin_name)

                # Re-discover the plugin
                plugin_file = self.plugins_directory / f"{plugin_name}.py"
                if plugin_file.exists():
                    await self._register_plugin(plugin_name, str(plugin_file))

                    # Try to load with default config
                    if plugin_name in self.registry:
                        default_config = StrategyConfig(
                            name=plugin_name,
                            version=self.registry[plugin_name].version,
                            enabled=False,
                            parameters={},
                            risk_limits={}
                        )
                        return await self.load_plugin(plugin_name, default_config)
                return False

            instance = self.plugins[plugin_name]
            old_config = instance.config

            # Unload current instance
            await self.unload_plugin(plugin_name)

            # Re-register plugin (this will update metadata if file changed)
            plugin_file = self.plugins_directory / f"{plugin_name}.py"
            if plugin_file.exists():
                await self._register_plugin(plugin_name, str(plugin_file))

            # Reload with same config
            success = await self.load_plugin(plugin_name, old_config)

            if success:
                logger.info("Plugin reloaded successfully", plugin=plugin_name)
            else:
                logger.error("Plugin reload failed", plugin=plugin_name)

            return success

        except Exception as e:
            logger.error("Failed to reload plugin", plugin=plugin_name, error=str(e))
            return False

    async def start_plugin(self, plugin_name: str) -> bool:
        """Start a loaded plugin."""
        if plugin_name not in self.plugins:
            return False

        instance = self.plugins[plugin_name]
        await instance.strategy.on_start()
        instance.status = StrategyStatus.ACTIVE
        logger.info("Plugin started", plugin=plugin_name)
        return True

    async def stop_plugin(self, plugin_name: str) -> bool:
        """Stop a running plugin."""
        if plugin_name not in self.plugins:
            return False

        instance = self.plugins[plugin_name]
        await instance.strategy.on_stop()
        instance.status = StrategyStatus.INACTIVE
        logger.info("Plugin stopped", plugin=plugin_name)
        return True

    async def pause_plugin(self, plugin_name: str) -> bool:
        """Pause a running plugin."""
        if plugin_name not in self.plugins:
            return False

        instance = self.plugins[plugin_name]
        await instance.strategy.on_pause()
        instance.status = StrategyStatus.PAUSED
        logger.info("Plugin paused", plugin=plugin_name)
        return True

    async def resume_plugin(self, plugin_name: str) -> bool:
        """Resume a paused plugin."""
        if plugin_name not in self.plugins:
            return False

        instance = self.plugins[plugin_name]
        await instance.strategy.on_resume()
        instance.status = StrategyStatus.ACTIVE
        logger.info("Plugin resumed", plugin=plugin_name)
        return True

    async def update_plugin_config(self, plugin_name: str, new_config: StrategyConfig) -> bool:
        """Update plugin configuration."""
        if plugin_name not in self.plugins:
            return False

        instance = self.plugins[plugin_name]
        await instance.strategy.on_config_update(new_config)
        instance.config = new_config
        logger.info("Plugin config updated", plugin=plugin_name)
        return True

    def list_plugins(self) -> Dict[str, Dict[str, Any]]:
        """List all plugins with their status."""
        result = {}

        for name, metadata in self.registry.items():
            plugin_info = {
                "metadata": asdict(metadata),
                "loaded": name in self.plugins,
                "status": None,
                "error_count": 0,
                "last_error": None
            }

            if name in self.plugins:
                instance = self.plugins[name]
                plugin_info["status"] = instance.status.value
                plugin_info["error_count"] = instance.error_count
                plugin_info["last_error"] = instance.last_error
                plugin_info["load_time"] = instance.load_time.isoformat()

            result[name] = plugin_info

        return result

    def get_plugin_instance(self, plugin_name: str) -> Optional[PluginInstance]:
        """Get plugin instance by name."""
        return self.plugins.get(plugin_name)

    async def get_plugin_health(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get health status of a plugin."""
        if plugin_name not in self.plugins:
            return None

        instance = self.plugins[plugin_name]
        try:
            health = await instance.strategy.get_health_status()
            return health
        except Exception as e:
            instance.error_count += 1
            instance.last_error = str(e)
            logger.error("Failed to get plugin health", plugin=plugin_name, error=str(e))
            return {"status": "error", "error": str(e)}