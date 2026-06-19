// Shared (client + server) types and pure parsers for the legislators directory.
// DB access lives in $lib/server/legislators.ts; these helpers carry no secrets so the UI can use them.

export interface CongressServed {
	number: number;
	ordinal: string;
	chamber: string; // "Senate" | "House"
}

export function parseCongresses(raw: string | null | undefined): CongressServed[] {
	if (!raw) return [];
	try {
		return JSON.parse(raw) as CongressServed[];
	} catch {
		return [];
	}
}

export function parseAliases(raw: string | null | undefined): string[] {
	if (!raw) return [];
	try {
		return JSON.parse(raw) as string[];
	} catch {
		return [];
	}
}
