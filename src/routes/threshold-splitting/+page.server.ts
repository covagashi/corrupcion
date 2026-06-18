import type { PageServerLoad } from './$types';
import { getThresholdSplitting } from '$lib/server/contracts';

export const load: PageServerLoad = async ({ platform }) => {
	const years = await getThresholdSplitting(platform);
	const withExcess = years.filter((y) => y.excess_count != null);
	const totalExcessCount = withExcess.reduce((s, y) => s + (y.excess_count ?? 0), 0);
	const totalExcessValue = withExcess.reduce((s, y) => s + (y.excess_value ?? 0), 0);
	return { years, totalExcessCount, totalExcessValue };
};
