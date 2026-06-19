import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getOfficial, getOfficialTerms } from '$lib/server/officials';

export const load: PageServerLoad = async ({ platform, params }) => {
	const official = await getOfficial(platform, params.id);
	if (!official) throw error(404, 'Official not found');
	const terms = await getOfficialTerms(platform, params.id);
	return { official, terms };
};
