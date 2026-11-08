# DON-GEN (standalone)

This branch is now a **standalone game mod**, NOT a replacement patch for the Workshop Generative Summer mod.

Install ONLY the `don_gen/` folder to `Everlasting Summer/game/mods/don_gen/`. This folder contains independent Ren'Py labels and Python module names prefixed `dg_`.

Installation details: [README.md](README.md). RPG features: [RPG.md](RPG.md).

- No `ready_replace/` or legacy `patches/` package remains in this branch.
- Windows installer `install.ps1` copies the standalone folder, never overwrites other mods.
- Unmodified vanilla `archive.rpa` provides base sprites/backgrounds; 7DL is optional.
- RPG and AI generation data are isolated under `config.savedir/don_gen/`.
- Logs: `don_gen.log`, `don_gen_worker.log`, optional `traces/*.json`.
- Automatic Python checks run in GitHub Actions; in-game Ren'Py smoke testing is still necessary.

Base branch `gen-7dl-vanilla` is unchanged.

2026-11-08: Added direct installed 7DL CE resource support. -WorkshopDir writes a local resource_sources.json for cross-library installs; same-library and environment discovery remain supported. Workshop maps and numbered character icons take precedence, donor backgrounds cover additional RPG locations, and runtime manifest paths are absolute with forward slashes. The donor directory is not added to Ren'Py's script search path. Added fixture tests and a native four-actor preview using read-only vanilla/Workshop assets.

2026-11-08: Online-first RPG UI pass: bounded hub panels, persistent action drafts, scrollable setup, searchable travel, correct map back navigation, and hybrid scene history in the journal. Fixed free actions at extended locations, negated commands, NPC-name prefix collisions, same-day skill unlocks, and final-day quest expiration. See UI_CHANGES_RU.md for validation and remaining limitations.

2026-11-08: Native named Character dialogue and four-actor staging replace anonymous paragraphs and two fixed portraits. AI labels are parsed as text only; scene time/place are frozen before a turn. Map selection uses one art/hotspot transform and a separate destination panel. Fixed invalid focus_mask False and made viewport scrollbar sizing explicit. Added a Windows Ren'Py 7 headless render runner with placeholder vanilla resources; it exercises nine actual RPG screens without login or game saves.

2026-11-08: Replaced the map sidebar/atlas layout with the fullscreen classic gen_assets/maps/map_bg.jpg and its matching JPG hover layers. Corrected cabin hotspots, including cabin 12, and retained list access for unlabelled rooms. Installer now imports the classic map variants; private binaries remain outside the public repository and can be supplied with -AssetsDir. Render runner accepts --assets and --screen for checking the actual private map locally.

2026-11-01: Added `dg_world.py` nonlinear camp director and `tests/test_don_gen_world.py`; see README v0.3 for new UI and daily events. Character setup now uses its own contrast popup screen.

DON-GEN v0.4: Added `dg_social.py`: typed offline actions, 33 personal NPC chapters, 4 three-step timed quests, daily social rumours and interactive two-NPC encounters. Ren'Py screens include free-action modal, personal scenes, contracts, shared-map encounter markers and social journal tab. Existing JSON sessions migrate automatically.

