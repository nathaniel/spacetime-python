# Spacetime Python Port Handoff

This document is a compact continuation guide for future work on the Python
reimplementation of the Java **Spacetime** special-relativity application.
This repository contains the active Python implementation. The original Java
implementation is maintained separately as a behavioral reference.

## Current state

The project is at a feature-complete desktop-beta stage. The Python version
currently includes:

- Lorentz transformations, velocity addition, gamma factors, worldlines, and
  proper-time calculations.
- Clocks, light flashes, free events, intersections, birth/termination events,
  programmed Delta beta events, and diagram decorations.
- Spacetime scenario `.sce` loading and saving, including escaped Unicode and
  multiline comments.
- Synchronized Highway and Spacetime Diagrams.
- Object and Event tables with editing, read-only cells, context menus, and
  Java-style formatting.
- Object and Event tables use the same application font size, including after
  dynamic font-size changes.
- Undo/redo, scenario save/load, object programming, lifetime constraints,
  decorations, zooming, panning, time navigation, and frame changes.
- Platform-aware menus, persistent preferences, first-launch Getting Started,
  shortcuts and gestures, and Help content.
- Focused regression tests; the current suite has 33 passing tests.

The major remaining delivery work is native packaging and release hardening:
Windows and macOS builds, packaged smoke tests, resource bundling, and
optional signing/notarization. A longer-term design task is to consider
retooling scenario files as a versioned structured format, while retaining
Java-style `.sce` import compatibility.

## Repository layout

```text
spacetime/                 Java reference implementation
spacetime/
  spacetime/
    model/                 Physics and scenario state
    persistence/           Java .sce reader/writer and Properties codec
    commands/              Undo/redo commands
    gui/                   Main window, views, tables, Help
    resources/help/        Bundled HTML Help
  tests/                   pytest coverage
  PORT_PLAN.md             Original port and release plan
  IMPLEMENTATION_SUMMARY.md Implementation history and status
  README.md                Python-area overview
  HANDOFF.md               This continuation guide
```

Do not modify the Java source unless explicitly required for comparison or
compatibility research.

## Important compatibility rules

### Coordinates and physics

- The speed of light is `c = 1`.
- Stored object/event coordinates are in the original/master frame.
- Display coordinates use:

  ```text
  x' = gamma * (x - beta * t)
  t' = gamma * (t - beta * x)
  ```

- Non-flash object beta is capped at `±0.9999`.
- Light flashes use exactly beta `-1` or `+1`.
- Clock beta snapping follows the gamma-spaced Highway grid.
- Highway x and spacetime event coordinates snap to tenths where Java does.

### Object and event behavior

- Manual Highway or table changes to an object's x/beta remove its birth,
  termination, and Delta beta events and clear programmed mode.
- Setting Program mode alone preserves future worldline records, Delta beta
  events, and termination.
- Entering a new beta while programmed removes termination and continues the
  programmed worldline.
- Objects with birth/termination already set show Cancel actions instead of
  Set actions.
- Generated boundary events use numbered labels such as `E2` and `E3`.
- Generated Delta beta labels use the Greek, hyphenated form:
  `C1-Δβ1`, `C1-Δβ2`, and so on.
- Boundary events cannot be dragged or edited.
- Fixed/intersection and worldline-attached events have read-only coordinates.
- Free user events can be dragged and edited.
- A Highway object drag records a complete scenario snapshot so one Undo
  restores the object state and related events together.

### Rendering and labels

- Highway and spacetime views are synchronized for horizontal scale and pan.
- The current time is centered vertically in the Spacetime Diagram.
- The Scenario tab contains notes about the situation being explored; new
  scenarios start with a human-readable prompt.
- Interval decorations display `S`, `T`, or `L`, the interval value, `Δx`, and
  `Δt`, using Java-style pink decoration coloring.
- Spacetime-diagram context actions construct light cones and invariant
  hyperbolas immediately. `Spacetime interval to . . .` enters a two-event
  selection mode; clicking a different event completes it, while clicking
  empty space or pressing Esc cancels it.
- Event and object labels use the compact beta/gamma axis font size to reduce
  overlap.
- Flash worldlines use orange, and Highway object/event labels are positioned
  above the plotted worldline area to avoid overlap.
- The bottom status bar shows the current time and live hover details; a
  divider appears before details only while an object or event is hovered.
- Spacetime interval selection can be cancelled by pressing Esc or clicking
  empty space. While selection is active, its instruction takes priority over
  hover details.
- Interactive views provide cursor affordances, and the Create menu exposes
  Clock, Light Flash, and Event actions directly. Brief confirmations appear
  after creation, programming, and saving; major views and panels have
  accessible names.
- Right-clicking a worldline intersection in the Spacetime Diagram offers
  `Create event`; the two intersecting worldlines become visibly thicker on
  hover, and the event is fixed to the exact intersection. It is synchronized
  if the intersecting worldlines change. All crossings are considered,
  including crossings on semi-infinite segments before the first recorded
  worldline point.
- The Event table provides context actions equivalent to the spacetime
  diagram: construct a light cone, construct an invariant hyperbola, start
  spacetime-interval selection, or delete the event. These actions participate
  in undo/redo history.
- Help opens in a dockable panel with direct Getting Started, Tutorial, and
  Shortcuts & Gestures entries. A first-launch Getting Started dialog can be
  disabled and re-enabled in Preferences.
- Preferences/Settings persist application font size and mouse-wheel and
  trackpad sensitivity, plus whether Getting Started appears at launch.
  Changes preview immediately; Apply commits them and Cancel restores the
  previous values.

## Menus and shortcuts

The current top-level menus are:

- **Scenario** — New, Open, Save, Save As, Quit.
- **Edit** — Undo, Redo.
- **Create** — Clock, Light Flash, Event.
- **Reference frame** — Transform to beta relative to the current frame,
  Transform up/down, Return to original frame.
- **Coordinates** — Advance time, Rewind time, Set time, Set time to zero,
  Center on x.
- **View** — Zoom in/out, Move left/right.
- **Help** — Help Contents, Getting Started, Tutorial, Shortcuts & Gestures,
  and About.

Displayed modifier names are platform-aware:

- macOS uses `Cmd`.
- Windows/Linux use `Ctrl`.

Shortcuts:

- Up/Down: advance/rewind time by `0.1`.
- Cmd/Ctrl+Up/Down: advance/rewind time by `1.0`.
- Left/Right: move the synchronized view.
- Cmd/Ctrl+Left/Right: move the view by 10x the normal distance.
- Shift+Up/Down: transform the reference frame.
- Shift+0: return to the original reference frame.
- Cmd/Ctrl+0: set time to zero.
- Plus/Minus: zoom.
- Undo/Redo use Qt platform-standard sequences; macOS Undo is Cmd-Z and
  Redo is Cmd-Shift-Z.
- The window title's dirty marker is derived by comparing the current scenario
  with the last saved snapshot, so undoing back to the saved state clears it.

macOS may inject standard system services such as Writing Tools, Autofill,
Dictation, and Emoji & Symbols into the native Edit menu. This is normal
platform behavior and is intentionally accepted.

## Persistence details

`.sce` files use Java Properties syntax. The Python Properties codec must:

- Preserve unknown properties where possible.
- Escape actual newlines as `\n` rather than writing multiline property records.
- Preserve literal backslashes, tabs, carriage returns, form feeds, and Unicode
  escapes.
- Restore multiline comments exactly when loading.
- Preserve notes on generated birth and termination events when synchronizing
  boundary events after loading.
- Preserve the synchronized horizontal diagram view range using the `sx1` and
  `sx2` properties.

The Event table supports horizontal scrolling when needed, and its Note column
resizes to fit the current content.

The bundled scenarios are useful compatibility fixtures. Pay particular
attention to scenarios containing `Δβ` labels and escaped multiline comments.

## Validation

Use the existing Mamba environment:

```bash
mamba run -n spacetime-py env QT_QPA_PLATFORM=offscreen python -m pytest -q
```

The expected current result is 33 passing tests. For GUI smoke checks, use
`QT_QPA_PLATFORM=offscreen` and instantiate `MainWindow` with a `Scenario`.
Do not add new testing tools; use the existing pytest and Qt setup.

## Packaging status

Packaging is planned but not yet completed:

1. Build a Windows executable with PyInstaller on a native Windows runner.
2. Build a macOS `.app` with PyInstaller on a native macOS runner.
3. Bundle Help, resources, and representative example scenarios.
4. Run a smoke test against each packaged application.
5. Add code signing/notarization for macOS and executable signing or an
   installer for Windows if distribution requires it.

The source implementation should be stabilized further before release builds.

## Worktree caution

Generated artifacts should not be committed, including Java `.class` files,
`Spacetime.jar`, Python caches, egg-info directories, and generated scenario
artifacts.

At the time this handoff was written, the worktree also contained changes
outside the documentation and current feature edits, including an
`undo_redo.py` modification and a generated scenario-file modification. Do not
discard or reset those changes without inspecting them and confirming their
intended ownership.

## Recommended next steps

1. Inspect and resolve the existing worktree changes without using destructive
   reset or checkout commands.
2. Continue Java-vs-Python compatibility review for less-used table and
   decoration workflows.
3. Add broader golden-scenario comparisons and packaged smoke tests.
4. Implement native Windows and macOS packaging.
5. Only then address signing, notarization, installers, and release metadata.
