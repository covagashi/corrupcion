<script lang="ts">
	import { resolve } from '$app/paths';
	import { FLAGS, type FlagCode } from '$lib/flags';

	// Show flags strongest-first, the same order the detail page uses.
	const order: FlagCode[] = [
		'OVER_CEILING',
		'OVER_BUDGET',
		'DISTRICT_DOMINANCE',
		'EXACT_CEILING',
		'NEAR_CEILING'
	];
</script>

<svelte:head>
	<title>How we flag contracts — methodology</title>
	<meta
		name="description"
		content="Plain-language explanation of the simple, auditable statistics used to flag Philippine flood-control contracts."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/contracts')} class="inline-block py-4 text-sm text-blue-700 underline"
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
		<h2 class="text-base font-semibold text-slate-900">Threshold-splitting</h2>
		<p class="mt-2 text-sm text-slate-600">
			Across the national PhilGEPS procurement data we also watch for
			<strong>threshold-splitting</strong>: contracts priced just under the legal limit (₱1,000,000
			under RA 9184; ₱2,000,000 from 2025 under RA 12009) above which open competitive bidding
			becomes mandatory. We compare how many contracts cluster right below the limit against how
			many a normal price spread would predict, and report the excess — an indicator, not a verdict.
			Contracts inside that band carry the <em>"priced just below the bidding threshold"</em>
			flag.
			<a href={resolve('/threshold-splitting')} class="text-blue-700 underline"
				>See the year-by-year excess.</a
			>
		</p>
	</section>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">Legislators</h2>
		<p class="mt-2 text-sm text-slate-600">
			We also publish a <a href={resolve('/legislators')} class="text-blue-700 underline"
				>directory of senators and representatives</a
			>
			from the community-maintained Open Congress dataset (sourced from senate.gov.ph and congress.gov.ph).
			It records which chambers and congresses each person served in. It does
			<strong>not</strong> include the electoral district a representative held — that field is not in
			the data — so we deliberately do not (yet) link legislators to the contracts awarded in their area.
			Doing that honestly needs a district-level source we do not have.
		</p>
	</section>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">Officials in an area</h2>
		<p class="mt-2 text-sm text-slate-600">
			On a contract we show <a href={resolve('/officials')} class="text-blue-700 underline"
				>public officials</a
			>
			— governors, mayors, representatives — who held office in that contract's province (and town) around
			its year. We match on the <strong>province / locality name</strong> recorded for each office,
			near the contract's year. It is plain context: it shows who was in office, and
			<strong>never</strong> implies any official was involved in the contract. Matching depends on place
			names lining up between the two sources, so the list can be incomplete.
		</p>
	</section>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">
			Contractor license and the owner's surname
		</h2>
		<p class="mt-2 text-sm text-slate-600">
			For each contract we also look up the contractor against the public
			<strong>PCAB</strong> (Philippine Contractors Accreditation Board) license register. If the
			firm has a current license we show its number, category and validity, and the
			<strong>disclosed owner</strong> (the AMO — Authorized Managing Officer). If the firm appears
			in PCAB's <strong>suspended / revoked</strong> list, a red badge flags it — a contractor whose
			license was revoked should not have won new government work after that date. This is shown as
			context alongside the contract, and is <strong>not added to the score</strong> (it is a separate,
			third-party registry check, not a statistic we compute).
		</p>
		<p class="mt-2 text-sm text-slate-600">
			We also take the AMO surname and check whether any official in the contract's area — or any <a
				href={resolve('/legislators')}
				class="text-blue-700 underline">senator or representative</a
			>
			nationally — shares it. A surname overlap is <strong>a signal, not proof</strong>: Philippine
			surnames are common, and the same last name is no indication two people are related or
			coordinated. It just marks a place worth a closer look by a journalist or citizen, exactly the
			way the area-officials panel does.
		</p>
	</section>

	<section class="mt-6">
		<h2 class="text-base font-semibold text-slate-900">Political dynasty context</h2>
		<p class="mt-2 text-sm text-slate-600">
			For contracts in a province we also show the <strong>fat-dynasty share</strong> published by the
			Ateneo Policy Center for the closest election year to that contract (1992..2022, every three years),
			next to the national average that year. "Fat dynasty" is Ateneo's term for elected offices that
			stay within the same family across terms. A high share is a structural condition of the area's politics
			— useful context for reading why a contractor wins repeatedly in a place, but not by itself proof
			of anything about a specific contract.
		</p>
	</section>

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Source: DPWH Flood Control Projects + PhilGEPS awarded contracts + DPWH infrastructure
		transparency data + Open Congress + Raw Philippine Data officials (via BetterGov) + PCAB
		licenses + Ateneo Policy Center Political Dynasties Dataset. Our methodology is public and
		adapts the approach of contractes.cat to Philippine data.
		<a href={resolve('/threshold-splitting')} class="text-blue-700 underline"
			>Below-threshold pricing</a
		>.
	</footer>
</main>
