import type { PageServerLoad } from './$types';
import { getLegislatorTotals, listLegislators } from '$lib/server/legislators';

export const load: PageServerLoad = async ({ platform, url }) => {
	const search = url.searchParams.get('q')?.trim() || '';
	const chamberParam = url.searchParams.get('chamber');
	const chamber = chamberParam === 'senate' || chamberParam === 'house' ? chamberParam : null;

	const [totals, result] = await Promise.all([
		getLegislatorTotals(platform),
		listLegislators(platform, { search, chamber: chamber ?? undefined, limit: 60 })
	]);

	return { totals, legislators: result.rows, matched: result.total, search, chamber };
};
