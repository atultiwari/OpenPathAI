// Phase 21 — shared Tier + Mode badges. Used across Train / Analyse /
// Slides / Annotate so a pathologist can see at a glance which Phase-17
// run mode and difficulty preset is active.

import type { RunMode, TierLevel } from "../api/types";

interface TierBadgeProps {
  tier: TierLevel;
}

const TIER_DETAILS: Record<TierLevel, { label: string; hint: string; color: string }> = {
  Easy: { label: "Easy", hint: "minimal hparams", color: "var(--tier-easy, #16a34a)" },
  Standard: {
    label: "Standard",
    hint: "Lightning defaults",
    color: "var(--tier-standard, #2563eb)",
  },
  Expert: {
    label: "Expert",
    hint: "full hyper-parameter surface",
    color: "var(--tier-expert, #b45309)",
  },
};

export function TierBadge({ tier }: TierBadgeProps) {
  const meta = TIER_DETAILS[tier];
  return (
    <span
      className="tier-badge"
      role="img"
      aria-label={`Tier: ${meta.label}`}
      title={meta.hint}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: ".25rem",
        padding: "0.15rem 0.5rem",
        borderRadius: "0.5rem",
        background: `color-mix(in oklab, ${meta.color} 12%, transparent)`,
        color: meta.color,
        fontWeight: 600,
        fontSize: "0.75rem",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    >
      <span aria-hidden>◆</span>
      {meta.label}
    </span>
  );
}

interface ModeBadgeProps {
  mode: RunMode;
}

const MODE_DETAILS: Record<RunMode, { label: string; hint: string; color: string }> = {
  exploratory: {
    label: "Exploratory",
    hint: "no signed manifest required",
    color: "var(--mode-explore, #6366f1)",
  },
  diagnostic: {
    label: "Diagnostic",
    hint: "pinned commits + signed manifest",
    color: "var(--mode-diagnostic, #be185d)",
  },
};

export function ModeBadge({ mode }: ModeBadgeProps) {
  const meta = MODE_DETAILS[mode];
  return (
    <span
      className="mode-badge"
      role="img"
      aria-label={`Mode: ${meta.label}`}
      title={meta.hint}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: ".25rem",
        padding: "0.15rem 0.5rem",
        borderRadius: "0.5rem",
        background: `color-mix(in oklab, ${meta.color} 12%, transparent)`,
        color: meta.color,
        fontWeight: 600,
        fontSize: "0.75rem",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    >
      <span aria-hidden>◇</span>
      {meta.label}
    </span>
  );
}

interface BadgeStripProps {
  tier?: TierLevel;
  mode?: RunMode;
}

/**
 * Convenience composer — useful in screen headers where both badges
 * commonly appear next to each other.
 */
export function BadgeStrip({ tier, mode }: BadgeStripProps) {
  return (
    <span className="badge-strip" style={{ display: "inline-flex", gap: ".4rem" }}>
      {tier ? <TierBadge tier={tier} /> : null}
      {mode ? <ModeBadge mode={mode} /> : null}
    </span>
  );
}
