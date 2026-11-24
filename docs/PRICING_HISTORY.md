# AGY-Nexus Price Book & Model Rate History

> Generated deterministically from `src/agy_nexus/data/model_catalog.json` and `src/agy_nexus/data/cost_ledger.json` (**Catalog Revision `2`** · Updated `2026-11-24`).  
> Do not edit by hand; regenerate via `python3 scripts/catalog_sync.py --render-docs`.

## Subscription Tiers (Official US)

| Tier | Monthly USD | Included Dev Credits | Pool Multiplier | Notes |
| :--- | ---: | ---: | :---: | :--- |
| Google AI Plus | $4.99 | $0.00 | 2x Free | $4.99/mo (400 GB, 2x Free Gemini limits, Hydrogen 4) |
| Google AI Pro | $19.99 | $10.00 | 1x | $19.99/mo ($199.99/yr annual, 5 TB, $10/mo dev credits) |
| Google AI Ultra (5x) | $99.99 | $40.00 | 5x | $99.99/mo (20 TB, 5x Pro limits, $40/mo dev credits) |
| Google AI Ultra (20x) | $199.99 | $100.00 | 20x | $199.99/mo (30 TB, 20x Pro limits, $100/mo dev credits) |

## Model API Rate Epochs & IDE Context Limits

| Model | Effective Window | Input / 1M | Cache / 1M | Output / 1M | IDE Ctx / Out (Locked) | API Ctx / Out | Verified | Source | Notes |
| :--- | :--- | ---: | ---: | ---: | :---: | :---: | :---: | :--- | :--- |
| Gemini 4 Carbon (`carbon`) | `2025-01-01` .. `2026-11-30` | $2.00 | $0.100 | $10.00 | `1048k/65k` | `1048k/262k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Introductory rate through Nov 30 |
| Gemini 4 Carbon (`carbon`) | `2026-12-01` .. `present` | $4.00 | $0.200 | $20.00 | `1048k/65k` | `1048k/262k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Scheduled Dec 1 standard rate |
| Gemini 4 Neon (`neon`) | `2025-01-01` .. `present` | $3.00 | $0.150 | $15.00 | `1048k/65k` | `1048k/262k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Standard rate |
| Gemini 4 Argon (`argon`) | `2025-01-01` .. `2026-11-30` | $2.00 | $0.100 | $10.00 | `1048k/65k` | `1048k/65k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Introductory rate through Nov 30 |
| Gemini 4 Argon (`argon`) | `2026-12-01` .. `present` | $4.00 | $0.200 | $20.00 | `1048k/65k` | `1048k/65k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Scheduled Dec 1 standard rate |
| Gemini 4 Hydrogen (`hydrogen`) | `2025-01-01` .. `present` | $1.50 | $0.075 | $7.50 | `1048k/65k` | `1048k/262k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Standard rate |
| Gemini 3.8 Flash (`flash_3_8`) | `2025-01-01` .. `2026-12-31` | $0.75 | $0.075 | $3.75 | `1048k/65k` | `1048k/65k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Introductory rate through Dec 31 |
| Gemini 3.8 Flash (`flash_3_8`) | `2027-01-01` .. `present` | $1.50 | $0.150 | $7.50 | `1048k/65k` | `1048k/65k` | `2026-11-24` | [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Scheduled Jan 1 standard rate |
| Claude Opus 5.5 (`claude_opus_5_5`) | `2025-01-01` .. `present` | $4.00 | $0.200 | $20.00 | `200k/32k` | `1000k/128k` | `2026-11-24` | [pricing](https://www.anthropic.com/pricing) | Standard rate |
| Claude Sonnet 5.5 (`claude_sonnet_5_5`) | `2025-01-01` .. `present` | $2.00 | $0.100 | $10.00 | `200k/64k` | `1000k/128k` | `2026-11-24` | [pricing](https://www.anthropic.com/pricing) | Standard rate |
| GPT-OSS 120B (`gpt_oss_120b`) | `2025-01-01` .. `present` | $0.00 | $0.000 | $0.00 | `128k/16k` | `131k/32k` | `2026-11-24` | [pricing](https://models.dev/api.json) | Partner failover default ($0.00 configurable override) |
