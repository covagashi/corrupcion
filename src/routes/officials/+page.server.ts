import type { PageServerLoad } from './$types';
import { listOfficials } from '$lib/server/officials';

export const load: PageServerLoad = async ({ platform, url }) => {
	const search = url.searchParams.get('q')?.trim() || '';
	const result = await listOfficials(platform, { search, limit: 60 });
	return { officials: result.rows, matched: result.total, search };
};
