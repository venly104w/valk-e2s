# Valk Reel — office video generator (concept)

**Status:** idea only. Nothing to build, nothing to install, no code in this directory.
This document is self-contained and does not depend on the rest of `valk-e2s`.

**One line:** the office makes short branded videos by hand-generating clips on the
Higgsfield website during the free Seedance window, then running one fixed branding
pass over them. Everything needed already exists off the shelf.

---

## 1. Naming — say the precise thing

Half the confusion here is vocabulary. These are the real names.

| What we've been saying | What it actually is |
| --- | --- |
| "higgsfield generator" | **Higgsfield** — a commercial AI image/video product at higgsfield.ai. Not the Higgs field. Not something we generate; it is a service we log into. |
| "seedance" | **Seedance 2.0** — ByteDance's video model. We do not run it; Higgsfield, fal.ai and Replicate all serve it. |
| "brandex work" | **Brand pass** — a fixed, repeatable post step: logo bug, lower-third, intro card, outro card, safe-area, loudness normalise. Driven by a **brand kit** (logo files, 2 fonts, 3 hex colours, intro/outro cards). |
| "claus plan" | **Claude connector** — Higgsfield ships an MCP server, so Claude can drive generation directly. Distinct from the *production plan* in §5. |
| "total generator" | **Valk Reel** — proposed name for the office workflow as a whole (alternates: *Front Desk*, *Reel Desk*). One name for the pipeline so people stop calling three different things "the generator". |

Proposed name going forward: **Valk Reel**.

---

## 2. The fact that decides everything

> "Unlimited access here is scoped to the Higgsfield website, not automation surfaces
> like MCP, CLI, Canvas, or Supercomputer, so those workflows still use standard credits."
> — Higgsfield, *Seedance Unlimited: Get 4K Access for 14 Days*

**The free window does not cover automation.** The original idea — wire Higgsfield to
Claude and batch-generate videos through the free days — is exactly the thing the offer
excludes. Every clip pulled through MCP, the CLI or an API burns paid credits, free
window or not.

So the two routes are genuinely separate, and only one of them is free:

- **Free route** — a human sits at higgsfield.ai and generates by hand. Costs nothing
  during the window. Does not scale past what one person can click.
- **Automated route** — Claude/MCP/CLI/API. Scales fine. Costs money per clip from day one.

**Recommendation: run the free route for the clips, automate only the brand pass.** The
brand pass is local, deterministic, and free forever — that's where automation actually pays.

### Also: it is not 12 days

The 12 days figure doesn't match any current offer. What's actually on the table:

| Offer | Length | Contents |
| --- | --- | --- |
| New-user trial | 1 day | Unlimited across 20+ models incl. Seedance 2.0, cancel in one click |
| → continues into Plus | +7 days | Unlimited on Plus |
| Seedance Unlimited | 14 days | 7 days Seedance 2.0 at 4K, then 7 days on one of Seedance 2.5 / 2.0 Mini / 2.0 Fast |

**Confirm which offer the office is actually holding before anyone plans around it.** §5
is written for a 12-working-day calendar with a 7-day unlimited window inside it, which
fits the Seedance Unlimited shape.

---

## 3. Parts list — all of it already exists

Nothing on this list needs writing. This is the "find what's already there" answer.

**Generation**
- **higgsfield.ai website** — the only surface where the free window applies. Free route.
- **Higgsfield MCP** — connector URL `https://mcp.higgsfield.ai/mcp`. Add under
  Customize → Connectors in Claude. No API key; authenticates with the Higgsfield
  account. Works with Claude web, Cowork and Claude Code. This is the "claus plan" piece,
  and it's a settings-screen paste, not a build. **Spends credits.**
- **Higgsfield CLI** — `npm i -g @higgsfield/cli`, then `higgsfield auth login`. Only if
  someone wants terminal access. Skipped under "no install". **Spends credits.**
- **fal.ai / Replicate** — direct Seedance 2.0 endpoints if we ever outgrow Higgsfield.
  Higgsfield's own developer API is gated to higher tiers with thin docs; fal is the
  cleaner API if it comes to that.

**Brand pass**
- **`saud-learning-services/automated-video-brander`** — existing tool, ffmpeg-python,
  does intro + outro + watermark from a spreadsheet of rows. Closest match to what we want.
- **plain ffmpeg `overlay` / `drawtext`** — if the above is more than we need. Scale the
  logo to 10–15% of frame width, semi-transparent plate behind text.
- **OpusClip API** — hosted intro/outro branding, if we'd rather pay than run anything.

**Not needed:** any custom generator, any new repo, any glue service. If someone proposes
building one, this section is the reason not to.

---

## 4. What a clip costs when it isn't free

Once the window closes, or on anything automated:

| Route | Rate | 8-second clip |
| --- | --- | --- |
| fal.ai, Seedance 2.0, 720p | $0.3034 / sec | ~$2.43 |
| fal.ai, Seedance 2.0, 1080p | $0.682 / sec | ~$5.46 |
| Replicate | matches fal per-second | ~same |
| Higgsfield credits (MCP/CLI) | per-generation, plan-dependent | confirm on the plan page |

A 40-clip batch at 720p is roughly **$97**. At 1080p, roughly **$218**. Worth knowing
before anyone promises a monthly reel.

Higgsfield Plus subscription price is not stated here — nobody should quote it from
memory. Check the pricing page.

---

## 5. The 12 working days

Assumes the 7-day unlimited window sits in the middle. One named owner per block.

| Days | Block | Output |
| --- | --- | --- |
| 1 | Confirm the offer | Which trial the office holds, its real end date, whether commercial use is permitted. Nothing else starts until this is answered. |
| 1–2 | Brand kit | Logo (SVG + transparent PNG), 2 fonts, 3 hex colours, intro card, outro card, lower-third layout. Frozen — no edits after day 2. |
| 2 | Shot list | 30–40 rows: scene, prompt, on-screen copy, duration, aspect. Claude can draft this straight into a sheet; costs nothing because no generation happens. |
| 3–9 | **Free window** | Hand-generate on the website against the shot list. Keep every take. File as `NN-slug-take.mp4`. Expect ~50% keep rate, so over-generate. |
| 10–11 | Brand pass | One ffmpeg config over the whole folder. Same treatment on every clip — that's the entire point. |
| 12 | Review + handoff | Pick finals, hand over the folder, write down what to reuse next time. |

**Rules for the free week:** one person on the account (concurrent sessions risk the
trial), download everything the day it's made, cancel before the window ends if we're not
continuing. Nothing generated in that week should ever need a re-prompt after day 9.

---

## 6. Open items

1. **Which offer, ending when?** Everything above hangs on this.
2. **Commercial use** — the offer pages don't address whether trial output can be used in
   business material. Must be confirmed before a single clip ships externally.
3. **Who owns the brand kit** — the brand pass is worthless without frozen inputs.
4. **Where the clips live** — a shared drive folder, decided before day 3, not during.
5. **Is the Claude connector wanted at all?** It's a two-minute paste, but it spends
   credits on every generation. Only worth it after the free window, and only if the
   office wants volume beyond hand-clicking.

---

## Sources

- [Higgsfield MCP](https://higgsfield.ai/mcp)
- [Higgsfield CLI](https://higgsfield.ai/cli)
- [Seedance Unlimited: Get 4K Access for 14 Days](https://higgsfield.ai/blog/seedance-unlimited-14-days)
- [Higgsfield on X — 1-day trial + 7 days Plus](https://x.com/higgsfield/status/2079577416998277147)
- [Seedance 2 (Image to Video) on fal](https://fal.ai/models/bytedance/seedance-2.0/image-to-video)
- [Seedance 2 API: fal vs Replicate pricing](https://poyo.ai/comparison/seedance-2-fal-vs-replicate-vs-poyo)
- [automated-video-brander](https://github.com/markoprodanovic/automated-video-brander)
- [FFmpeg watermarking: text and logo overlays](https://www.ffmpeg.media/articles/watermarking-text-logo-overlays)
- [Add branded intros and outros via API (OpusClip)](https://www.opus.pro/blog/add-intro-outro-video-api)
