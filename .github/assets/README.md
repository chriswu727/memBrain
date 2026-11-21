# Images for the README and social posts

Every picture here comes from the real memory page (`/memory`, opened with `membrain plugin ui`). They were captured on
2026-11-21 from runtime commit `907ee90e`, on Windows 11 in headless Chrome with a new temporary profile. No UI was
mocked up or painted in. All data is fictional:

- **Showcase:** the built-in demo map (`src/membrain/web/memory-map-demo.json`, opened at `/memory?demo=brain&show=1`).
  It is the same demo data as `brain-showcase.png`.
- **Brain, Notes and Conversations:** a new profile seeded through the public API. Messages were sent with the SDK's
  `observe`. Notes were saved with `membrain.notes.save_note`, the function behind the `memory_note` tool, and each
  cites the user messages it came from. The people (Lena, Sam, Pepper the dog) and the conversations are made up. The
  seeding took one day, so every note and message is dated 2026-11-21, including where the text mentions an earlier
  day.

| File | Size | What it shows |
| --- | --- | --- |
| `demo.gif` | 1200×750, 17.5 s, 7.6 MB | The hero demo (timeline below). |
| `social-preview.png` | 1280×640, 0.4 MB | The GitHub social preview: the name, the line “Agent memory you can trace: who said it, where it came from.” and a Showcase frame. |
| `still-showcase.png` | 1920×1200 | Showcase, full screen, with the demo map. The corner reads “Demo · Simulated signals”. |
| `still-memories-graph.png` | 1680×1290 | Brain view, graph layer **Memories**, 3D observatory, seeded profile. The September trip note is picked (wire sphere). The list beside it counts each kind, including 19 recent messages and 38 learned assertions (records the runtime derives from messages). |
| `still-note-sources.png` | 1650×1140 | The page opened at one note (`#note=<id>`, the address `membrain plugin ui --note <id>` opens). The note shows the earlier note it replaced, the message it was saved from and the message the earlier note was based on, each marked **You** and linked to its conversation. |
| `still-you-and-agent.png` | 1650×659 | One conversation, reached from the food note's source link, which outlines the message it points to. The user's messages are marked **You** with a green edge. The agent's offer of a weekly meal plan is marked **Agent**. The note saved from this conversation (“Eats fish but no meat since summer 2026. Does not want a meal plan.”) cites only the two **You** messages; the Notes view shows this, but this still does not. |
| `brain-showcase.png` | 1470×741 | An earlier capture of the 2D Showcase with the demo map. It is older than this set and is still used by the README. |

## What is decoration

Use captions that keep these limits:

- **Showcase** (`demo.gif` opening, `still-showcase.png`, `social-preview.png`): only the bright dots and the lines
  that join them stand for records and their recorded links, here the fictional demo records. The following are
  illustrative geometry:
  - the brain-shaped shell of filaments;
  - the branches around each dot;
  - the cerebellum and stem wireframes;
  - the projector rings;
  - the glow.

  The travelling light is simulated (“Simulated signals”) and is not agent activity or recall. The demo map draws
  branches around its dots. A map of real memory uses the structural layout, which draws none; with the seeded
  profile its dots gathered in the middle. A person's own Showcase can therefore look sparser than these pictures.
- **3D observatory** (`demo.gif` middle, `still-memories-graph.png`): the wire shell, the region labels and the positions
  are a layout aid. Being close together means nothing. Dot size is layout weight, not strength or importance. Only
  the drawn lines are recorded links, as the page itself explains under “How to read the 3D view”.

## How `demo.gif` was made

1. **0–5 s:** Showcase with the demo map. It is zoomed in a little with the page's own scroll zoom and rotated by
   dragging.
2. **Crossfade (0.3 s):** to a separate recording of the seeded profile.
3. **About 5–12 s:** Brain view with graph layer Memories and the 3D observatory. The view is rotated by dragging, then
   the September trip note is clicked. The page scrolls down to the opened memory: its status and date, the note it
   replaces, the message it was derived from and the message the earlier note was based on.
4. **About 12–17 s:** the page opens at that note (`#note=<id>`) with its sources expanded, and scrolls a little.
5. **Last quarter second:** fade into the first frame so the loop has no jump.

The cut joins two real recordings; no frame mixes them, apart from the crossfades. Parts play 1.15–1.5 times faster
than they were recorded. The capture itself has no cursor, so the pointer and click ring were drawn afterwards at the
recorded pointer positions. Colours are reduced to GIF palettes: 128 colours for the Showcase frames and 255 for the
page frames.

## How the other images were made

- **Stills:** unedited screenshots at device scale 1.5. `still-you-and-agent.png` is cropped to the open conversation.
- **`social-preview.png`:** a crop of a Showcase screenshot (demo map), edge-feathered onto a flat background whose
  colour is sampled from the same frame. The text is set in Segoe UI. It is a composed image, not a screen of the
  product.
- **Using the preview:** the repository owner uploads it under Settings → General → Social preview. It was not
  uploaded as part of this work.
