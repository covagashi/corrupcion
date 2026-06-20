import type { PageServerLoad } from './$types';
import { getTotals, listContracts } from '$lib/server/contracts';

export const load: PageServerLoad = async ({ platform, url }) => {
	const search = url.searchParams.get('q')?.trim() || '';
	const flaggedOnly = url.searchParams.get('all') !== '1';
	const source = url.searchParams.get('source') as 'flood_control' | 'philgeps' | 'dpwh' | null;
	const province = url.searchParams.get('province')?.trim() || '';

	const [totals, result] = await Promise.all([
		getTotals(platform),
		listContracts(platform, {
			search,
			flaggedOnly,
			limit: 50,
			source: source ?? undefined,
			province: province || undefined
		})
	]);

	return {
		totals,
		contracts: result.rows,
		matched: result.total,
		search,
		flaggedOnly,
		source,
		province
	};
};
