# Spacetime Python Implementation Summary

This document records the successful implementation path for the Python version
of the Java **Spacetime** special-relativity application and describes the
intended development process. Superseded approaches and intermediate defects
are intentionally omitted.

## Objective

Reimplement the Java desktop application in Python while preserving its
physics, scenario-file compatibility, major interaction behavior, and visual
relationship between the Highway and spacetime diagrams. The eventual
deliverables are pre-built applications for Windows and macOS.

## Steps completed so far

### 1. Establish the project structure

- Preserved the original Java implementation under `spacetime/`.
- Placed all Python implementation work under `python/`.
- Created a dedicated `spacetime-py` environment.
- Added package metadata, a console entry point, test configuration, and
  packaging configuration.
- Documented the overall port and packaging plan in `PORT_PLAN.md`.

### 2. Build the physics and domain model

- Implemented Lorentz coordinate transformations and inverse transformations.
- Implemented relativistic velocity transformations and gamma calculations.
- Added worldline records, piecewise motion, intersections, and proper-time
  calculations.
- Added clocks with readings and proper time.
- Added light flashes with exact light-speed velocities and lightlike traces.
- Added events and visual decorations, including intervals, light cones, and
  invariant hyperbolas.
- Added object existence boundaries, including birth and termination.
- Kept the distinction between subluminal clocks and light-speed flashes
  throughout the model.

### 3. Add scenario persistence

- Implemented loading and saving of Java-compatible `.sce` scenario files.
- Added Java Properties parsing, including escaped Unicode labels.
- Preserved scenario objects, events, decorations, comments, frame state, and
  current time.
- Added persistence tests using bundled Java scenarios.

### 4. Create the desktop interface

- Implemented the PySide6 application and main window.
- Added synchronized Highway and spacetime diagram views.
- Added object and event tables.
- Added editable current-time control.
- Added menus and actions for creating clocks, flashes, and events.
- Added scenario creation, loading, saving, and replacement.
- Added undo/redo infrastructure.

### 5. Match the Java visual behavior

- Added Highway position, beta, and gamma axes.
- Added spacetime axes, worldlines, event markers, and decorations.
- Rendered clocks with clock faces, moving hands, and proper-time readings.
- Rendered flashes with lightlike traces and Java-style markers.
- Applied Lorentz length contraction to clock glyphs.
- Rendered bounded worldline segments and rays for object lifetimes.
- Added a distinctive current-time band, centerline, and current-position dots.
- Kept the current time vertically centered in the spacetime diagram.
- Synchronized horizontal scale and panning between both diagrams.

### 6. Match Java interaction behavior

- Added context-menu creation and deletion for clocks, flashes, and events.
- Added dragging and table editing of model objects and events.
- Applied Java-compatible snapping:
  - Highway positions snap to tenths.
  - Highway beta values snap to the Java gamma-spaced grid.
  - Spacetime event coordinates snap to tenths in the displayed frame.
- Added event-aware time stepping.
- Kept regular time steps at `0.1`.
- Added `1.0` steps for Ctrl+Up/Ctrl+Down on Windows/Linux and
  Cmd+Up/Cmd+Down on macOS.
- Added keyboard, wheel, trackpad, zoom, and pan interactions.
- Added off-screen Highway indicators for objects outside the active view.
- Preserved Java-style generated names and event notes.
- Disabled jumping to the rest frame of light flashes, matching Java behavior.

### 7. Validate the implementation

- Added focused tests for physics, persistence, editing, and light flashes.
- Verified headless PySide6 operation.
- Verified Java scenario Unicode labels such as `Shuttle-Δβ`.
- Verified synchronized diagram navigation and current-time centering.
- Kept the application dependent on system fonts rather than bundled fonts.

## Desired development process

### A. Use the Java application as the behavioral reference

For each feature, first identify the corresponding Java model, rendering, or
interaction code. Treat physics, coordinate conventions, scenario formats,
keyboard behavior, and user-visible terminology as compatibility requirements.
Treat internal implementation details as replaceable.

### B. Keep the layers independent

Maintain clear boundaries between:

1. **Model and physics** — Lorentz transformations, worldlines, objects,
   events, decorations, and scenario state.
2. **Persistence** — Java `.sce` parsing and writing.
3. **Commands** — Mutations and undo/redo.
4. **GUI** — Views, tables, menus, input handling, and synchronization.
5. **Packaging** — Application bundles and platform-specific release files.

The physics and persistence layers should remain testable without creating a
GUI window.

### C. Implement features in dependency order

Continue development in this order:

1. Establish or confirm the model behavior.
2. Add persistence support.
3. Add or update focused regression tests.
4. Connect the behavior to the GUI.
5. Match Java rendering and interaction details.
6. Validate the feature in loaded and newly created scenarios.
7. Package only after source behavior is stable.

### D. Preserve compatibility deliberately

When behavior differs between the Python and Java versions, determine whether
the difference is required for correctness or is an accidental compatibility
gap. Preserve established Java behavior for:

- Coordinate frames and Lorentz transformations
- Clock readings and proper time
- Light-flash behavior
- Object and event naming
- Snapping rules
- Event-aware stepping
- `.sce` scenario contents
- Keyboard and context-menu semantics

Any intentional divergence should be documented separately and covered by a
focused test.

### E. Validate incrementally

Use the smallest relevant validation after each substantial change:

- Physics tests for model changes
- Persistence tests for `.sce` changes
- Editing tests for commands and table changes
- Flash tests for light-speed behavior
- Headless Qt smoke tests for GUI changes
- Scenario loading and saving checks for compatibility changes

Before a release, run the complete test suite and verify representative
bundled scenarios in both source and packaged forms.

## Current implementation organization

```text
python/
  spacetime/
    model/
    persistence/
    commands/
    gui/
  tests/
  packaging/
  PORT_PLAN.md
  README.md
```

The most behavior-sensitive code is currently concentrated in:

- `model/lorentz.py`
- `model/worldline.py`
- `model/objects.py`
- `model/scenario.py`
- `persistence/scenario_file.py`
- `gui/views.py`
- `gui/main_window.py`
- `gui/tables.py`

## Remaining delivery process

1. Maintain regression coverage as additional Java-compatible behavior is
   implemented.
2. Validate representative scenarios after model, persistence, and GUI
   changes.
3. Run the application from source using the dedicated environment.
4. Build a Windows application with PyInstaller on a native Windows runner.
5. Build a macOS application bundle with PyInstaller on a native macOS runner.
6. Include resources, example scenarios, help content, and application
   metadata in each package.
7. Run a smoke test against each packaged application.
8. Add code signing and notarization for macOS distribution, and executable
   signing or an installer for Windows distribution when release distribution
   requires it.
