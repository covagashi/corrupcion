<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';
	import { pesoShort } from '$lib/format';

	let { data }: { data: PageData } = $props();

	function provinceHref(name: string) {
		return resolve(`/contracts?province=${encodeURIComponent(name)}`);
	}
</script>

<svelte:head>
	<title>Browse contracts by area — Philippine government contracts</title>
	<meta
		name="description"
		content="Every province and area where Philippine government contract money was spent — by total value and number of flagged contracts."
	/>
</svelte:head>

<main class="mx-auto max-w-screen-sm px-4 pb-16">
	<a href={resolve('/')} class="inline-block py-4 text-sm text-blue-700 underline">← Home</a>

	<header class="pb-2">
		<h1 class="text-xl font-bold text-slate-900">Find your area</h1>
		<p class="mt-1 text-sm text-slate-600">
			{data.provinces.length.toLocaleString()} areas where contract money was spent, biggest first. Tap
			one to see its contracts, riskiest first.
		</p>
	</header>

	{#if data.provinces.length}
		<ul class="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
			{#each data.provinces as p (p.province)}
				<li>
					<a
						href={provinceHref(p.province)}
						class="flex items-center justify-between gap-3 p-3 active:bg-slate-50"
					>
						<span class="min-w-0">
							<span class="block truncate text-sm font-semibold text-slate-900">{p.province}</span>
							<span class="mt-0.5 block text-xs text-slate-500">
								{p.count.toLocaleString()} contracts
								{#if p.flagged > 0}· {p.flagged.toLocaleString()} flagged{/if}
							</span>
						</span>
						<span class="shrink-0 text-right">
							<span class="block text-sm font-semibold text-slate-900">{pesoShort(p.value)}</span>
							<span class="text-slate-400">→</span>
						</span>
					</a>
				</li>
			{/each}
		</ul>
	{:else}
		<p
			class="mt-3 rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
		>
			No area data is loaded yet. Run the pipeline and seed the database (see <code
				>docs/deploy.md</code
			>).
		</p>
	{/if}

	<footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
		Area = province (or PhilGEPS area of delivery). Sources: DPWH Flood Control, DPWH Infrastructure
		and PhilGEPS (via BetterGov).
		<a href={resolve('/methodology')} class="text-blue-700 underline">How we flag contracts</a>.
	</footer>
</main>
