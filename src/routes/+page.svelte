<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { peso, pesoShort } from '$lib/format';

	let { data }: { data: PageData } = $props();

	const hasData = $derived(data.totals.contracts > 0);

	function provinceHref(name: string) {
		return resolve(`/contracts?province=${encodeURIComponent(name)}`);
	}
</script>

<svelte:head>
	<title>Follow the money — Philippine government contracts</title>
	<meta
		name="description"
		content="See where Philippine public money goes. Government contracts (flood control, DPWH, PhilGEPS) checked for simple, auditable signs of irregularity — and browsable by your area."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<!-- Hero -->
	<header class="pt-8 pb-6">
		<h1 class="text-2xl leading-tight font-extrabold tracking-tight text-slate-900">
			Where does the public money go?
		</h1>
		<p class="mt-2 text-base text-slate-600">
			We collect Philippine government contracts and check each one for simple, auditable signs that
			something is off — bids that hug the budget ceiling, one contractor dominating a district,
			amounts parked just under the bidding limit. Plain numbers, no secret scores.
		</p>
	</header>

	<!-- Headline numbers -->
	{#if hasData}
		<section class="grid grid-cols-3 gap-2 text-center">
			<div class="rounded-xl border border-slate-200 bg-white p-3">
				<div class="text-lg font-bold text-slate-900">{pesoShort(data.totals.totalValue)}</div>
				<div class="mt-0.5 text-xs text-slate-500">in contracts tracked</div>
			</div>
			<div class="rounded-xl border border-slate-200 bg-white p-3">
				<div class="text-lg font-bold text-slate-900">
					{data.totals.contracts.toLocaleString()}
				</div>
				<div class="mt-0.5 text-xs text-slate-500">contracts</div>
			</div>
			<div class="rounded-xl border border-slate-200 bg-white p-3">
				<div class="text-lg font-bold text-amber-700">{data.totals.flagged.toLocaleString()}</div>
				<div class="mt-0.5 text-xs text-slate-500">carry a flag</div>
			</div>
		</section>
	{:else}
		<section
			class="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
		>
			No contract data is loaded yet. Run the pipeline and seed the database (see <code
				>docs/deploy.md</code
			>).
		</section>
	{/if}

	<!-- Find your area -->
	{#if data.topProvinces.length}
		<section class="mt-8">
			<div class="flex items-baseline justify-between">
				<h2 class="text-base font-bold text-slate-900">Find your area</h2>
				<a href={resolve('/areas')} class="text-sm text-blue-700 underline"
					>All {data.provinceCount} areas →</a
				>
			</div>
			<p class="mt-1 text-sm text-slate-600">
				Tap a province to see the contracts spent there, riskiest first.
			</p>
			<ul class="mt-3 grid grid-cols-2 gap-2">
				{#each data.topProvinces as p (p.province)}
					<li>
						<a
							href={provinceHref(p.province)}
							class="block rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
						>
							<div class="truncate text-sm font-semibold text-slate-900">{p.province}</div>
							<div class="mt-0.5 text-xs text-slate-500">
								{pesoShort(p.value)} · {p.flagged.toLocaleString()} flagged
							</div>
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<!-- Explore -->
	<section class="mt-8 space-y-3">
		<h2 class="text-base font-bold text-slate-900">Explore</h2>

		<a
			href={resolve('/contracts')}
			class="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 active:bg-slate-50"
		>
			<span>
				<span class="block text-sm font-semibold text-slate-900">Browse all contracts</span>
				<span class="mt-0.5 block text-xs text-slate-500"
					>Search every source, ranked most concerning first.</span
				>
			</span>
			<span class="text-slate-400">→</span>
		</a>

		<a
			href={resolve('/threshold-splitting')}
			class="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 active:bg-slate-50"
		>
			<span>
				<span class="block text-sm font-semibold text-slate-900">Priced to dodge open bidding</span>
				<span class="mt-0.5 block text-xs text-slate-500">
					{#if data.excessCount > 0}
						~{Math.round(data.excessCount).toLocaleString()} extra contracts ({peso(
							data.excessValue
						)}) sit just below the bidding threshold.
					{:else}
						How many contracts cluster just below the legal bidding limit.
					{/if}
				</span>
			</span>
			<span class="text-slate-400">→</span>
		</a>

		<a
			href={resolve('/legislators')}
			class="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 active:bg-slate-50"
		>
			<span>
				<span class="block text-sm font-semibold text-slate-900">Legislators</span>
				<span class="mt-0.5 block text-xs text-slate-500">
					{#if data.legislatorCount > 0}
						{data.legislatorCount.toLocaleString()} senators and representatives, 8th–20th Congress.
					{:else}
						Senators and representatives and the congresses they served.
					{/if}
				</span>
			</span>
			<span class="text-slate-400">→</span>
		</a>

		<a
			href={resolve('/methodology')}
			class="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 active:bg-slate-50"
		>
			<span>
				<span class="block text-sm font-semibold text-slate-900">How we flag contracts</span>
				<span class="mt-0.5 block text-xs text-slate-500"
					>Every flag, in one plain sentence. No black box.</span
				>
			</span>
			<span class="text-slate-400">→</span>
		</a>
	</section>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Sources: DPWH Flood Control, DPWH Infrastructure and PhilGEPS (via BetterGov). Flags are simple,
		auditable statistics — they indicate patterns worth reviewing, not proof of wrongdoing.
	</footer>
</main>
