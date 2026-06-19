// Server-only D1 access for the legislators directory (Phase 4 — politicians).
// Rows are precomputed by pipeline/congress.py from the Open Congress dataset. The source has no
// geographic district, so legislators are not joined to contracts by area.
import { error } from '@sveltejs/kit';

export type { CongressServed } from '$lib/legislators';

export interface LegislatorRow {
	id: string;
	full_name: string;
	first_name: string | null;
	last_name: string | null;
	positions: string | null;
	is_senator: number;
	is_rep: number;
	congresses: string | null; // JSON array of CongressServed
	first_congress: number | null;
	latest_congress: number | null;
	aliases: string | null; // JSON array of strings
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

export interface LegislatorListResult {
	rows: LegislatorRow[];
	total: number;
}

/** Directory list — by name, optionally filtered by a free-text query and chamber. */
export async function listLegislators(
	platform: App.Platform | undefined,
	opts: { search?: string; chamber?: 'senate' | 'house'; limit?: number }
): Promise<LegislatorListResult> {
	const limit = Math.min(opts.limit ?? 60, 100);
	const where: string[] = [];
	const binds: unknown[] = [];

	if (opts.chamber === 'senate') where.push('is_senator = 1');
	else if (opts.chamber === 'house') where.push('is_rep = 1');

	if (opts.search) {
		const p = `?${binds.length + 1}`;
		where.push(`(full_name LIKE ${p} OR aliases LIKE ${p})`);
		binds.push(`%${opts.search}%`);
	}
	const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';

	const listSql =
		'SELECT id, full_name, positions, is_senator, is_rep, congresses, first_congress, ' +
		`latest_congress, aliases FROM legislators ${whereSql} ` +
		`ORDER BY latest_congress DESC, last_name ASC LIMIT ${limit}`;
	const countSql = `SELECT COUNT(*) AS n FROM legislators ${whereSql}`;

	const conn = db(platform);
	const [list, count] = await Promise.all([
		conn
			.prepare(listSql)
			.bind(...binds)
			.all<LegislatorRow>(),
		conn
			.prepare(countSql)
			.bind(...binds)
			.first<{ n: number }>()
	]);

	return { rows: list.results ?? [], total: count?.n ?? 0 };
}

export async function getLegislator(
	platform: App.Platform | undefined,
	id: string
): Promise<LegislatorRow | null> {
	return db(platform)
		.prepare('SELECT * FROM legislators WHERE id = ?1')
		.bind(id)
		.first<LegislatorRow>();
}

export interface LegislatorTotals {
	total: number;
	senators: number;
	representatives: number;
}

export async function getLegislatorTotals(
	platform: App.Platform | undefined
): Promise<LegislatorTotals> {
	const row = await db(platform)
		.prepare(
			'SELECT COUNT(*) AS total, ' +
				'SUM(is_senator) AS senators, SUM(is_rep) AS representatives FROM legislators'
		)
		.first<{ total: number; senators: number; representatives: number }>();
	return {
		total: row?.total ?? 0,
		senators: row?.senators ?? 0,
		representatives: row?.representatives ?? 0
	};
}
