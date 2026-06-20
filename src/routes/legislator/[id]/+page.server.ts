import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getLegislator } from '$lib/server/legislators';

export const load: PageServerLoad = async ({ platform, params }) => {
	const legislator = await getLegislator(platform, params.id);
	if (!legislator) throw error(404, 'Legislator not found');
	return { legislator };
};
