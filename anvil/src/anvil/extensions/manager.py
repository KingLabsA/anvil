"""Extension system for Anvil - allows custom tools and integrations."""

from __future__ import annotations

import json
import importlib
import inspect
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass, field


@dataclass
class ExtensionMetadata:
    """Metadata for an extension."""
    name: str
    version: str
    description: str
    author: str
    tools: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)


@dataclass
class Extension:
    """Represents a loaded extension."""
    metadata: ExtensionMetadata
    module: Any
    path: Path
    enabled: bool = True


class ExtensionManager:
    """Manages Anvil extensions."""
    
    def __init__(self, extensions_dir: Path | None = None):
        """Initialize extension manager.
        
        Args:
            extensions_dir: Directory to store extensions (default: ~/.anvil/extensions)
        """
        self.extensions_dir = extensions_dir or (Path.home() / ".anvil" / "extensions")
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        self.extensions: dict[str, Extension] = {}
        self.hooks: dict[str, list[Callable]] = {}
        self._load_extensions()
    
    def _load_extensions(self) -> None:
        """Load all installed extensions."""
        for ext_dir in self.extensions_dir.iterdir():
            if ext_dir.is_dir():
                manifest_file = ext_dir / "extension.json"
                if manifest_file.exists():
                    try:
                        self._load_extension(ext_dir)
                    except Exception as e:
                        print(f"Failed to load extension {ext_dir.name}: {e}")
    
    def _load_extension(self, ext_dir: Path) -> None:
        """Load a single extension.
        
        Args:
            ext_dir: Extension directory
        """
        manifest_file = ext_dir / "extension.json"
        manifest = json.loads(manifest_file.read_text())
        
        metadata = ExtensionMetadata(
            name=manifest["name"],
            version=manifest["version"],
            description=manifest.get("description", ""),
            author=manifest.get("author", ""),
            tools=manifest.get("tools", []),
            hooks=manifest.get("hooks", []),
        )
        
        # Load the extension module
        main_file = ext_dir / manifest.get("main", "main.py")
        if main_file.exists():
            spec = importlib.util.spec_from_file_location(
                f"anvil_extension_{metadata.name}",
                main_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            extension = Extension(
                metadata=metadata,
                module=module,
                path=ext_dir,
            )
            
            self.extensions[metadata.name] = extension
            
            # Register hooks
            for hook_name in metadata.hooks:
                if hasattr(module, hook_name):
                    hook_func = getattr(module, hook_name)
                    if hook_name not in self.hooks:
                        self.hooks[hook_name] = []
                    self.hooks[hook_name].append(hook_func)
    
    def install(self, source: str) -> ExtensionMetadata:
        """Install an extension from a source.
        
        Args:
            source: Git URL, local path, or extension name
        
        Returns:
            Extension metadata
        """
        import shutil
        import subprocess
        
        source_path = Path(source)
        
        # If it's a local directory
        if source_path.is_dir():
            ext_name = source_path.name
            dest = self.extensions_dir / ext_name
            
            if dest.exists():
                shutil.rmtree(dest)
            
            shutil.copytree(source_path, dest)
            
        # If it's a git URL
        elif source.startswith("http") or source.startswith("git"):
            # Clone the repository
            ext_name = source.split("/")[-1].replace(".git", "")
            dest = self.extensions_dir / ext_name
            
            if dest.exists():
                shutil.rmtree(dest)
            
            subprocess.run(
                ["git", "clone", source, str(dest)],
                check=True,
                capture_output=True,
            )
        else:
            raise ValueError(f"Invalid extension source: {source}")
        
        # Load the extension
        self._load_extension(dest)
        
        return self.extensions[ext_name].metadata
    
    def uninstall(self, name: str) -> bool:
        """Uninstall an extension.
        
        Args:
            name: Extension name
        
        Returns:
            True if uninstalled, False if not found
        """
        import shutil
        
        if name not in self.extensions:
            return False
        
        extension = self.extensions[name]
        
        # Remove hooks
        for hook_name in extension.metadata.hooks:
            if hook_name in self.hooks:
                self.hooks[hook_name] = [
                    h for h in self.hooks[hook_name]
                    if not (inspect.getmodule(h) and inspect.getmodule(h).__name__.endswith(f"_{name}"))
                ]
        
        # Remove extension directory
        shutil.rmtree(extension.path)
        
        # Remove from registry
        del self.extensions[name]
        
        return True
    
    def enable(self, name: str) -> bool:
        """Enable an extension.
        
        Args:
            name: Extension name
        
        Returns:
            True if enabled, False if not found
        """
        if name not in self.extensions:
            return False
        
        self.extensions[name].enabled = True
        return True
    
    def disable(self, name: str) -> bool:
        """Disable an extension.
        
        Args:
            name: Extension name
        
        Returns:
            True if disabled, False if not found
        """
        if name not in self.extensions:
            return False
        
        self.extensions[name].enabled = False
        return True
    
    def list_extensions(self) -> list[ExtensionMetadata]:
        """List all installed extensions.
        
        Returns:
            List of extension metadata
        """
        return [ext.metadata for ext in self.extensions.values()]
    
    def get_extension(self, name: str) -> Extension | None:
        """Get an extension by name.
        
        Args:
            name: Extension name
        
        Returns:
            Extension or None if not found
        """
        return self.extensions.get(name)
    
    def call_hook(self, hook_name: str, *args, **kwargs) -> list[Any]:
        """Call all registered hooks for a given event.
        
        Args:
            hook_name: Hook name
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            List of results from hook calls
        """
        results = []
        
        if hook_name in self.hooks:
            for hook_func in self.hooks[hook_name]:
                # Check if extension is enabled
                module = inspect.getmodule(hook_func)
                if module:
                    module_name = module.__name__
                    ext_name = module_name.split("_")[-1] if "_" in module_name else ""
                    
                    if ext_name in self.extensions and self.extensions[ext_name].enabled:
                        try:
                            result = hook_func(*args, **kwargs)
                            results.append(result)
                        except Exception as e:
                            print(f"Hook {hook_name} failed: {e}")
                else:
                    # If we can't determine the module, just call the hook
                    try:
                        result = hook_func(*args, **kwargs)
                        results.append(result)
                    except Exception as e:
                        print(f"Hook {hook_name} failed: {e}")
        
        return results
    
    def get_tool(self, tool_name: str) -> Callable | None:
        """Get a tool function by name.
        
        Args:
            tool_name: Tool name
        
        Returns:
            Tool function or None if not found
        """
        for ext in self.extensions.values():
            if not ext.enabled:
                continue
            
            if tool_name in ext.metadata.tools:
                if hasattr(ext.module, tool_name):
                    return getattr(ext.module, tool_name)
        
        return None
    
    def list_tools(self) -> list[str]:
        """List all available tools from extensions.
        
        Returns:
            List of tool names
        """
        tools = []
        for ext in self.extensions.values():
            if ext.enabled:
                tools.extend(ext.metadata.tools)
        return tools
