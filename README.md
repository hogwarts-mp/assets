# hogwarts-mp / assets

Static asset host for **Hogwarts Legacy Multiplayer (HogwartsMP)**.

This repo serves the mod's in-game CEF web UI (HUD + chat) over **GitHub Pages**, so
the game client loads it from a URL instead of from local disk — its CEF view does
`CreateView("https://hogwarts-mp.github.io/assets/ui/hud.html")` and fetches it like
any web page. This is the interim host until the MafiaHub services CDN is ready; at
that point only the base URL changes on the client.

> The same repo can later carry binary artifacts (e.g. the `.pak` triplet) as GitHub
> **Releases**: Pages for the UI, Releases for binaries.

## What's published

A self-contained, flat, no-build static bundle — relative refs only, so all three
files must stay siblings in the same directory:

- [`docs/ui/hud.html`](docs/ui/hud.html)
- [`docs/ui/chat.html`](docs/ui/chat.html)
- [`docs/ui/theme.css`](docs/ui/theme.css)  ← referenced relatively by both HTML files

Source of truth lives in the mod repo at
`Framework/code/projects/mod/files/ui/`. When those change, re-copy them here.

> The launcher UI (`code/launcher_ui/web` in the mod repo) is **not** published here
> — it stays bundled locally with the launcher exe (it's the bootstrap and must not
> depend on the network).

## Live URLs

- `https://hogwarts-mp.github.io/assets/ui/hud.html`
- `https://hogwarts-mp.github.io/assets/ui/chat.html`
- `https://hogwarts-mp.github.io/assets/ui/theme.css`

## Pages configuration

- Repository visibility: **public** (required — the client fetches the UI
  anonymously, and free-org Pages only serves public repos).
- **Source:** `main` branch, `/docs` folder (Settings → Pages).
- `.nojekyll` markers (repo root + `docs/`) keep Pages from running Jekyll, so files
  are served verbatim and `_`-prefixed paths aren't dropped.

## Verify

After Pages is live, open `https://hogwarts-mp.github.io/assets/ui/hud.html` in a
normal browser. It should render with the parchment-and-gold theme applied,
confirming the relative `theme.css` reference resolves on Pages.
