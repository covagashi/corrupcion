<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { peso } from '$lib/format';

	let { data }: { data: PageData } = $props();

	const count = (n: number) => Math.round(n).toLocaleString('en-PH');
	// Bars are scaled to the busiest year so the recent-year trend reads at a glance.
	const maxExcess = $derived(Math.max(1, ...data.years.map((y) => y.excess_count ?? 0)));
	const hasData = $derived(data.years.some((y) => y.excess_count != null));
</script>

<svelte:head>
	<title>Contracts priced just below the bidding threshold</title>
	<meta
		name="description"
		content="How many Philippine government contracts cluster just below the legal limit that triggers open competitive bidding — observed versus expected."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/')} class="inline-block py-4 text-sm text-blue-700 underline"
		>← All contracts</a
	>

	<h1 class="text-xl font-bold text-slate-900">Priced to dodge open bidding</h1>
	<p class="mt-2 text-sm text-slate-600">
		Above a legal peso limit, government contracts must go through open competitive bidding. When
		many contracts cluster <em>just below</em> that limit, it can mean awards were split to stay under
		it. Here is how many more such contracts we see than a normal price spread would predict.
	</p>

	{#if hasData}
		<p class="mt-6 text-4xl font-extrabold tracking-tight text-slate-900">
			{count(data.totalExcessCount)}
			<span class="mt-1 block text-base font-medium text-slate-500">
				extra contracts just below the threshold ({peso(data.totalExcessValue)} above expectation)
			</span>
		</p>

		<section class="mt-8">
			<h2 class="text-sm font-semibold tracking-wide text-slate-500 uppercase">
				Excess contracts by year
			</h2>
			<ul class="mt-3 space-y-2">
				{#each data.years as y (y.year)}
					<li class="text-sm">
						<div class="flex justify-between text-slate-700">
							<span class="font-medium">{y.year}</span>
							<span class="text-slate-500">
								{y.excess_count == null ? '—' : count(y.excess_count)}
							</span>
						</div>
						<div class="mt-1 h-2 overflow-hidden rounded bg-slate-100">
							<div
								class="h-2 rounded bg-amber-500"
								style="width: {((y.excess_count ?? 0) / maxExcess) * 100}%"
							></div>
						</div>
					</li>
				{/each}
			</ul>
			<p class="mt-3 text-xs text-slate-500">
				Pre-2020 history is thin, so read the recent years most. A blank year is one with too few
				contracts below the limit to estimate a reliable baseline.
			</p>
		</section>
	{:else}
		<p
			class="mt-6 rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
		>
			No threshold-splitting data is loaded yet. Run the pipeline and seed the database (see <code
				>docs/deploy.md</code
			>).
		</p>
	{/if}

	<p class="mt-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
		This is an indicator of possibly reduced competition, <strong>not proof</strong> of splitting or wrongdoing
		in any individual contract.
	</p>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: PhilGEPS awarded contracts (via BetterGov).
		<a href={resolve('/methodology')} class="text-blue-700 underline">How we flag contracts</a>.
	</footer>
</main>
