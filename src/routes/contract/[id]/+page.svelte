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
	<a href={resolve('/contracts')} class="inline-block py-4 text-sm text-blue-700 underline"
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

	{#if data.companyInfo.license || data.companyInfo.suspended}
		<section class="mt-6">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">
				Contractor license (PCAB)
			</h2>
			{#if data.companyInfo.suspended}
				{@const s = data.companyInfo.suspended}
				<div class="mt-2 rounded-xl border border-red-200 bg-red-50 p-4">
					<div class="flex items-center gap-2">
						<span class="rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white uppercase"
							>{s.status ?? 'License suspended'}</span
						>
						<span class="text-sm font-semibold text-red-900">PCAB license no longer valid</span>
					</div>
					<p class="mt-2 text-sm text-red-800">
						<strong>{s.contractor_name}</strong>
						{#if s.valid_from}
							— from {s.valid_from}{#if s.valid_to}
								to {s.valid_to}{/if}
						{/if}
						{#if s.reason}
							<br />Reason: {s.reason}
						{/if}
					</p>
					<p class="mt-2 text-xs text-red-700">
						A contractor whose license was suspended or revoked by PCAB should not have won new
						government contracts after that date. Worth checking against the contract's award year.
					</p>
				</div>
			{:else if data.companyInfo.license}
				{@const l = data.companyInfo.license}
				<dl class="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
					<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
						<dt class="text-slate-500">PCAB license no.</dt>
						<dd class="text-right font-medium text-slate-900">{l.license_no ?? '—'}</dd>
					</div>
					<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
						<dt class="text-slate-500">License category</dt>
						<dd class="text-right font-medium text-slate-900">{l.category ?? '—'}</dd>
					</div>
					<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
						<dt class="text-slate-500">Valid to</dt>
						<dd class="text-right font-medium text-slate-900">{l.valid_to ?? '—'}</dd>
					</div>
					{#if l.amo_owner}
						<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
							<dt class="text-slate-500">Disclosed owner (AMO)</dt>
							<dd class="text-right font-medium text-slate-900">{l.amo_owner}</dd>
						</div>
					{/if}
					{#if l.gov_registered !== null}
						<div class="flex justify-between gap-4 px-4 py-2.5 text-sm">
							<dt class="text-slate-500">Registered for gov't projects</dt>
							<dd class="text-right font-medium text-slate-900">
								{l.gov_registered === 1 ? 'Yes' : 'No'}
							</dd>
						</div>
					{/if}
				</dl>
				<p class="mt-1 text-xs text-slate-500">
					Source: Philippine Contractors Accreditation Board — public license verification.
				</p>
			{/if}
		</section>
	{:else if c.contractor}
		<p class="mt-6 text-xs text-slate-400">
			No PCAB license record matched this contractor in our snapshot — the firm may be unlicensed,
			or its name in the contract does not match the PCAB record.
		</p>
	{/if}

	{#if data.surnameOverlaps.length}
		<section class="mt-6">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">
				Surname overlap with officials
			</h2>
			<p class="mt-1 text-xs text-slate-500">
				The disclosed owner of this contractor's PCAB license
				{#if data.companyInfo.license?.amo_owner}
					({data.companyInfo.license.amo_owner}){/if}
				shares a surname with the {data.surnameOverlaps.length}
				official{data.surnameOverlaps.length === 1 ? '' : 's'} listed below. This is a
				<strong>signal, not proof</strong> — surnames are common; it just marks a connection worth a closer
				look.
			</p>
			<ul class="mt-3 divide-y divide-slate-100 rounded-xl border border-amber-200 bg-amber-50">
				{#each data.surnameOverlaps as o (o.scope + o.person_id)}
					<li>
						<a
							href={resolve(o.scope === 'legislator' ? '/legislator/[id]' : '/official/[id]', {
								id: o.person_id
							})}
							class="flex items-center justify-between gap-3 p-3 active:bg-amber-100"
						>
							<span class="min-w-0">
								<span class="block truncate text-sm font-semibold text-slate-900"
									>{o.full_name ?? 'Unknown'}</span
								>
								<span class="mt-0.5 block text-xs text-slate-600">
									{#if o.scope === 'legislator'}
										{o.roles ?? 'Legislator'}
										{#if o.year}
											· latest {o.year}{/if}
									{:else}
										{o.position ?? '—'}{#if o.locality}
											of {o.locality}{/if}
										{#if o.party}
											· {o.party}{/if}
										{#if o.year}
											· {o.year}{/if}
									{/if}
								</span>
							</span>
							<span class="shrink-0 text-xs font-medium text-amber-700"
								>{o.scope === 'legislator' ? 'national' : 'local'}</span
							>
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#if data.dynastyContext && data.dynastyContext.share}
		{@const sh = data.dynastyContext.share}
		{@const d = data.dynastyContext}
		<section class="mt-6">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">
				Dynasty context in {sh.province}
			</h2>
			<p class="mt-1 text-xs text-slate-500">
				Share of local politicians in {sh.province} who belong to a "fat" political dynasty (Ateneo Policy
				Center), at the closest election year to this contract.
			</p>
			<div class="mt-2 rounded-xl border border-slate-200 bg-white p-4">
				<div class="flex items-baseline justify-between gap-3">
					<span class="text-2xl font-bold text-slate-900">{Math.round(sh.share)}%</span>
					<span class="text-xs text-slate-500">election year {sh.year}</span>
				</div>
				{#if d.nationalAverage !== null}
					<p class="mt-2 text-sm text-slate-600">
						{#if sh.share > d.nationalAverage}
							<strong>Above</strong> the national average ({Math.round(d.nationalAverage)}%) for {sh.year}.
						{:else}
							<strong>Below</strong> the national average ({Math.round(d.nationalAverage)}%) for {sh.year}.
						{/if}
					</p>
				{/if}
				{#if d.totalCount > 0}
					<p class="mt-2 text-xs text-slate-500">
						Sample: {d.fatCount} of {d.totalCount} local politicians in the Ateneo dataset that year were
						classified as members of a fat dynasty.
					</p>
				{/if}
				<p class="mt-2 text-xs text-slate-500">
					A high fat-dynasty share means political offices tend to stay within the same families —
					relevant context for reading the contract, not in itself a sign of fraud in this specific
					contract.
				</p>
			</div>
		</section>
	{/if}

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

	{#if data.areaOfficials.provinceWide.length || data.areaOfficials.local.length}
		<section class="mt-6">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">
				Who held office in this area
			</h2>
			<p class="mt-1 text-xs text-slate-500">
				Officials recorded for {[c.municipality, c.province]
					.filter(Boolean)
					.join(', ')}{#if data.areaYear}
					around {data.areaYear}{/if}. This shows who was in office — it does
				<strong>not</strong> imply any involvement in this contract.
			</p>
			<ul class="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
				{#each [...data.areaOfficials.provinceWide, ...data.areaOfficials.local] as o (o.person_id + o.position)}
					<li>
						<a
							href={resolve('/official/[id]', { id: o.person_id })}
							class="flex items-center justify-between gap-3 p-3 active:bg-slate-50"
						>
							<span class="min-w-0">
								<span class="block truncate text-sm font-semibold text-slate-900"
									>{o.full_name ?? 'Unknown'}</span
								>
								<span class="mt-0.5 block text-xs text-slate-500">
									{o.position ?? '—'}{#if o.locality}
										of {o.locality}{/if}
									{#if o.party}
										· {o.party}{/if}
									{#if o.year}
										· {o.year}{/if}
								</span>
							</span>
							<span class="shrink-0 text-slate-400">→</span>
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

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
