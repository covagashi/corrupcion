// Server-only D1 access for the Ateneo Political Dynasties dataset. Phase 4 — dynasties leg.
// Rows are precomputed by pipeline/dynasties.py from the local xlsx; the Worker only reads.
import { error } from '@sveltejs/kit';
import { normalizeProvince } from '$lib/officials';

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

const ELECTION_YEARS = [1992, 1995, 1998, 2001, 2004, 2007, 2010, 2013, 2016, 2019, 2022];

export interface DynastyShareRow {
	province_key: string;
	province: string;
	year: number;
	share: number;
}

export interface DynastyContext {
	/** The fat-dynasty percentage in this province, at the election year closest to the contract. */
	share: DynastyShareRow | null;
	/** The national average fat-dynasty share at that same election year (for context: is this
	 * province above/below the Philippine mean?). */
	nationalAverage: number | null;
	/** Headline counts at the chosen election year for this province: number of fat-dynasty vs
	 * total politicians. */
	fatCount: number;
	totalCount: number;
}

function nearestElectionYear(year: number | null): number {
	if (!year) return ELECTION_YEARS[ELECTION_YEARS.length - 1];
	let best = ELECTION_YEARS[0];
	let bestD = Math.abs(year - best);
	for (const y of ELECTION_YEARS) {
		const d = Math.abs(year - y);
		if (d < bestD) {
			best = y;
			bestD = d;
		}
	}
	return best;
}

export async function getDynastyContext(
	platform: App.Platform | undefined,
	opts: { province: string | null | undefined; year?: number | null }
): Promise<DynastyContext> {
	const pkey = normalizeProvince(opts.province);
	const refYear = nearestElectionYear(opts.year ?? null);
	if (!pkey) {
		return { share: null, nationalAverage: null, fatCount: 0, totalCount: 0 };
	}
	const conn = db(platform);

	// Province share row for the nearest election year.
	const share = await conn
		.prepare(
			'SELECT province_key, province, year, share FROM dynasty_shares WHERE province_key = ?1 AND year = ?2'
		)
		.bind(pkey, refYear)
		.first<DynastyShareRow>();

	// National average at that year — a single row aggregate.
	const nat = await conn
		.prepare('SELECT AVG(share) AS avg FROM dynasty_shares WHERE year = ?1')
		.bind(refYear)
		.first<{ avg: number | null }>();
	const nationalAverage = nat?.avg ?? null;

	// Headline counts: fat-dynasty vs total politicians in this province at the chosen year. The
	// Ateneo dataset breaks the share down to the actual rows behind it (its sample is local politicians
	// holding office that year).
	const counts = await conn
		.prepare(
			'SELECT ' +
				'COUNT(*) AS total, ' +
				'SUM(CASE WHEN is_fat = 1 THEN 1 ELSE 0 END) AS fat ' +
				'FROM dynasty_politicians WHERE province_key = ?1 AND year = ?2'
		)
		.bind(pkey, refYear)
		.first<{ total: number | null; fat: number | null }>();

	return {
		share,
		nationalAverage,
		fatCount: counts?.fat ?? 0,
		totalCount: counts?.total ?? 0
	};
}

export async function listProvincesWithDynastyShare(
	platform: App.Platform | undefined
): Promise<DynastyShareRow[]> {
	const res = await db(platform)
		.prepare(
			'SELECT province_key, province, year, share FROM dynasty_shares ORDER BY share DESC LIMIT 100'
		)
		.all<DynastyShareRow>();
	return res.results ?? [];
}
