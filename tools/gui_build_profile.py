#!/usr/bin/env python3
"""Helpers for build preset selection and current build-profile state."""

from __future__ import annotations

from dataclasses import dataclass

from slot_definitions import BUILD_PRESETS, DEFAULT_SCALE_FILTER, normalize_cursor_sizes, resolve_build_preset


PROFILE_KIND_EXACT = "exact-preset"
PROFILE_KIND_CUSTOM_DERIVED = "custom-derived"
PROFILE_KIND_CUSTOM_UNMATCHED = "custom-unmatched"


@dataclass(frozen=True, slots=True)
class BuildProfileState:
    kind: str
    base_preset_label: str | None
    matching_preset_labels: tuple[str, ...]
    target_sizes: tuple[int, ...]
    scale_filter: str

    @property
    def label(self) -> str:
        if self.kind == PROFILE_KIND_EXACT and self.base_preset_label:
            return self.base_preset_label
        if self.base_preset_label:
            return f"Custom from {self.base_preset_label}"
        return "Custom"

    @property
    def headline(self) -> str:
        return f"Current build profile: {self.label}"

    @property
    def detail(self) -> str:
        aliases = [label for label in self.matching_preset_labels if label != self.base_preset_label]
        if self.kind == PROFILE_KIND_EXACT and self.base_preset_label:
            if aliases:
                return "Exact named preset. These settings also match " + ", ".join(aliases) + "."
            return "Exact named preset. Manual edits will switch this profile into Custom."
        if self.kind == PROFILE_KIND_CUSTOM_DERIVED and self.base_preset_label:
            if self.matching_preset_labels:
                return (
                    f"Started from {self.base_preset_label}. Manual edits changed the settings. "
                    f"They now match {', '.join(self.matching_preset_labels)}."
                )
            return (
                f"Started from {self.base_preset_label}. Manual edits changed the settings and they no longer match "
                "any named preset."
            )
        if self.matching_preset_labels:
            return "Manual settings currently match " + ", ".join(self.matching_preset_labels) + "."
        return "Manual settings that do not currently match any named preset."

    @property
    def compare_label(self) -> str:
        return self.label


def _normalize_scale_filter(value: str | None) -> str:
    normalized = (value or "").strip()
    return normalized or DEFAULT_SCALE_FILTER


def matching_preset_labels(target_sizes: list[int] | tuple[int, ...], scale_filter: str | None) -> tuple[str, ...]:
    normalized_sizes = tuple(normalize_cursor_sizes(list(target_sizes)))
    normalized_filter = _normalize_scale_filter(scale_filter)
    return tuple(
        preset["label"]
        for preset in BUILD_PRESETS
        if tuple(preset["target_sizes"]) == normalized_sizes and preset["scale_filter"] == normalized_filter
    )


def resolve_build_profile_state(
    target_sizes: list[int] | tuple[int, ...],
    scale_filter: str | None,
    *,
    base_preset_label: str | None,
) -> BuildProfileState:
    normalized_sizes = tuple(normalize_cursor_sizes(list(target_sizes)))
    normalized_filter = _normalize_scale_filter(scale_filter)
    matching_labels = matching_preset_labels(normalized_sizes, normalized_filter)

    resolved_base = None
    if base_preset_label:
        try:
            resolved_base = resolve_build_preset(base_preset_label)["label"]
        except KeyError:
            resolved_base = None

    if resolved_base is not None:
        base_preset = resolve_build_preset(resolved_base)
        if tuple(base_preset["target_sizes"]) == normalized_sizes and base_preset["scale_filter"] == normalized_filter:
            kind = PROFILE_KIND_EXACT
        elif matching_labels:
            kind = PROFILE_KIND_CUSTOM_DERIVED
        else:
            kind = PROFILE_KIND_CUSTOM_UNMATCHED
        return BuildProfileState(
            kind=kind,
            base_preset_label=resolved_base,
            matching_preset_labels=matching_labels,
            target_sizes=normalized_sizes,
            scale_filter=normalized_filter,
        )

    inferred_base = matching_labels[0] if matching_labels else None
    kind = PROFILE_KIND_EXACT if inferred_base else PROFILE_KIND_CUSTOM_UNMATCHED
    return BuildProfileState(
        kind=kind,
        base_preset_label=inferred_base,
        matching_preset_labels=matching_labels,
        target_sizes=normalized_sizes,
        scale_filter=normalized_filter,
    )


def build_profile_payload(state: BuildProfileState) -> dict:
    return {
        "version": 1,
        "kind": state.kind,
        "base_preset_label": state.base_preset_label,
        "matching_preset_labels": list(state.matching_preset_labels),
    }


def restore_profile_base_preset(
    profile_payload: dict | None,
    target_sizes: list[int] | tuple[int, ...],
    scale_filter: str | None,
) -> str | None:
    if isinstance(profile_payload, dict):
        base_preset_label = profile_payload.get("base_preset_label")
        if isinstance(base_preset_label, str) and base_preset_label.strip():
            try:
                return resolve_build_preset(base_preset_label)["label"]
            except KeyError:
                pass
    matches = matching_preset_labels(target_sizes, scale_filter)
    return matches[0] if matches else None
