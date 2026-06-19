import type { PageServerLoad } from './$types';
import { listProvinces } from '$lib/server/contracts';

export const load: PageServerLoad = async ({ platform }) => {
	const provinces = await listProvinces(platform);
	return { provinces };
};
