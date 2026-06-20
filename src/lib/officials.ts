// Shared (client + server) types and helpers for public officials (Phase 4 alignment).
// DB access is in $lib/server/officials.ts; these helpers carry no secrets.

export interface OfficialTerm {
	id: string;
	person_id: string;
	full_name: string | null;
	party: string | null;
	region: string | null;
	province: string | null;
	locality: string | null;
	position: string | null;
	year: number | null;
}

/**
 * Normalize a place name for matching. MUST stay identical to normalize_place in
 * pipeline/officials.py, or the contract↔official join silently misses.
 */
export function normalizePlace(value: string | null | undefined): string | null {
	if (value == null) return null;
	const s = value.trim().toLowerCase().replace(/\s+/g, ' ');
	return s || null;
}

export function parseList(raw: string | null | undefined): string[] {
	if (!raw) return [];
	try {
		return JSON.parse(raw) as string[];
	} catch {
		return [];
	}
}

// Roughly rank offices so the most relevant local leaders surface first in the area panel.
const POSITION_RANK: Record<string, number> = {
	governor: 0,
	'vice governor': 1,
	representative: 2,
	'board member': 3,
	mayor: 4,
	'vice mayor': 5,
	councilor: 6
};

export function positionRank(position: string | null): number {
	if (!position) return 99;
	return POSITION_RANK[position.trim().toLowerCase()] ?? 50;
}
