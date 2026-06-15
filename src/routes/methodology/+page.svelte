<script lang="ts">
	import { resolve } from '$app/paths';
	import { FLAGS, type FlagCode } from '$lib/flags';

	// Show flags strongest-first, the same order the detail page uses.
	const order: FlagCode[] = ['OVER_CEILING', 'DISTRICT_DOMINANCE', 'EXACT_CEILING', 'NEAR_CEILING'];
</script>

<svelte:head>
	<title>How we flag contracts — methodology</title>
	<meta
		name="description"
		content="Plain-language explanation of the simple, auditable statistics used to flag Philippine flood-control contracts."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/')} class="inline-block py-4 text-sm text-blue-700 underline"
		>← All contracts</a
	>

	<h1 class="text-xl font-bold text-slate-900">How we flag contracts</h1>
	<p class="mt-2 text-sm text-slate-600">
		Every flag on this site is a simple statistic you can check yourself. A flag points to a pattern
		worth a closer look — <strong>it is never, on its own, proof of fraud or wrongdoing.</strong>
	</p>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">The numbers behind each contract</h2>
		<p class="mt-2 text-sm text-slate-600">
			Each flood-control contract has an <strong>approved budget</strong> (ABC) — the government's
			own legal ceiling — and an <strong>awarded cost</strong> (what the winning contractor was actually
			paid). Comparing the two, and looking at who wins where, is enough to surface the patterns below.
		</p>
	</section>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">Why we don't just flag "close to budget"</h2>
		<p class="mt-2 text-sm text-slate-600">
			The obvious idea — flag every bid that uses 99%+ of the budget — turns out to be useless here:
			<strong>about 73% of these contracts</strong> already sit that close to the ceiling. When a pattern
			is the norm, it tells you nothing. So instead we use a few sharper flags and add up how concerning
			each one is into a score from 0 to 100.
		</p>
	</section>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">The flags</h2>
		<ul class="mt-2 space-y-3">
			{#each order as code (code)}
				<li class="rounded-xl border border-slate-200 bg-white p-4">
					<div class="flex items-start justify-between gap-2">
						<span class="text-sm font-semibold text-slate-900">{FLAGS[code].label}</span>
						<span class="shrink-0 text-xs text-slate-400">+{FLAGS[code].weight}</span>
					</div>
					<p class="mt-1 text-sm text-slate-600">{FLAGS[code].explanation}</p>
				</li>
			{/each}
		</ul>
		<p class="mt-3 text-xs text-slate-500">
			A contract gets at most one budget-related flag (the most serious that applies), and the
			one-contractor-dominates flag can stack on top. The score is just the sum of the points shown.
		</p>
	</section>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">What's coming next</h2>
		<p class="mt-2 text-sm text-slate-600">
			As we add the larger national procurement datasets, we'll also watch for
			<strong>threshold-splitting</strong>: contracts priced just under a legal limit that would
			otherwise force open competition. We'll compare how many contracts cluster right below the
			limit against how many you'd expect normally, and report the excess — again, as an indicator,
			not a verdict.
		</p>
	</section>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: DPWH Flood Control Projects (via BetterGov). Our methodology is public and adapts the
		approach of contractes.cat to Philippine data.
	</footer>
</main>
