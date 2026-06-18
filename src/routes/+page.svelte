<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { FLAGS, parseFlags, riskLabel } from '$lib/flags';
	import { pesoShort, peso, percent } from '$lib/format';

	let { data }: { data: PageData } = $props();

	// Link that flips the flagged-only filter, preserving the current search term.
	const toggleHref = $derived.by(() => {
		const parts: string[] = [];
		if (data.flaggedOnly) parts.push('all=1'); // currently flagged-only -> link shows all
		if (data.search) parts.push(`q=${encodeURIComponent(data.search)}`);
		if (data.source) parts.push(`source=${data.source}`);
		const qs = parts.join('&');
		return resolve(qs ? `/?${qs}` : '/');
	});
</script>

<svelte:head>
	<title>Philippine government contracts — irregularity check</title>
	<meta
		name="description"
		content="Philippine government contracts (flood control + PhilGEPS) ranked by simple, auditable irregularity flags."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<header class="py-6">
		<h1 class="text-xl font-bold text-slate-900">Government contracts</h1>
		<p class="mt-1 text-sm text-slate-600">
			{data.totals.contracts.toLocaleString()} contracts worth {peso(data.totals.totalValue)}.
			{data.totals.flagged.toLocaleString()} carry at least one irregularity flag. Ranked most concerning
			first.
		</p>
	</header>

	<form method="GET" class="mb-4 flex flex-wrap gap-2">
		<input
			type="search"
			name="q"
			value={data.search}
			placeholder="Contractor, district or project…"
			class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
		/>
		{#if !data.flaggedOnly}<input type="hidden" name="all" value="1" />{/if}
		<select
			name="source"
			value={data.source ?? ''}
			class="rounded-lg border border-slate-300 px-2 py-2 text-sm text-slate-700"
			aria-label="Filter by data source"
		>
			<option value="">All sources</option>
			<option value="flood_control">Flood Control</option>
			<option value="philgeps">PhilGEPS</option>
			<option value="dpwh">DPWH Infra</option>
		</select>
		<button class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white">Search</button>
	</form>

	<div class="mb-4 text-sm">
		<a class="text-blue-700 underline" href={toggleHref}>
			{data.flaggedOnly
				? 'Show all contracts (including unflagged)'
				: 'Show only flagged contracts'}
		</a>
		<span class="ml-2 text-slate-500">{data.matched.toLocaleString()} match</span>
	</div>

	<ul class="space-y-3">
		{#each data.contracts as c (c.id)}
			{@const flags = parseFlags(c.risk_flags)}
			<li>
				<a
					href={resolve('/contract/[id]', { id: c.id })}
					class="block rounded-xl border border-slate-200 bg-white p-4 active:bg-slate-50"
				>
					<div class="flex items-start justify-between gap-3">
						<span class="text-sm font-semibold text-slate-900">{c.contractor ?? 'Unknown'}</span>
						<span
							class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
							class:bg-red-100={c.risk_score >= 60}
							class:text-red-800={c.risk_score >= 60}
							class:bg-amber-100={c.risk_score >= 30 && c.risk_score < 60}
							class:text-amber-800={c.risk_score >= 30 && c.risk_score < 60}
							class:bg-slate-100={c.risk_score < 30}
							class:text-slate-700={c.risk_score < 30}
						>
							{riskLabel(c.risk_score)}
						</span>
					</div>
					<p class="mt-1 line-clamp-2 text-sm text-slate-600">{c.description ?? '—'}</p>
					<div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
						{#if c.source === 'philgeps'}
							<span>{c.procuring_entity ?? c.province ?? 'PhilGEPS'}</span>
							<span>•</span>
							<span>{pesoShort(c.contract_cost)}</span>
							{#if c.category}
								<span>•</span>
								<span>{c.category}</span>
							{/if}
						{:else if c.source === 'dpwh'}
							<span>{c.province ?? c.region ?? 'DPWH'}</span>
							<span>•</span>
							<span>{pesoShort(c.abc)}</span>
							{#if c.category}
								<span>•</span>
								<span>{c.category}</span>
							{/if}
						{:else}
							<span>{c.legislative_district ?? '—'}</span>
							<span>•</span>
							<span>{pesoShort(c.contract_cost)}</span>
							{#if c.bid_to_ceiling_ratio != null}
								<span>•</span>
								<span>{percent(c.bid_to_ceiling_ratio)} of ceiling</span>
							{/if}
						{/if}
					</div>
					{#if flags.length}
						<div class="mt-2 flex flex-wrap gap-1">
							{#each flags as f (f)}
								<span class="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700"
									>{FLAGS[f].label}</span
								>
							{/each}
						</div>
					{/if}
				</a>
			</li>
		{:else}
			<li
				class="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
			>
				No contracts match your search.
			</li>
		{/each}
	</ul>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: DPWH Flood Control Projects (via BetterGov). Flags are simple, auditable statistics —
		they indicate patterns worth reviewing, not proof of wrongdoing.
		<a href={resolve('/methodology')} class="text-blue-700 underline">How we flag contracts</a>
		·
		<a href={resolve('/threshold-splitting')} class="text-blue-700 underline"
			>Below-threshold pricing</a
		>.
	</footer>
</main>
