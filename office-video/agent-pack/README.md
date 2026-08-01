# KADRE — the per-place video director robot

**Status:** definition only. No build, no install, no dependencies. Three markdown files.

**What it is:** a named agent that turns a one-line brief into a full high-level video
package — concept, shot list, Veo/Seedance prompt blocks, bilingual on-screen copy, and a
brand pass spec. One agent definition, one profile per place. Each office gets its own
robot by writing a profile; nobody writes a second agent.

---

## The name

**KADRE.** From كادر / *cadre* — the frame. It means "the shot" in the Arabic the OHG bot
already speaks, and "the frame" in the film sense. Reads as a director's name, works as
`@kadre`, and doesn't collide with BRANDEX OS or BrandEx Studio AI.

Alternates if it's taken: **VELA**, **ATLAS**.

Precise about what is what, since these overlap:

| Name | What it is | Where |
| --- | --- | --- |
| **BrandEx Studio AI** | Existing app — dashboard, Flow Studio, shot cards, library | `venly104w/brdx-video` |
| **BRANDEX OS** | The Veo prompt-architect system prompt inside that app | `services/geminiService.ts` |
| **OHG bot** | Existing office chatbot, company facts baked into one system prompt | `venly104w/v0-ohg-company-chatbot` |
| **KADRE** | *New.* The portable director agent. Per-place profiles. | this folder |
| **Valk Reel** | The production workflow around it | `../README.md` |

KADRE is not a replacement for BRANDEX OS. BRANDEX OS architects a single Veo prompt in
chat; KADRE plans a whole campaign for a specific place and emits the objects the Studio
app already understands.

---

## Why a profile, not a fork

The OHG bot works because one system prompt carries everything about the company — the
250-years line, the seven countries, the `info@ohg.world` routing, the Arabic RTL rule.
That's the pattern worth keeping. What isn't worth keeping is that it's *welded to that
one bot*: a second office means copying 90 lines of prompt and hand-editing it.

So KADRE splits it. The agent holds the craft — how to build a shot list, what a lens
choice does, how a brand pass works. The **profile** holds the place — its brand, voice,
languages, palette, contacts, what it's allowed to say. New office, new profile file.
The agent never changes.

```
agents/kadre.md          the director. identical everywhere.
profiles/ohg.md          Omari Holdings Group — lifted from the live office bot
profiles/_template.md    blank. copy it for the next place.
```

## Using it

Copy `agents/kadre.md` into `.claude/agents/` in whichever repo the office works from —
`brdx-video` is the natural home — and put `profiles/` next to it. Then:

> `@kadre` using profiles/ohg.md — 6 clips for the Q1 expansion push, vertical, Arabic + English

It answers with a concept, a numbered shot list, a Flow JSON block per shot, the on-screen
copy in both languages, and the brand pass spec. Paste the prompts into Higgsfield or Flow
by hand — see the free-window constraint in [../README.md §2](../README.md).

To add a place: copy `_template.md`, fill it, name it after the place. That's the whole
onboarding.

## Output shapes

KADRE emits the exact key names `brdx-video/types.ts` already defines, so output drops into
the Studio app without translation:

- shot technical block → `{ lens, lighting, filmStock }` (the `Shot.technical` interface)
- Flow JSON → `shot_description, camera_movement, camera_angle, distance, speed, lighting,
  effects, vibe, audio_sync` (the BRANDEX OS schema)

If those interfaces change, change them here too. That coupling is deliberate — it's what
makes the agent useful rather than decorative.
