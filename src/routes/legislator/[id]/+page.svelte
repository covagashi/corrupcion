<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { parseAliases, parseCongresses } from '$lib/legislators';

	let { data }: { data: PageData } = $props();
	const l = $derived(data.legislator);
	const congresses = $derived(parseCongresses(l.congresses).slice().reverse()); // newest first
	const aliases = $derived(parseAliases(l.aliases));
</script>

<svelte:head>
	<title>{l.full_name} — legislator</title>
	<meta name="description" content="{l.full_name}: {l.positions ?? 'Philippine legislator'}." />
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/legislators')} class="inline-block py-4 text-sm text-blue-700 underline"
		>← All legislators</a
	>

	<header>
		<h1 class="text-lg font-bold text-slate-900">{l.full_name}</h1>
		{#if l.positions}<p class="mt-1 text-sm text-slate-600">{l.positions}</p>{/if}
		{#if aliases.length}
			<p class="mt-1 text-xs text-slate-500">Also known as: {aliases.join(', ')}</p>
		{/if}
	</header>

	<section class="mt-6">
		<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">Congresses served</h2>
		{#if congresses.length}
			<ul class="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
				{#each congresses as c (c.number)}
					<li class="flex items-center justify-between p-3 text-sm">
						<span class="font-medium text-slate-900">{c.ordinal} Congress</span>
						<span
							class="rounded-full px-2 py-0.5 text-xs font-medium"
							class:bg-purple-100={c.chamber === 'Senate'}
							class:text-purple-800={c.chamber === 'Senate'}
							class:bg-emerald-100={c.chamber === 'House'}
							class:text-emerald-800={c.chamber === 'House'}>{c.chamber}</span
						>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="mt-3 text-sm text-slate-500">No chamber membership recorded.</p>
		{/if}
	</section>

	<p class="mt-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
		This directory records the chambers a legislator served in, not the electoral district they
		represented — that field is not in the source data — so it does not (yet) link legislators to
		the contracts awarded in their area.
	</p>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: Open Congress (community-maintained, from senate.gov.ph and congress.gov.ph).
		<a href={resolve('/methodology')} class="text-blue-700 underline">About the data</a>.
	</footer>
</main>
