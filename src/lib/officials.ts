// Shared (client + server) types and helpers for public officials (Phase 4 alignment).
// DB access is in $lib/server/officials.ts; these helpers carry no secrets.

import aliases from './place-aliases.json';

const PROVINCE_ALIASES = aliases.provinceAliases as Record<string, string>;
const LOCALITY_PREFIXES = aliases.localityPrefixes as string[];
const LOCALITY_ABBREV = aliases.localityAbbrev as Record<string, string>;

const PAREN = /\s*\([^)]*\)/g;

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

function stripParen(s: string): string {
	return s.replace(PAREN, '').replace(/\s+/g, ' ').trim();
}

/** Province key: base → drop parentheticals → province alias. Mirror of normalize_province (Python). */
export function normalizeProvince(value: string | null | undefined): string | null {
	const base = normalizePlace(value);
	if (base == null) return null;
	const s = stripParen(base);
	if (!s) return null;
	return PROVINCE_ALIASES[s] ?? s;
}

/** Locality key: base → drop parentheticals/prefix/trailing " city" → expand abbrev. Mirror of normalize_locality (Python). */
export function normalizeLocality(value: string | null | undefined): string | null {
	const base = normalizePlace(value);
	if (base == null) return null;
	let s = stripParen(base);
	for (const prefix of LOCALITY_PREFIXES) {
		if (s.startsWith(prefix)) {
			s = s.slice(prefix.length);
			break;
		}
	}
	if (s.endsWith(' city')) s = s.slice(0, -' city'.length);
	const sp = s.indexOf(' ');
	const first = sp === -1 ? s : s.slice(0, sp);
	if (LOCALITY_ABBREV[first]) {
		s = sp === -1 ? LOCALITY_ABBREV[first] : `${LOCALITY_ABBREV[first]}${s.slice(sp)}`;
	}
	s = s.replace(/\s+/g, ' ').trim();
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
