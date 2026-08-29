"""Append-only registry for harness-neutral skills (SKILL-4)."""

from __future__ import annotations

from cellxp.harness.contracts import SkillPlugin


class SkillRegistry:
    def __init__(self) -> None:
        self._plugins: dict[tuple[str, str], SkillPlugin] = {}

    def register(self, plugin: SkillPlugin) -> SkillPlugin:
        key = (plugin.spec.name, plugin.spec.version)
        if key in self._plugins:
            raise ValueError(f"skill {plugin.spec.name!r}@{plugin.spec.version} is already registered")
        self._plugins[key] = plugin
        return plugin

    def get(self, name: str, version: str | None = None) -> SkillPlugin:
        if version is not None:
            try:
                return self._plugins[(name, version)]
            except KeyError:
                raise KeyError(f"no skill registered as {name!r}@{version}") from None

        matches = [plugin for (candidate, _), plugin in self._plugins.items() if candidate == name]
        if not matches:
            raise KeyError(f"no skill registered as {name!r}")
        if len(matches) > 1:
            versions = sorted(plugin.spec.version for plugin in matches)
            raise KeyError(f"skill {name!r} has multiple versions; select one of {versions}")
        return matches[0]

    def tool_definitions(self) -> list[dict[str, object]]:
        return [
            plugin.tool_definition()
            for _, plugin in sorted(self._plugins.items())
            if plugin.spec.model_visible
        ]

    def names(self) -> list[str]:
        return sorted({name for name, _ in self._plugins})

    def __len__(self) -> int:
        return len(self._plugins)


__all__ = ["SkillRegistry"]
