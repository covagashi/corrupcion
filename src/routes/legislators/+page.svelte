<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { parseCongresses } from '$lib/legislators';

	let { data }: { data: PageData } = $props();

	function chamberHref(chamber: 'senate' | 'house' | null) {
		const parts: string[] = [];
		if (data.search) parts.push(`q=${encodeURIComponent(data.search)}`);
		if (chamber) parts.push(`chamber=${chamber}`);
		const qs = parts.join('&');
		return resolve(qs ? `/legislators?${qs}` : '/legislators');
	}

	// Latest congress + chamber, for the one-line summary on each row.
	function latest(congresses: string | null) {
		const list = parseCongresses(congresses);
		return list.length ? list[list.length - 1] : null;
	}
</script>

<svelte:head>
	<title>Legislators — Philippine senators and representatives</title>
	<meta
		name="description"
		content="Directory of Philippine senators and representatives and the congresses they served in, from the community-maintained Open Congress dataset."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/')} class="inline-block py-4 text-sm text-blue-700 underline">← Home</a>

	<header class="pb-2">
		<h1 class="text-xl font-bold text-slate-900">Legislators</h1>
		<p class="mt-1 text-sm text-slate-600">
			{data.totals.total.toLocaleString()} senators and representatives across the 8th–20th Congress.
			Search by name, or filter by chamber.
		</p>
	</header>

	<form method="GET" class="mb-3 flex gap-2">
		<input
			type="search"
			name="q"
			value={data.search}
			placeholder="Search a legislator by name…"
			class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
		/>
		{#if data.chamber}<input type="hidden" name="chamber" value={data.chamber} />{/if}
		<button class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white">Search</button>
	</form>

	<div class="mb-4 flex gap-2 text-sm">
		<a
			href={chamberHref(null)}
			class="rounded-full border px-3 py-1 {data.chamber === null
				? 'border-slate-900 bg-slate-900 text-white'
				: 'border-slate-300 text-slate-700'}">All</a
		>
		<a
			href={chamberHref('senate')}
			class="rounded-full border px-3 py-1 {data.chamber === 'senate'
				? 'border-slate-900 bg-slate-900 text-white'
				: 'border-slate-300 text-slate-700'}">Senate</a
		>
		<a
			href={chamberHref('house')}
			class="rounded-full border px-3 py-1 {data.chamber === 'house'
				? 'border-slate-900 bg-slate-900 text-white'
				: 'border-slate-300 text-slate-700'}">House</a
		>
		<span class="ml-auto self-center text-slate-500">{data.matched.toLocaleString()} match</span>
	</div>

	<ul class="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
		{#each data.legislators as l (l.id)}
			{@const last = latest(l.congresses)}
			<li>
				<a
					href={resolve('/legislator/[id]', { id: l.id })}
					class="flex items-center justify-between gap-3 p-3 active:bg-slate-50"
				>
					<span class="min-w-0">
						<span class="block truncate text-sm font-semibold text-slate-900">{l.full_name}</span>
						<span class="mt-0.5 block text-xs text-slate-500">
							{l.positions ?? '—'}
							{#if last}· last served {last.ordinal} Congress ({last.chamber}){/if}
						</span>
					</span>
					<span class="shrink-0 text-slate-400">→</span>
				</a>
			</li>
		{:else}
			<li class="p-6 text-center text-sm text-slate-500">
				No legislators match. (If this is empty everywhere, the data is not loaded yet — see
				<code>docs/deploy.md</code>.)
			</li>
		{/each}
	</ul>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: Open Congress (community-maintained, from senate.gov.ph and congress.gov.ph). The
		dataset records chambers served, not electoral districts, so legislators are not linked to
		contracts by area here.
		<a href={resolve('/methodology')} class="text-blue-700 underline">About the data</a>.
	</footer>
</main>
