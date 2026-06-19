<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { parseList } from '$lib/officials';

	let { data }: { data: PageData } = $props();
	const o = $derived(data.official);
	const parties = $derived(parseList(o.parties));

	// Distinct provinces this official held office in — each links to that area's contracts.
	const provinces = $derived([
		...new Set(data.terms.map((t) => t.province).filter((p): p is string => !!p))
	]);

	function areaHref(province: string) {
		return resolve(`/contracts?province=${encodeURIComponent(province)}`);
	}
</script>

<svelte:head>
	<title>{o.full_name} — public official</title>
	<meta name="description" content="{o.full_name}: offices held by province, locality and year." />
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/officials')} class="inline-block py-4 text-sm text-blue-700 underline"
		>← All officials</a
	>

	<header>
		<h1 class="text-lg font-bold text-slate-900">{o.full_name}</h1>
		{#if parties.length}
			<p class="mt-1 text-xs text-slate-500">Party: {parties.join(', ')}</p>
		{/if}
	</header>

	{#if provinces.length}
		<section class="mt-5">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">
				Contracts in their area
			</h2>
			<div class="mt-2 flex flex-wrap gap-2">
				{#each provinces as p (p)}
					<a
						href={areaHref(p)}
						class="rounded-full border border-slate-300 px-3 py-1 text-sm text-blue-700 active:bg-slate-50"
						>{p} →</a
					>
				{/each}
			</div>
		</section>
	{/if}

	<section class="mt-6">
		<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">Offices held</h2>
		{#if data.terms.length}
			<ul class="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
				{#each data.terms as t (t.id)}
					<li class="flex items-center justify-between gap-3 p-3 text-sm">
						<span class="min-w-0">
							<span class="block font-medium text-slate-900">{t.position ?? '—'}</span>
							<span class="mt-0.5 block text-xs text-slate-500">
								{[t.locality, t.province, t.region].filter(Boolean).join(', ') || '—'}
								{#if t.party}· {t.party}{/if}
							</span>
						</span>
						<span class="shrink-0 text-sm font-medium text-slate-700">{t.year ?? '—'}</span>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="mt-3 text-sm text-slate-500">No offices recorded.</p>
		{/if}
	</section>

	<p class="mt-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
		This records the offices a person held by area and year. Linking to contracts shows what was
		spent in those areas — it is context, <strong>not</strong> a claim that this official was involved
		in any contract.
	</p>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: Raw Philippine Data (public officials + memberships, via BetterGov).
		<a href={resolve('/methodology')} class="text-blue-700 underline">About the data</a>.
	</footer>
</main>
