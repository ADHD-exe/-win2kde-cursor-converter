#!/usr/bin/env python3
"""Helpers for readiness messaging and compare guidance in the GUI workbench."""

from __future__ import annotations

from dataclasses import dataclass

from slot_definitions import SLOT_BY_KEY


READINESS_BUILD_READY = "build-ready"
READINESS_BUILD_READY_WITH_REVIEW = "build-ready with review"
READINESS_COMPARE_BEFORE_EXPORT = "compare before export"
READINESS_REDRAW_REQUIRED = "redraw/manual replacement required"


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    overall_quality_text: str
    readiness_headline: str
    readiness_detail: str
    review_queue_headline: str
    review_queue_hint: str
    guidance_text: str
    suggested_preset: str | None


def decision_lane(decision: str | None) -> str:
    normalized = (decision or "").strip().lower()
    if normalized == "build-ready":
        return READINESS_BUILD_READY
    if normalized == "build-ready with review":
        return READINESS_BUILD_READY_WITH_REVIEW
    if normalized == "compare before export":
        return READINESS_COMPARE_BEFORE_EXPORT
    return READINESS_REDRAW_REQUIRED


def _overall_quality_text(
    *,
    quality_entries: list[tuple[dict, dict, dict | None]],
    pending_slots: list[str],
    selected_slot_count: int,
    resolved_role_count: int,
    mapping_error: str | None,
) -> str:
    if mapping_error:
        return "Overall quality forecast: configuration error"
    if not quality_entries and pending_slots:
        return f"Overall quality forecast: loading slot analysis ({len(pending_slots)} pending)"
    if not quality_entries:
        return "Overall quality forecast: no source slots assigned"

    score_map = {
        "excellent": 4,
        "good": 3,
        "acceptable": 2,
        "likely blurry": 1,
        "redraw recommended": 0,
    }
    labels = [quality.get("label", "redraw recommended") for _slot, quality, _context in quality_entries]
    avg_score = sum(score_map.get(label, 0) for label in labels) / max(1, len(labels))
    if avg_score >= 3.5:
        overall = "excellent"
    elif avg_score >= 2.6:
        overall = "good"
    elif avg_score >= 1.8:
        overall = "acceptable"
    elif avg_score >= 1.0:
        overall = "likely blurry"
    else:
        overall = "redraw recommended"

    low_confidence_count = sum(1 for _slot, quality, _context in quality_entries if quality.get("confidence") == "low")
    confidence = "low" if low_confidence_count >= max(1, len(quality_entries) // 3) else "medium"
    if low_confidence_count == 0 and all(quality.get("confidence") == "high" for _slot, quality, _context in quality_entries):
        confidence = "high"
    suffix = f" | {len(pending_slots)} slot(s) still preparing" if pending_slots else ""
    return (
        f"Overall quality forecast: {overall} ({confidence} confidence) | "
        f"{selected_slot_count} slot(s) assigned | {resolved_role_count} Linux roles resolved{suffix}"
    )


def build_readiness_snapshot(
    *,
    quality_entries: list[tuple[dict, dict, dict | None]],
    pending_slots: list[str],
    selected_slot_count: int,
    resolved_role_count: int,
    target_sizes: list[int] | tuple[int, ...],
    size_error: str | None,
    mapping_error: str | None,
    pack_analysis: dict | None,
    safe_preset_label: str,
) -> ReadinessSnapshot:
    counts = {
        READINESS_BUILD_READY: 0,
        READINESS_BUILD_READY_WITH_REVIEW: 0,
        READINESS_COMPARE_BEFORE_EXPORT: 0,
        READINESS_REDRAW_REQUIRED: 0,
    }
    fallback_entries: list[tuple[dict, dict, dict | None]] = []
    review_entries: list[tuple[dict, dict, dict | None]] = []
    compare_entries: list[tuple[dict, dict, dict | None]] = []
    redraw_entries: list[tuple[dict, dict, dict | None]] = []
    suggested_preset = None

    for slot, quality, context in quality_entries:
        lane = decision_lane(quality.get("decision"))
        counts[lane] += 1
        if quality.get("suggested_preset") and suggested_preset is None:
            suggested_preset = quality["suggested_preset"]
        if context and context.get("origin") == "fallback":
            fallback_entries.append((slot, quality, context))
        if lane == READINESS_BUILD_READY_WITH_REVIEW:
            review_entries.append((slot, quality, context))
        elif lane == READINESS_COMPARE_BEFORE_EXPORT:
            compare_entries.append((slot, quality, context))
        elif lane == READINESS_REDRAW_REQUIRED:
            redraw_entries.append((slot, quality, context))

    hidpi = (pack_analysis or {}).get("hidpi_potential", {})
    weak_hidpi = hidpi.get("rating") in {"weak", "limited"}
    ambiguous_slots = sorted((pack_analysis or {}).get("ambiguous_candidates", {}).keys())
    pack_warnings = list((pack_analysis or {}).get("warnings", []))

    if suggested_preset is None and weak_hidpi and max((int(size) for size in target_sizes), default=0) >= 96:
        suggested_preset = safe_preset_label

    if mapping_error or size_error:
        readiness_headline = "Pack readiness: configuration error"
    elif redraw_entries:
        readiness_headline = "Pack readiness: redraw/manual replacement required"
    elif compare_entries or fallback_entries or ambiguous_slots:
        readiness_headline = "Pack readiness: compare before export"
    elif review_entries or weak_hidpi:
        readiness_headline = "Pack readiness: build-ready with review"
    elif pending_slots:
        readiness_headline = "Pack readiness: preparing slot analysis"
    elif quality_entries:
        readiness_headline = "Pack readiness: build-ready"
    else:
        readiness_headline = "Pack readiness: no source slots assigned"

    readiness_parts = [
        f"{selected_slot_count} slot(s) assigned",
        f"{resolved_role_count} Linux role(s)",
        f"{counts[READINESS_BUILD_READY]} build-ready",
        f"{counts[READINESS_BUILD_READY_WITH_REVIEW]} review",
        f"{counts[READINESS_COMPARE_BEFORE_EXPORT]} compare-first",
        f"{counts[READINESS_REDRAW_REQUIRED]} redraw/manual",
    ]
    if fallback_entries:
        readiness_parts.append(f"{len(fallback_entries)} fallback-reused")
    if ambiguous_slots:
        readiness_parts.append(f"{len(ambiguous_slots)} ambiguous")
    if weak_hidpi:
        readiness_parts.append("weak HiDPI coverage")
    if pending_slots:
        readiness_parts.append(f"{len(pending_slots)} pending")
    readiness_detail = " | ".join(readiness_parts)

    if not quality_entries and not pending_slots:
        review_queue_headline = "Review queue: no source slots assigned yet"
        review_queue_hint = "Assign or auto-fill slots first, then use Compare to clear export risk."
    else:
        review_parts = [
            f"{counts[READINESS_COMPARE_BEFORE_EXPORT]} compare-first",
            f"{counts[READINESS_REDRAW_REQUIRED]} redraw/manual",
            f"{len(fallback_entries)} fallback-reused",
            f"{len(ambiguous_slots)} ambiguous",
        ]
        if weak_hidpi:
            review_parts.append("weak HiDPI")
        review_queue_headline = "Review queue: " + " | ".join(review_parts)
    if redraw_entries:
        review_queue_hint = "Clear redraw/manual items first, then compare ambiguous or fallback-reused slots before export."
    elif compare_entries or fallback_entries or ambiguous_slots:
        review_queue_hint = "Use Compare to clear ambiguous, fallback-reused, or upscale-risk slots before building."
    elif review_entries or weak_hidpi:
        review_queue_hint = "A normal visual pass is still recommended before export."
    elif quality_entries or pending_slots:
        review_queue_hint = "No obvious blockers. The queue is mostly clear."

    guidance_lines: list[str] = []
    if suggested_preset:
        guidance_lines.extend(
            [
                "Preset guidance:",
                f"- {suggested_preset} is the safer baseline if the current build feels too upscale-heavy.",
                "",
            ]
        )
    if mapping_error:
        guidance_lines.extend(["Configuration:", f"- Mapping error: {mapping_error}", ""])
    if size_error:
        guidance_lines.extend(["Configuration:", f"- Output sizes: {size_error}", ""])
    if pending_slots:
        preview = ", ".join(pending_slots[:4])
        if len(pending_slots) > 4:
            preview += ", ..."
        guidance_lines.extend(["Pending analysis:", f"- Preparing slot analysis for: {preview}", ""])
    if compare_entries:
        guidance_lines.append("Compare before export:")
        for slot, quality, _context in compare_entries[:8]:
            guidance_lines.append(
                f"- {slot['label']}: {quality.get('label', '--')} ({quality.get('confidence', 'low')} confidence) | {quality.get('decision', '--')}"
            )
        guidance_lines.append("")
    if redraw_entries:
        guidance_lines.append("Manual replacement / redraw queue:")
        for slot, quality, _context in redraw_entries[:6]:
            action = next(iter(quality.get("actions", [])), "Manual replacement recommended.")
            guidance_lines.append(f"- {slot['label']}: {action}")
        guidance_lines.append("")
    if fallback_entries:
        guidance_lines.append("Fallback-reused slots:")
        for slot, _quality, context in fallback_entries[:6]:
            source_slot = (context or {}).get("source_slot")
            source_label = SLOT_BY_KEY.get(source_slot, {}).get("label", source_slot or "--")
            guidance_lines.append(f"- {slot['label']}: currently reuses {source_label}")
        guidance_lines.append("")
    if review_entries:
        guidance_lines.append("Build-ready with review:")
        for slot, quality, _context in review_entries[:8]:
            guidance_lines.append(
                f"- {slot['label']}: {quality.get('label', '--')} ({quality.get('confidence', 'low')} confidence) | {quality.get('decision', '--')}"
            )
        guidance_lines.append("")
    if ambiguous_slots:
        guidance_lines.append("Ambiguous slots:")
        for slot_key in ambiguous_slots[:8]:
            guidance_lines.append(f"- {SLOT_BY_KEY.get(slot_key, {}).get('label', slot_key)}")
        guidance_lines.append("")
    if weak_hidpi or pack_warnings:
        guidance_lines.append("Pack-level watch items:")
        if weak_hidpi:
            guidance_lines.append(
                f"- HiDPI coverage is {hidpi.get('rating', 'unknown')}; larger presets may need extra compare work."
            )
        for warning in pack_warnings[:8]:
            guidance_lines.append(f"- {warning}")
        guidance_lines.append("")
    if not guidance_lines:
        guidance_lines.append("No major warnings.")
    elif guidance_lines[-1] == "":
        guidance_lines.pop()

    return ReadinessSnapshot(
        overall_quality_text=_overall_quality_text(
            quality_entries=quality_entries,
            pending_slots=pending_slots,
            selected_slot_count=selected_slot_count,
            resolved_role_count=resolved_role_count,
            mapping_error=mapping_error,
        ),
        readiness_headline=readiness_headline,
        readiness_detail=readiness_detail,
        review_queue_headline=review_queue_headline,
        review_queue_hint=review_queue_hint,
        guidance_text="\n".join(guidance_lines),
        suggested_preset=suggested_preset,
    )


def build_compare_guidance(
    mode: str,
    *,
    slot_label: str,
    current_profile_label: str,
    current_quality: dict | None,
    selection_context: dict | None,
    weak_hidpi: bool,
    is_ambiguous: bool,
    alternate_path: str | None = None,
    alternate_rank: int | None = None,
    alternate_quality: dict | None = None,
    compare_preset_label: str | None = None,
    compare_preset_quality: dict | None = None,
) -> tuple[str, str]:
    status_clauses: list[str] = []
    if selection_context and selection_context.get("origin") == "fallback":
        source_slot = selection_context.get("source_slot", "another slot")
        status_clauses.append(
            f"This slot currently reuses {SLOT_BY_KEY.get(source_slot, {}).get('label', source_slot)} as a fallback."
        )
    if is_ambiguous:
        status_clauses.append("Pack analysis marked this slot as ambiguous.")
    if current_quality and decision_lane(current_quality.get("decision")) == READINESS_COMPARE_BEFORE_EXPORT:
        status_clauses.append("The current forecast already calls for compare before export.")
    if weak_hidpi:
        status_clauses.append("Pack-wide HiDPI coverage is weak, so large outputs need extra scrutiny.")

    if mode == "Current vs Candidate":
        summary = f"Comparing the active {slot_label} assignment against a ranked alternate."
        if alternate_path:
            rank_text = f"rank #{alternate_rank}" if alternate_rank is not None else "ranked alternate"
            hint = f"Use this view to decide whether {alternate_path} should replace the current choice ({rank_text})."
        else:
            hint = "Use this view when the current slot looks ambiguous, fallback-reused, or manually overridden."
    elif mode == "Source vs Linux Output":
        summary = f"Comparing the source art against the predicted Linux output for {slot_label}."
        hint = (
            f"Use this view to validate scaling softness, frame timing, hotspot behavior, and non-square output under "
            f"the current profile ({current_profile_label})."
        )
    else:
        summary = f"Comparing the current build profile against {compare_preset_label} for {slot_label}."
        hint = (
            f"Use this view when you need a safer export baseline or want to see whether {compare_preset_label} "
            f"reduces upscale risk versus {current_profile_label}."
        )

    if current_quality and compare_preset_quality and compare_preset_label:
        hint += (
            f" Current forecast: {current_quality.get('label', '--')} ({current_quality.get('confidence', 'low')} confidence). "
            f"{compare_preset_label}: {compare_preset_quality.get('label', '--')} "
            f"({compare_preset_quality.get('confidence', 'low')} confidence)."
        )
    elif alternate_quality and alternate_path:
        hint += (
            f" Alternate forecast for {alternate_path}: {alternate_quality.get('label', '--')} "
            f"({alternate_quality.get('confidence', 'low')} confidence)."
        )

    if status_clauses:
        hint += " " + " ".join(status_clauses)
    return summary, hint
