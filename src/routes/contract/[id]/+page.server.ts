import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getContract, getDistrictStat } from '$lib/server/contracts';
import { getAreaOfficials } from '$lib/server/officials';

export const load: PageServerLoad = async ({ platform, params }) => {
	const contract = await getContract(platform, params.id);
	if (!contract) throw error(404, 'Contract not found');

	// The year to centre the "who held office here" lookup on — whichever the source carries.
	const year =
		contract.infra_year ??
		contract.funding_year ??
		contract.completion_year ??
		(contract.award_date ? new Date(contract.award_date).getUTCFullYear() : null);

	const [districtStat, areaOfficials] = await Promise.all([
		getDistrictStat(platform, contract.contractor, contract.legislative_district),
		getAreaOfficials(platform, {
			province: contract.province,
			locality: contract.municipality,
			year
		})
	]);

	return { contract, districtStat, areaOfficials, areaYear: year };
};
