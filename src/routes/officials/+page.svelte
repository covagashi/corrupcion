<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { parseList } from '$lib/officials';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>Public officials — Philippine governors, mayors and representatives</title>
	<meta
		name="description"
		content="Directory of Philippine public officials — governors, mayors, representatives and the offices they held by province, locality and year."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/')} class="inline-block py-4 text-sm text-blue-700 underline">← Home</a>

	<header class="pb-2">
		<h1 class="text-xl font-bold text-slate-900">Public officials</h1>
		<p class="mt-1 text-sm text-slate-600">
			Governors, mayors, representatives and other officials, and the offices they held by province
			and year. Search by name.
		</p>
	</header>

	<form method="GET" class="mb-4 flex gap-2">
		<input
			type="search"
			name="q"
			value={data.search}
			placeholder="Search an official by name…"
			class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
		/>
		<button class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white">Search</button>
	</form>

	<div class="mb-3 text-sm text-slate-500">{data.matched.toLocaleString()} match</div>

	<ul class="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
		{#each data.officials as o (o.id)}
			{@const positions = parseList(o.positions)}
			<li>
				<a
					href={resolve('/official/[id]', { id: o.id })}
					class="flex items-center justify-between gap-3 p-3 active:bg-slate-50"
				>
					<span class="min-w-0">
						<span class="block truncate text-sm font-semibold text-slate-900">{o.full_name}</span>
						<span class="mt-0.5 block truncate text-xs text-slate-500">
							{positions.slice(0, 3).join(', ') || '—'}
							{#if o.latest_year}· to {o.latest_year}{/if}
						</span>
					</span>
					<span class="shrink-0 text-slate-400">→</span>
				</a>
			</li>
		{:else}
			<li class="p-6 text-center text-sm text-slate-500">
				No officials match. (If empty everywhere, the data is not loaded yet — see
				<code>docs/deploy.md</code>.)
			</li>
		{/each}
	</ul>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: Raw Philippine Data (public officials + memberships, via BetterGov). Names and offices
		are community-maintained and may be incomplete.
		<a href={resolve('/methodology')} class="text-blue-700 underline">About the data</a>.
	</footer>
</main>
