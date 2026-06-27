// Server-only D1 access for PCAB company licenses + the Phase 4 surname-overlap alignment.
// Rows are precomputed by pipeline/pcab.py. The Worker only reads them.
import { error } from '@sveltejs/kit';
import { normalizeProvince } from '$lib/officials';

export interface PcabLicenseRow {
	id: string | null;
	license_no: string | null;
	contractor_name: string;
	contractor_key: string;
	amo_owner: string | null;
	owner_surname: string | null;
	category: string | null;
	valid_to: string | null;
	gov_registered: number | null;
}

export interface PcabSuspendedRow {
	id: string | null;
	contractor_name: string;
	license_no: string | null;
	status: string | null;
	valid_from: string | null;
	valid_to: string | null;
	reason: string | null;
}

export interface CompanyInfo {
	license: PcabLicenseRow | null;
	suspended: PcabSuspendedRow | null;
	/** The surname to match against officials/legislators, from the license owner when present. */
	ownerSurname: string | null;
}

function db(platform: App.Platform | undefined): D1Database {
	const binding = (platform?.env as Env | undefined)?.DB;
	if (!binding) {
		throw error(
			500,
			'Database not available. Run the pipeline and load D1 (see pipeline/README.md).'
		);
	}
	return binding;
}

const NON_ALNUM = /[^A-Z0-9]+/g;

/**
 * Normalize a contractor name for matching PCAB rows. Must stay identical to
 * normalize_company_key in pipeline/pcab.py — uppercased alphanumerics, single-spaced.
 */
export function normalizeCompanyKey(name: string | null | undefined): string | null {
	if (!name) return null;
	const s = name.toUpperCase().replace(NON_ALNUM, ' ').trim().replace(/\s+/g, ' ');
	return s || null;
}

const PARTICLES = new Set([
	'de',
	'del',
	'dela',
	'la',
	'las',
	'lo',
	'los',
	'y',
	'mac',
	'mc',
	'saint',
	'san',
	'santo',
	'sta',
	'sto'
]);
const SUFFIXES = new Set(['JR', 'SR', 'II', 'III', 'IV']);

/**
 * Surname of an AMO owner string. Mirror of surname_of in pipeline/pcab.py — drop generational
 * suffix and any particle attached to the last token. Used when the license row had no AMO
 * (legacy rows) and for the officials-leg surname query we build below.
 */
export function surnameOf(amo: string | null | undefined): string | null {
	if (!amo) return null;
	const s = amo.replace(/[^A-Za-z -]/g, '').trim();
	if (!s) return null;
	let tokens = s.split(/\s+/).filter(Boolean);
	if (tokens.length === 0) return null;
	while (tokens.length && SUFFIXES.has(tokens[tokens.length - 1].toUpperCase())) {
		tokens.pop();
	}
	while (tokens.length >= 2 && PARTICLES.has(tokens[tokens.length - 2].toLowerCase())) {
		tokens = [...tokens.slice(0, -2), tokens[tokens.length - 1]];
	}
	if (tokens.length === 0) return null;
	return tokens[tokens.length - 1].toUpperCase() || null;
}

export async function getCompanyInfo(
	platform: App.Platform | undefined,
	contractor: string | null | undefined
): Promise<CompanyInfo> {
	const key = normalizeCompanyKey(contractor);
	if (!key) return { license: null, suspended: null, ownerSurname: null };
	const conn = db(platform);
	const [license, suspended] = await Promise.all([
		conn
			.prepare(
				'SELECT id, license_no, contractor_name, contractor_key, amo_owner, owner_surname, ' +
					'category, valid_to, gov_registered FROM pcab_licenses WHERE contractor_key = ?1 LIMIT 1'
			)
			.bind(key)
			.first<PcabLicenseRow>(),
		conn
			.prepare(
				'SELECT id, contractor_name, license_no, status, valid_from, valid_to, reason ' +
					'FROM pcab_suspended WHERE contractor_key = ?1 LIMIT 1'
			)
			.bind(key)
			.first<PcabSuspendedRow>()
	]);
	const ownerSurname = license?.owner_surname ?? surnameOf(license?.amo_owner);
	return { license, suspended, ownerSurname };
}

export interface SurnameOverlap {
	person_id: string;
	full_name: string | null;
	position: string | null;
	party: string | null;
	year: number | null;
	locality: string | null;
	scope: 'area_official' | 'legislator';
	roles: string | null; // "Senator, Representative" for legislators
}

/**
 * Phase 4 "owners" leg alignment: who in the contract's area (or among national legislators)
 * shares a surname with the contractor's disclosed AMO owner. Pure surname overlap is a *signal*,
 * not proof — the methodology page says so plainly. Returns area officials first, then any
 * national legislator with the same surname.
 */
export async function getSurnameOverlaps(
	platform: App.Platform | undefined,
	opts: {
		surname: string | null;
		province: string | null | undefined;
		locality?: string | null | undefined;
	}
): Promise<SurnameOverlap[]> {
	if (!opts.surname || opts.surname.length < 3) return []; // 2-letter surnames = too noisy
	const conn = db(platform);
	const pkey = normalizeProvince(opts.province);
	const out: SurnameOverlap[] = [];

	if (pkey) {
		// Officials in this province whose last name matches the AMO surname. Capped, best-year first.
		const res = await conn
			.prepare(
				'SELECT person_id, full_name, position, party, year, locality, locality_key ' +
					'FROM official_terms WHERE province_key = ?1 ' +
					'AND full_name LIKE ?2 ' +
					'ORDER BY year DESC LIMIT 40'
			)
			.bind(pkey, `% ${opts.surname}%`)
			.all<SurnameOverlap & { locality_key: string | null }>();
		const seen = new Set<string>();
		for (const t of res.results ?? []) {
			const k = `${t.person_id}|${(t.position ?? '').toLowerCase()}`;
			if (seen.has(k)) continue;
			seen.add(k);
			out.push({
				person_id: t.person_id,
				full_name: t.full_name,
				position: t.position,
				party: t.party,
				year: t.year,
				locality: t.locality,
				scope: 'area_official',
				roles: null
			});
		}
	}

	// National legislators (senators / representatives) with the same surname — no province key on
	// the legislators table, so this is a nationwide overlap. Best-year first.
	const leg = await conn
		.prepare(
			'SELECT id, full_name, positions, latest_year FROM legislators ' +
				'WHERE last_name LIKE ?1 ORDER BY latest_year DESC LIMIT 20'
		)
		.bind(`${opts.surname}%`)
		.all<{
			id: string;
			full_name: string | null;
			positions: string | null;
			latest_year: number | null;
		}>();
	for (const l of leg.results ?? []) {
		out.push({
			person_id: l.id,
			full_name: l.full_name,
			position: null,
			party: null,
			year: l.latest_year,
			locality: null,
			scope: 'legislator',
			roles: l.positions
		});
	}

	// De-dup a person who shows up both as an area official and as a legislator.
	const uniq = new Map<string, SurnameOverlap>();
	for (const o of out) uniq.set(`${o.scope}|${o.person_id}`, o);
	return [...uniq.values()].slice(0, 12);
}
