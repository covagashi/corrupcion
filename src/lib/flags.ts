// Plain-language metadata for each risk flag. The codes and weights mirror pipeline/transform.py;
// keep them in sync. Used by both the list and detail pages — explain every flag in one sentence.

export type FlagCode = 'OVER_CEILING' | 'EXACT_CEILING' | 'NEAR_CEILING' | 'DISTRICT_DOMINANCE';

export interface FlagInfo {
	label: string;
	/** One sentence a non-expert understands. */
	explanation: string;
	weight: number;
	severity: 'high' | 'medium' | 'low';
}

export const FLAGS: Record<FlagCode, FlagInfo> = {
	OVER_CEILING: {
		label: 'Awarded above the budget ceiling',
		explanation:
			'The contract was awarded for more than the government’s own approved budget — by law the winning bid should never exceed it.',
		weight: 40,
		severity: 'high'
	},
	DISTRICT_DOMINANCE: {
		label: 'One contractor dominates the district',
		explanation:
			'This contractor won at least half of all flood-control money in its legislative district across three or more contracts, pointing to weak competition.',
		weight: 30,
		severity: 'high'
	},
	EXACT_CEILING: {
		label: 'Bid matched the ceiling almost exactly',
		explanation:
			'The winning bid landed within 0.01% of the secret budget ceiling — suspiciously precise for a competitive bid.',
		weight: 15,
		severity: 'medium'
	},
	NEAR_CEILING: {
		label: 'Bid sat right at the ceiling',
		explanation:
			'The winning bid used up 99% or more of the approved budget, leaving the government almost no savings.',
		weight: 5,
		severity: 'low'
	}
};

export function parseFlags(raw: string | null | undefined): FlagCode[] {
	if (!raw) return [];
	try {
		return (JSON.parse(raw) as string[]).filter((c): c is FlagCode => c in FLAGS);
	} catch {
		return [];
	}
}

export function riskLabel(score: number): string {
	if (score >= 60) return 'High concern';
	if (score >= 30) return 'Notable concern';
	if (score > 0) return 'Worth a look';
	return 'No flags';
}
