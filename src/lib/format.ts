// Display helpers. Money in this dataset is Philippine pesos (₱).

const PESO = new Intl.NumberFormat('en-PH', {
	style: 'currency',
	currency: 'PHP',
	maximumFractionDigits: 0
});

export function peso(value: number | null | undefined): string {
	if (value == null) return '—';
	return PESO.format(value);
}

/** Compact pesos for tight mobile rows, e.g. "₱17.9M". */
export function pesoShort(value: number | null | undefined): string {
	if (value == null) return '—';
	if (value >= 1e9) return `₱${(value / 1e9).toFixed(1)}B`;
	if (value >= 1e6) return `₱${(value / 1e6).toFixed(1)}M`;
	if (value >= 1e3) return `₱${Math.round(value / 1e3)}K`;
	return `₱${Math.round(value)}`;
}

export function percent(ratio: number | null | undefined): string {
	if (ratio == null) return '—';
	return `${(ratio * 100).toFixed(1)}%`;
}
