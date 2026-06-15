import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getContract, getDistrictStat } from '$lib/server/contracts';

export const load: PageServerLoad = async ({ platform, params }) => {
	const contract = await getContract(platform, params.id);
	if (!contract) throw error(404, 'Contract not found');

	const districtStat = await getDistrictStat(
		platform,
		contract.contractor,
		contract.legislative_district
	);

	return { contract, districtStat };
};
