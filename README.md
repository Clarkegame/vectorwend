# VectorWend

A word-path puzzle (in the style of LinkedIn's Wend) for mosquito and vector control professionals, and a companion
to [VectorWord](https://clarkegame.github.io/vectorword/). It's a static site with no build step and no backend.

## How it plays
- A 5x5 (Tuesday) or 6x6 (Thursday) grid of letters (with a few gray wall tiles) hides 3-6 themed words. Empty slot rows show each word's length.
- Drag (mouse or touch) through orthogonally adjacent tiles and release to submit. A trace counts only if it spells one of
  the hidden words, in reading order, on that word's own tiles. Found words lock in with a color. Wrong traces flash and shake.
- Every open tile belongs to exactly one word. **Hint** highlights the start tile and reveals the next letter of an unsolved word
  (revealing every letter completes the word). **Undo** and **Reset** remove found words. Hints stay counted.
- The timer runs only while the puzzle is on screen (it pauses in dialogs and background tabs). The results screen shows the time, hints,
  theme, each word's definition, stats/streak, a countdown, Share (copy or native share) and Post to LinkedIn.

## Files
- `index.html`: the page, including Open Graph/LinkedIn meta tags (absolute URLs for https://clarkegame.github.io/vectorwend/)
- `style.css`, `app.js`: styling and game logic
- `puzzles.js`: 156 precomputed puzzles in a fixed order, plus definitions (generated, don't hand-edit)
- `og-image.png`: 1200x627 link preview. Regenerate it with `python tools/make_og.py` (from `tools/og-image.html`).
- `tools/gen_puzzles.py`: the puzzle generator (`python3 tools/gen_puzzles.py`, deterministic, seed 20260928)
- `tools/answers.js`: word bank + definitions (a copy of VectorWord's answers.js). `tools/words.js`: ENABLE word list for the uniqueness check.
- `tools/test_game.py`: headless Playwright tests (`python tools/test_game.py`)

## Puzzle verification (done by the generator for every puzzle)
1. The intended words cover every open tile exactly once, each word being a simple orthogonal path.
2. Each hidden word can be traced on exactly one set of tiles in the grid.
3. Using any of the 194 bank words, there is exactly one way to fill the grid with words of the slot lengths.
4. The tile partition is also unique when any English word (ENABLE list, 4-8 letters) is allowed.

## Schedule
- Puzzle #1 is Tuesday, Sep 29, 2026. A new puzzle goes live at midnight Pacific time every Tuesday (5x5) and
  Thursday (6x6). On other days the latest puzzle stays up.
- 156 puzzles covers 78 weeks (about 1.5 years, through late March 2028), then the list repeats. Regenerating `puzzles.js` changes
  future puzzles, so if you tweak the generator after launch, keep the already-published puzzles at the front.
