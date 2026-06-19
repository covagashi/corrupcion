import type { PageServerLoad } from './$types';
import { getThresholdSplitting, getTotals, listProvinces } from '$lib/server/contracts';
import { getLegislatorTotals } from '$lib/server/legislators';

export const load: PageServerLoad = async ({ platform }) => {
	const [totals, provinces, years, legislators] = await Promise.all([
		getTotals(platform),
		listProvinces(platform),
		getThresholdSplitting(platform),
		getLegislatorTotals(platform)
	]);

	// Headline of the threshold-splitting metric, summed across the years we could estimate.
	const excessCount = years.reduce((s, y) => s + (y.excess_count ?? 0), 0);
	const excessValue = years.reduce((s, y) => s + (y.excess_value ?? 0), 0);

	return {
		totals,
		topProvinces: provinces.slice(0, 12),
		provinceCount: provinces.length,
		excessCount,
		excessValue,
		legislatorCount: legislators.total
	};
};
