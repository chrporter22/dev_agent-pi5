# Seeded synthetic ML data source as the default

- **Date:** 2026-11-07
- **Decided by:** user (chat, this session)
- **Topic:** llm

## Decision

`core/ml` ships a seeded synthetic embedding stream as the default data source,
so the dashboard renders real numbers (PCA, drift, risk) immediately on a fresh
clone, without requiring a real embedding pipeline.  Selection is via the
`ML_DATA_SOURCE` env flag (`synthetic` | `none`, default `synthetic`).  Setting
`ML_DATA_SOURCE=none` restores the pre-2026-11-07 dormant behaviour.

## Why

`core/ml`'s `_load_embeddings()` has been a stub returning `None` since the
2026-10-24 simplify removed `core/vdb`.  The pipeline prints
`No data source wired — pipeline idle` every cycle, the dashboard's three ML
cards render zeros, and the chart components in `core/pca-backend/src/components/charts/`
crash on null arrays (see the open-threads note in
`.ai/sessions/llm/2026-11-07-0201--next-steps-and-prioritization.md`).

Wiring a real source was discussed but not chosen now:

- The external `~/ai-gateway` exposes an ml-service on port 8081 and a
  rag-service on 8082; integrating either requires a contract decision, an
  outbound egress for `core/ml`, and a wire-format to keep stable across repos.
- The bot's `/chat` history stream would require feeding the worker + ML
  worker through a shared Redis channel — a feature, not a config knob.
- Hand-rolled embedding pipelines (e.g. sentence-transformers) were explicitly
  dropped in the 2026-10-24 simplify along with the rest of `core/llm`.

The user chose to **unblock the dashboard now** with a deterministic seeded
synthetic stream and revisit a real source later.  The synthetic stream:

- Produces 64 samples of 128 dims with a fixed low-rank latent structure
  (the first ~3 PCA components capture most variance) so the charts show
  meaningful shape, not a flat blob.
- Has a slow sinusoidal drift on the latent centroid, so the drift score
  changes cycle by cycle instead of staying static.
- Is deterministic from `seed = 42 + cycle_counter` (modulo an initial fixed
  projection matrix), so values are reproducible across restarts and testable.

The default is `synthetic`, not `none`, because the dashboard is the visible
artifact of a fresh clone and an empty dashboard reads as "broken".  The flag
exists so anyone who wants the old behaviour (or is running on hardware where
the ML loop should be off) can switch back.

## What stays

- `_load_embeddings()` returns `None` when `ML_DATA_SOURCE=none`, preserving
  the exact pre-change behaviour of the post-2026-10-24 simplify code.
- The PCA / drift / risk math (`pca_engine.py`, `drift_detector.py`,
  `risk_classifier.py`) is unchanged.  Synthetic data flows through the same
  pipeline as any future real source.
- The `_heartbeat()` call still runs every cycle so the dashboard's WorkerCard
  sees a live process even when `none` is selected.
- The rules-based risk classifier's thresholds and band logic are unchanged.
  The synthetic stream produces drift scores that land in the "High/Critical"
  range by design (high-dim data has a non-trivial variance component), but
  the thresholds and bands are not retuned in this change.

## What changes

- `core/ml/ml_worker.py` gains `_load_synthetic_embeddings()` and a dispatcher
  in `_load_embeddings()` keyed on `ML_DATA_SOURCE`.
- `core/ml/config.py` adds `ML_DATA_SOURCE`, `ML_SYNTHETIC_SAMPLES`,
  `ML_SYNTHETIC_DIM` env reads with safe defaults.
- `.env.example` documents the new flags under a dedicated section.
- The README "Bring-up" section is sharpened to call out the three
  user-side values that gate go-live (`TELEGRAM_TOKEN`, `ALLOWED_USER`,
  `DEFAULT_REPO`) and explains that the synthetic ML stream renders data
  before any of them is set.

## Trade-offs considered

- **Real source now vs synthetic placeholder now.** User chose synthetic. The
  flagged re-evaluation point is "when a real embedding pipeline is decided".
  Until then, every cycle's data is illustrative, not derived from production.
- **Always-on vs flag-gated default.** Chose flag-gated with `synthetic` as the
  default. This keeps the off-CPU option (`none`) reachable without code edits
  while still showing real numbers on first boot.
- **High dimensionality (128) vs smaller (e.g. 16).** 128 keeps the PCA chart
  looking interesting (first 3 components dominate) and matches the order of
  magnitude of typical embedding vectors (BGE-small is 384, E5 is 1024, etc.).
  Smaller dims would push the chart into a denser scatter.
- **Drift oscillates with `sin(t)` vs random walk.** Chose `sin(t)` for
  predictability and reproducibility; a random walk would produce a less
  readable trend in the drift card.

## Deferred to user

- Wiring a real embedding source.  The next decision will pick the source
  (gateway `ml-service`, `/chat` history stream, or external) and define the
  contract between `core/ml` and the producer.  Until then,
  `ML_DATA_SOURCE=synthetic` is the default and the dashboard renders
  illustrative numbers.

## Supersedes / relates to

- `.ai/decisions/simplify/2026-10-24--strip-llm-and-vdb-keep-bot-pca.md` — the
  decision that removed `core/vdb` and left the ML pipeline with no source.
  This decision does not re-introduce vdb; it ships a self-contained synthetic
  source so the existing PCA / drift / risk pipeline has something to chew on
  while a real source remains TBD.
- `.ai/sessions/llm/2026-11-07-0201--next-steps-and-prioritization.md` — the
  session that identified the dormant pipeline as the largest engineering gap.
- `.ai/sessions/llm/2026-11-04-2127--plan-review-and-leave-off.md` — recorded
  the dormant pipeline and listed it as the only open engineering item; this
  decision closes the gap with a placeholder.
