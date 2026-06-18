<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { FLAGS, parseFlags, riskLabel } from '$lib/flags';
	import { peso, percent } from '$lib/format';

	let { data }: { data: PageData } = $props();
	const c = $derived(data.contract);
	const flags = $derived(parseFlags(c.risk_flags));
	const sortedFlags = $derived([...flags].sort((a, b) => FLAGS[b].weight - FLAGS[a].weight));
	const isPhilgeps = $derived(c.source === 'philgeps');
	const isDpwh = $derived(c.source === 'dpwh');
	const awardYear = $derived(c.award_date ? new Date(c.award_date).getUTCFullYear() : null);
</script>

<svelte:head>
	<title>{c.contractor ?? 'Contract'} — {c.legislative_district ?? c.procuring_entity ?? ''}</title>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/')} class="inline-block py-4 text-sm text-blue-700 underline"
		>← All contracts</a
	>

	<header>
		<span
			class="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
			class:bg-red-100={c.risk_score >= 60}
			class:text-red-800={c.risk_score >= 60}
			class:bg-amber-100={c.risk_score >= 30 && c.risk_score < 60}
			class:text-amber-800={c.risk_score >= 30 && c.risk_score < 60}
			class:bg-slate-100={c.risk_score < 30}
			class:text-slate-700={c.risk_score < 30}
		>
			{riskLabel(c.risk_score)} · score {c.risk_score}/100
		</span>
		<h1 class="mt-2 text-lg font-bold text-slate-900">{c.contractor ?? 'Unknown contractor'}</h1>
		<p class="mt-1 text-sm text-slate-600">{c.description ?? '—'}</p>
	</header>

	{#if sortedFlags.length}
		<section class="mt-6">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">Why it's flagged</h2>
			<ul class="mt-2 space-y-3">
				{#each sortedFlags as f (f)}
					<li class="rounded-xl border border-slate-200 bg-white p-4">
						<div class="flex items-start justify-between gap-2">
							<span class="text-sm font-semibold text-slate-900">{FLAGS[f].label}</span>
							<span class="shrink-0 text-xs text-slate-400">+{FLAGS[f].weight}</span>
						</div>
						<p class="mt-1 text-sm text-slate-600">{FLAGS[f].explanation}</p>
					</li>
				{/each}
			</ul>
		</section>
	{:else}
		<p class="mt-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
			No irregularity flags. The bid and contractor patterns here look unremarkable.
		</p>
	{/if}

	<section class="mt-6">
		<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">The money</h2>
		<dl class="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
			{#if isPhilgeps}
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Awarded contract amount</dt>
					<dd class="font-medium text-slate-900">{peso(c.contract_cost)}</dd>
				</div>
			{:else if isDpwh}
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Approved budget</dt>
					<dd class="font-medium text-slate-900">{peso(c.abc)}</dd>
				</div>
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Amount paid</dt>
					<dd class="font-medium text-slate-900">{peso(c.contract_cost)}</dd>
				</div>
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Paid as share of budget</dt>
					<dd class="font-medium text-slate-900">{percent(c.bid_to_ceiling_ratio)}</dd>
				</div>
			{:else}
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Approved budget (ceiling)</dt>
					<dd class="font-medium text-slate-900">{peso(c.abc)}</dd>
				</div>
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Awarded contract cost</dt>
					<dd class="font-medium text-slate-900">{peso(c.contract_cost)}</dd>
				</div>
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Bid as share of ceiling</dt>
					<dd class="font-medium text-slate-900">{percent(c.bid_to_ceiling_ratio)}</dd>
				</div>
			{/if}
		</dl>
	</section>

	{#if data.districtStat}
		{@const s = data.districtStat}
		<section class="mt-6">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">
				This contractor in {c.legislative_district}
			</h2>
			<p class="mt-2 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
				Won <strong>{s.contract_count}</strong>
				{s.contract_count === 1 ? 'contract' : 'contracts'} worth
				<strong>{peso(s.total_value)}</strong> here —
				<strong>{percent(s.district_value_share)}</strong>
				of all flood-control money in this legislative district.
			</p>
		</section>
	{/if}

	<section class="mt-6">
		<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">Where & when</h2>
		<dl class="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
			<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
				<dt class="text-slate-500">Location</dt>
				<dd class="text-right font-medium text-slate-900">
					{[c.municipality, c.province, c.region].filter(Boolean).join(', ') || '—'}
				</dd>
			</div>
			{#if isPhilgeps}
				<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Procuring entity</dt>
					<dd class="text-right font-medium text-slate-900">{c.procuring_entity ?? '—'}</dd>
				</div>
				{#if c.category}
					<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
						<dt class="text-slate-500">Category</dt>
						<dd class="text-right font-medium text-slate-900">{c.category}</dd>
					</div>
				{/if}
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Award year</dt>
					<dd class="font-medium text-slate-900">{awardYear ?? '—'}</dd>
				</div>
			{:else if isDpwh}
				{#if c.category}
					<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
						<dt class="text-slate-500">Category</dt>
						<dd class="text-right font-medium text-slate-900">{c.category}</dd>
					</div>
				{/if}
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Year</dt>
					<dd class="font-medium text-slate-900">{c.infra_year ?? c.completion_year ?? '—'}</dd>
				</div>
			{:else}
				<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Implementing office</dt>
					<dd class="text-right font-medium text-slate-900">{c.implementing_office ?? '—'}</dd>
				</div>
				<div class="flex justify-between px-4 py-2.5 text-sm">
					<dt class="text-slate-500">Year</dt>
					<dd class="font-medium text-slate-900">{c.infra_year ?? c.funding_year ?? '—'}</dd>
				</div>
			{/if}
		</dl>
	</section>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Flags are simple, auditable statistics — they indicate patterns worth reviewing, not proof of
		wrongdoing.
		<a href={resolve('/methodology')} class="text-blue-700 underline">How we flag contracts</a>
		·
		<a href={resolve('/threshold-splitting')} class="text-blue-700 underline"
			>Below-threshold pricing</a
		>.
	</footer>
</main>
