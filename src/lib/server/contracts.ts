// Server-only D1 access. The Worker reads precomputed rows; it never computes metrics here.
import { error } from '@sveltejs/kit';

export interface ContractRow {
	id: string;
	description: string | null;
	contractor: string | null;
	region: string | null;
	province: string | null;
	municipality: string | null;
	legislative_district: string | null;
	district_engineering_office: string | null;
	implementing_office: string | null;
	type_of_work: string | null;
	infra_type: string | null;
	latitude: number | null;
	longitude: number | null;
	abc: number | null;
	contract_cost: number | null;
	infra_year: number | null;
	funding_year: number | null;
	completion_year: number | null;
	bid_to_ceiling_ratio: number | null;
	risk_flags: string | null;
	risk_score: number;
}

export interface ContractorDistrictStat {
	contractor: string;
	legislative_district: string;
	contract_count: number;
	total_value: number;
	district_value_share: number;
}

function db(platform: App.Platform | undefined): D1Database {
	// Cast to the wrangler-generated global Env: App.Platform.env doesn't pick up the binding types
	// through svelte-check, but the global Env (from worker-configuration.d.ts) is correct.
	const binding = (platform?.env as Env | undefined)?.DB;
	if (!binding) {
		throw error(
			500,
			'Database not available. Run the pipeline and load D1 (see pipeline/README.md).'
		);
	}
	return binding;
}

const LIST_COLUMNS =
	'id, description, contractor, region, province, municipality, legislative_district, ' +
	'abc, contract_cost, bid_to_ceiling_ratio, risk_flags, risk_score';

export interface ListResult {
	rows: ContractRow[];
	total: number;
}

/** Riskiest-first list, optionally filtered by a free-text query and a minimum score. */
export async function listContracts(
	platform: App.Platform | undefined,
	opts: { search?: string; flaggedOnly?: boolean; limit?: number }
): Promise<ListResult> {
	const limit = Math.min(opts.limit ?? 50, 100);
	const where: string[] = [];
	const binds: unknown[] = [];

	if (opts.flaggedOnly) where.push('risk_score > 0');
	if (opts.search) {
		where.push('(contractor LIKE ?1 OR description LIKE ?1 OR legislative_district LIKE ?1)');
		binds.push(`%${opts.search}%`);
	}
	const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';

	const listSql =
		`SELECT ${LIST_COLUMNS} FROM contracts ${whereSql} ` +
		`ORDER BY risk_score DESC, contract_cost DESC LIMIT ${limit}`;
	const countSql = `SELECT COUNT(*) AS n FROM contracts ${whereSql}`;

	const conn = db(platform);
	const [list, count] = await Promise.all([
		conn
			.prepare(listSql)
			.bind(...binds)
			.all<ContractRow>(),
		conn
			.prepare(countSql)
			.bind(...binds)
			.first<{ n: number }>()
	]);

	return { rows: list.results ?? [], total: count?.n ?? 0 };
}

export async function getContract(
	platform: App.Platform | undefined,
	id: string
): Promise<ContractRow | null> {
	return db(platform)
		.prepare('SELECT * FROM contracts WHERE id = ?1')
		.bind(id)
		.first<ContractRow>();
}

/** The contractor's standing in this contract's district, for the detail page. */
export async function getDistrictStat(
	platform: App.Platform | undefined,
	contractor: string | null,
	district: string | null
): Promise<ContractorDistrictStat | null> {
	if (!contractor || !district) return null;
	return db(platform)
		.prepare(
			'SELECT * FROM contractor_district_stats WHERE contractor = ?1 AND legislative_district = ?2'
		)
		.bind(contractor, district)
		.first<ContractorDistrictStat>();
}

export interface Totals {
	contracts: number;
	flagged: number;
	totalValue: number;
}

export async function getTotals(platform: App.Platform | undefined): Promise<Totals> {
	const row = await db(platform)
		.prepare(
			'SELECT COUNT(*) AS contracts, ' +
				'SUM(CASE WHEN risk_score > 0 THEN 1 ELSE 0 END) AS flagged, ' +
				'SUM(contract_cost) AS totalValue FROM contracts'
		)
		.first<{ contracts: number; flagged: number; totalValue: number }>();
	return {
		contracts: row?.contracts ?? 0,
		flagged: row?.flagged ?? 0,
		totalValue: row?.totalValue ?? 0
	};
}
