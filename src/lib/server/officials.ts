// Server-only D1 access for public officials + the contract↔official area alignment.
// Rows are precomputed by pipeline/officials.py from the Raw Philippine Data persons/memberships.
import { error } from '@sveltejs/kit';
import {
	normalizeProvince,
	normalizeLocality,
	positionRank,
	type OfficialTerm
} from '$lib/officials';

export interface OfficialRow {
	id: string;
	full_name: string;
	first_name: string | null;
	last_name: string | null;
	name_suffix: string | null;
	term_count: number;
	latest_year: number | null;
	positions: string | null; // JSON array
	parties: string | null; // JSON array
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

export interface OfficialListResult {
	rows: OfficialRow[];
	total: number;
}

/** Directory list — by name, optionally filtered by a free-text query. */
export async function listOfficials(
	platform: App.Platform | undefined,
	opts: { search?: string; limit?: number }
): Promise<OfficialListResult> {
	const limit = Math.min(opts.limit ?? 60, 100);
	const where: string[] = [];
	const binds: unknown[] = [];

	if (opts.search) {
		where.push(`full_name LIKE ?${binds.length + 1}`);
		binds.push(`%${opts.search}%`);
	}
	const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';

	const listSql =
		'SELECT id, full_name, term_count, latest_year, positions, parties ' +
		`FROM officials ${whereSql} ORDER BY latest_year DESC, last_name ASC LIMIT ${limit}`;
	const countSql = `SELECT COUNT(*) AS n FROM officials ${whereSql}`;

	const conn = db(platform);
	const [list, count] = await Promise.all([
		conn
			.prepare(listSql)
			.bind(...binds)
			.all<OfficialRow>(),
		conn
			.prepare(countSql)
			.bind(...binds)
			.first<{ n: number }>()
	]);

	return { rows: list.results ?? [], total: count?.n ?? 0 };
}

export async function getOfficialCount(platform: App.Platform | undefined): Promise<number> {
	const row = await db(platform)
		.prepare('SELECT COUNT(*) AS n FROM officials')
		.first<{ n: number }>();
	return row?.n ?? 0;
}

export async function getOfficial(
	platform: App.Platform | undefined,
	id: string
): Promise<OfficialRow | null> {
	return db(platform)
		.prepare('SELECT * FROM officials WHERE id = ?1')
		.bind(id)
		.first<OfficialRow>();
}

/** Every term a single official held, newest first — for their profile page. */
export async function getOfficialTerms(
	platform: App.Platform | undefined,
	personId: string
): Promise<OfficialTerm[]> {
	const res = await db(platform)
		.prepare(
			'SELECT id, person_id, full_name, party, region, province, locality, position, year ' +
				'FROM official_terms WHERE person_id = ?1 ORDER BY year DESC, position ASC'
		)
		.bind(personId)
		.all<OfficialTerm>();
	return res.results ?? [];
}

export interface AreaOfficial {
	person_id: string;
	full_name: string | null;
	position: string | null;
	party: string | null;
	year: number | null;
	locality: string | null;
}

export interface AreaOfficials {
	provinceWide: AreaOfficial[];
	local: AreaOfficial[];
}

/**
 * Who held office in a contract's area, near its year. Province-wide offices (governor,
 * representative, board member — locality is blank) are matched on the province; local offices
 * (mayor, councilor) on the municipality. We keep the single best term per person+position
 * (closest year to the contract's), so a long career collapses to one relevant line.
 */
export async function getAreaOfficials(
	platform: App.Platform | undefined,
	opts: { province: string | null; locality?: string | null; year?: number | null }
): Promise<AreaOfficials> {
	const pkey = normalizeProvince(opts.province);
	if (!pkey) return { provinceWide: [], local: [] };
	const lkey = normalizeLocality(opts.locality);
	const ref = opts.year ?? null;

	// Pull all terms in the province (province-wide rows have province_key set). Capped — a
	// province has at most a few thousand membership rows across all years.
	const res = await db(platform)
		.prepare(
			'SELECT person_id, full_name, party, position, year, locality, locality_key ' +
				'FROM official_terms WHERE province_key = ?1 ORDER BY year DESC LIMIT 2000'
		)
		.bind(pkey)
		.all<AreaOfficial & { locality_key: string | null }>();
	const terms = res.results ?? [];

	const pick = (rows: typeof terms): AreaOfficial[] => {
		// best term per person+position by closeness to the reference year
		const best = new Map<string, AreaOfficial & { locality_key: string | null }>();
		for (const t of rows) {
			const key = `${t.person_id}|${(t.position ?? '').toLowerCase()}`;
			const cur = best.get(key);
			if (!cur) {
				best.set(key, t);
				continue;
			}
			const d = ref != null && t.year != null ? Math.abs(t.year - ref) : Number.MAX_SAFE_INTEGER;
			const dCur =
				ref != null && cur.year != null ? Math.abs(cur.year - ref) : Number.MAX_SAFE_INTEGER;
			if (d < dCur) best.set(key, t);
		}
		return [...best.values()]
			.sort(
				(a, b) =>
					positionRank(a.position) - positionRank(b.position) || (b.year ?? 0) - (a.year ?? 0)
			)
			.slice(0, 8)
			.map((t) => ({
				person_id: t.person_id,
				full_name: t.full_name,
				position: t.position,
				party: t.party,
				year: t.year,
				locality: t.locality
			}));
	};

	const provinceWide = pick(terms.filter((t) => !t.locality_key));
	const local = lkey ? pick(terms.filter((t) => t.locality_key === lkey)) : [];
	return { provinceWide, local };
}
