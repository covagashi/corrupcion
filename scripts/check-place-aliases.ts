// Asserts the TS canonicalizers match pipeline/test/place-cases.json (the same
// fixture the Python test uses), so the Python/TS pair cannot silently drift.
// Run: npx tsx scripts/check-place-aliases.ts
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { normalizeProvince, normalizeLocality } from '../src/lib/officials.ts';

const casesPath = fileURLToPath(new URL('../pipeline/test/place-cases.json', import.meta.url));
const cases = JSON.parse(readFileSync(casesPath, 'utf-8')) as {
	province: { value: string | null; key: string | null }[];
	locality: { value: string | null; key: string | null }[];
};

const failures: string[] = [];
for (const c of cases.province) {
	const got = normalizeProvince(c.value);
	if (got !== c.key)
		failures.push(
			`province ${JSON.stringify(c.value)}: got ${JSON.stringify(got)}, want ${JSON.stringify(c.key)}`
		);
}
for (const c of cases.locality) {
	const got = normalizeLocality(c.value);
	if (got !== c.key)
		failures.push(
			`locality ${JSON.stringify(c.value)}: got ${JSON.stringify(got)}, want ${JSON.stringify(c.key)}`
		);
}

if (failures.length) {
	console.error(failures.join('\n'));
	process.exit(1);
}
console.log(`OK: ${cases.province.length + cases.locality.length} cases passed`);
