# Images for the README and social posts

Every picture here comes from the real memory page (`/memory`, opened with `membrain plugin ui`). They were captured on
2026-11-21 from commit `ff62707c` (runtime `9a423c2d`, the repaired page), on Windows 11 in headless Chrome, with
temporary profiles. No UI was mocked up or painted in. All data is fictional:

- **Recorded memory** (`demo.gif`, the social preview and most stills): the small world of
  `tests/page_polish_world.py`. It is recorded as a user's memory is made: through the Claude Code plugin's own hooks
  (`session_start`, `user_prompt`, `stop`) and its MCP server's `memory_note` tool, on a scenario clock
  (2 to 7 November 2026). No model was called. The world has 24 user turns with the agent's replies and 12 notes,
  each citing the user message it came from. One more conversation of two turns was added the same way: the agent
  offers a meal plan, the user declines, and a note keeps what the user said. The map counts 128 records and 80 links:
  52 messages, 63 learned assertions (statements the runtime derives from messages), 11 current notes and 2 feelings
  attached to notes. The people (Mira), places and projects are made up.
- **Built-in demo** (`still-showcase.png`, `brain-showcase.png`): the demo map shipped with the page
  (`src/membrain/web/memory-map-demo.json`, opened at `/memory?demo=brain&show=1`). Each picture shows its label,
  "Demo · Simulated signals" or "Fictional demo data".

| File | Size | What it shows |
| --- | --- | --- |
| `demo.gif` | 1200×750, 17.6 s, 7.6 MB | The hero demo, one recording of the recorded memory (timeline below). |
| `social-preview.png` | 1280×640, 0.4 MB | The GitHub social preview: the name, the line “Agent memory you can trace: who said it, where it came from.” and a Showcase frame of the recorded memory. |
| `still-showcase-recorded.png` | 1920×1200 | Showcase, full screen, recorded memory. The corner reads “Simulated signals”. |
| `still-showcase.png` | 1920×1200 | Showcase, full screen, built-in demo. The corner reads “Demo · Simulated signals”. |
| `brain-showcase.png` | 1470×741 | The 2D Showcase (the page's view without WebGL), built-in demo, captioned “Fictional demo data”. The README shows it. |
| `still-memories-graph.png` | 1680×1290 | Brain view, graph layer **Memories**, 3D observatory, recorded memory. The note “Book Rifugio Biella … for the night of 3 July” is picked (wire sphere). The list beside it counts each kind. |
| `still-note-sources.png` | 1650×1140 | The page opened at that note (`#note=<id>`, the address `membrain plugin ui --note <id>` opens). It shows the earlier note it replaced (5 July), the message it was saved from and the message the earlier note was based on, each marked **You** and linked to its conversation. |
| `still-you-and-agent.png` | 1650×851 | One conversation, reached from the food note's source link, which outlines the message it points to. The user's messages are marked **You**, the agent's are marked **Agent**. The agent offers a weekly meal plan; the user declines. The note “Eats fish but no meat. Does not want a meal plan.” rests only on the user's message. |

## What is decoration

Use captions that keep these limits. While the full-screen Showcase runs, nothing on screen says that the brain shape
is decoration (the footer that says so is hidden there), so a caption has to say it.

- **Showcase** (`demo.gif` opening, `still-showcase-recorded.png`, `still-showcase.png`, `social-preview.png`): only
  the bright dots and the lines that join them stand for records and their recorded links. The following are
  illustrative geometry:
  - the brain-shaped shell of filaments;
  - the cerebellum and stem wireframes;
  - the projector rings;
  - the glow;
  - in the built-in demo only, the neuron-like branches around each dot. They stand for nothing, and a recorded
    memory never gets them.

  The travelling light, and the short streaks it leaves in a still, is simulated (“Simulated signals”). It is not
  agent activity or recall. The built-in demo is richer in notes than a recorded memory, which is mostly messages and
  the statements taken from them, so a person's own Showcase looks like the recorded one, not the demo.
- **3D observatory** (`demo.gif` middle, `still-memories-graph.png`): the wire shell, the area names and the positions
  are a layout aid. Being close together means nothing. Dot size is layout weight, not strength or importance. Only
  the drawn lines are recorded links, as the page itself explains under “How to read the 3D view”.

## How `demo.gif` was made

One recording, signed in to the recorded memory, with no cut:

1. **0–4.8 s:** the Showcase (`?show=1`), zoomed in a little with the page's own scroll zoom and rotated by dragging.
   The pointer then clicks the close button.
2. **4.8–5.6 s:** the Brain view appears and the page scrolls down to the graph. This part plays at three times speed,
   so the status cards above the graph pass quickly. One of them says the semantic model is not enabled, because it
   was switched off for this profile.
3. **5.6–9.5 s:** graph layer Memories in the 3D observatory: zoom, rotate, hover and click the hut note. Its label
   shows on hover.
4. **9.5–13.2 s:** the page scrolls to the opened memory: its date, the note it replaces, the message it was derived
   from and the message the earlier note was based on.
5. **13.2–17.6 s:** the page opens at that note (`#note=<id>`) with its sources expanded, and scrolls a little.
6. **Last quarter second:** fade into the first frame so the loop has no jump.

Parts play 1.15 to 3 times faster than recorded; the note page plays at recorded speed. The capture itself has no
cursor, so the pointer and click ring were drawn afterwards at the recorded pointer positions. The pointer was led
around the cluster of learned assertions in the 3D view. Their hover labels show the stored text, which can read
“assistant assistant (direct_statement): …”, a known defect of the page. Colours are reduced to GIF palettes:
128 colours for the Showcase frames, and 255 each for the Brain frames and the note page.

## How the other images were made

- **Stills:** unedited screenshots at device scale 1.5. `still-you-and-agent.png` is cropped to the open conversation.
  `brain-showcase.png` is at device scale 1, and WebGL was turned off in the browser to reach the 2D Showcase.
- **`social-preview.png`:** a crop of a Showcase screenshot (recorded memory), edge-feathered onto a flat background
  whose colour is sampled from the same frame. The crop leaves out the page's controls and its “Simulated signals”
  label. The text is set in Segoe UI. It is a composed image, not a screen of the product.
- **Using the preview:** the repository owner uploads it under Settings → General → Social preview. It was not
  uploaded as part of this work.
