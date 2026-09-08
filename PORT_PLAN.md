# Python Reimplementation and Desktop Packaging Plan

## Objective

Create a Python reimplementation of the Java **Spacetime** application that preserves its special-relativity functionality, supports existing `.sce` scenario files, and can be distributed as pre-built applications for Windows and macOS.

## Recommended technology

- Python 3.12+
- PySide6 / Qt for the desktop interface
- Custom Qt painting or PyQtGraph for the Highway and spacetime diagram
- `pytest` for physics, persistence, and integration tests
- PyInstaller for self-contained application bundles
- GitHub Actions for Windows and macOS release builds

## Phase 1: Define existing behavior

Create a functional specification from the Java source and HTML help files.

Document:

- Clock and light-flash objects
- Free events, worldline events, intersections, birth/termination events, and velocity-change events
- Piecewise-constant-velocity worldlines
- Reference-frame transformations
- Clock readings and proper-time calculations
- Highway and spacetime-diagram rendering rules
- Time stepping, dragging, keyboard shortcuts, zooming, panning, and context menus
- Undo/redo behavior
- Scenario save/load format
- Localization and user-visible terminology

Separate required compatibility from replaceable implementation details. Record known quirks so they can either be preserved deliberately or corrected explicitly.

## Phase 2: Build the Python domain model

Keep the physics and scenario model independent of the GUI.

Suggested structure:

```text
spacetime/
  model/
    scenario.py
    worldline.py
    objects.py
    events.py
    decorations.py
    lorentz.py
    units.py
  persistence/
    scenario_file.py
  gui/
    main_window.py
    highway_view.py
    diagram_view.py
    object_table.py
    event_table.py
    help_view.py
  commands/
    undo_redo.py
  resources/
    translations/
    help/
```

Use dataclasses, enums, type annotations, and explicit validation.

Suggested model mapping:

| Java concept | Python equivalent |
|---|---|
| `Scenario` | Scenario state and object/event/decorations collections |
| `STObject` | Base worldline object |
| `STClock` | Clock with proper-time display |
| `STFlash` | Light-speed object |
| `WorldlineRecord` | Position/time/old-beta/new-beta segment record |
| `STEvent` | Event in spacetime |
| `STInterval` | Interval decoration |
| `STLightCone` | Light-cone decoration |
| `STHyperbola` | Invariant-interval hyperbola |
| `HistoryWriter` | Command-based undo/redo manager |

## Phase 3: Implement and validate the physics

Implement:

- Lorentz coordinate transformation:

  ```text
  x' = gamma * (x - beta * t)
  t' = gamma * (t - beta * x)
  ```

- Relativistic velocity addition
- `gamma = 1 / sqrt(1 - beta²)`
- Piecewise-linear worldline positions
- Proper time along a worldline
- Clock synchronization and readings
- Timelike, spacelike, and lightlike interval classification
- Light-cone equations
- Invariant hyperbolas
- Object existence between birth and termination

Add focused tests for:

- Transforming to a frame and back
- Velocity addition near zero and near the speed of light
- Stationary and moving clocks
- Light flashes
- Programmed velocity changes
- Twin-paradox scenarios
- Worldline intersections
- Interval invariance across frames
- Boundary and invalid-value handling

Load the existing `.sce` files and compare calculated positions, velocities, event coordinates, and clock readings with the Java application where practical.

## Phase 4: Preserve scenario-file compatibility

Implement a dedicated `.sce` reader and writer rather than coupling parsing to GUI classes.

The existing Java Properties-based files contain:

- Global reference-frame velocity
- Current time
- Object, event, and decoration name lists
- Per-object metadata and worldline records
- Per-event coordinates and relationships
- Decoration parameters
- Scenario comments and counters

Recommended strategy:

1. Read existing files exactly as they are.
2. Preserve unknown properties when possible.
3. Write files in a stable, documented format.
4. Add round-trip tests for every bundled scenario.
5. Optionally introduce a new versioned JSON format later while retaining `.sce` import/export.

## Phase 5: Recreate the desktop interface

Use a `QMainWindow` with split or dockable panels:

- Highway view
- Spacetime diagram view
- Object table
- Event table
- Comments pane
- Current-time/status display

Implement the main views as custom Qt widgets:

- `HighwayView` renders horizontal position and the nonlinear beta/gamma vertical scale.
- `SpacetimeDiagramView` renders coordinates, worldlines, events, decorations, and the current simultaneity line.

Both views should observe the same scenario model so that dragging, editing, time changes, frame transformations, and selection updates remain synchronized.

Use Qt signals and slots for model/view synchronization rather than having drawing widgets directly manipulate unrelated state.

## Phase 6: Recreate interaction behavior

Implement the workflows in this order:

1. Create, move, edit, and delete clocks
2. Create light flashes
3. Create and edit events
4. Create events on worldlines and at intersections
5. Advance, rewind, reset, and manually set time
6. Program velocity changes
7. Set and cancel birth/termination
8. Transform up/down and return to the original frame
9. Construct intervals, light cones, and hyperbolas
10. Zoom and pan
11. Undo and redo
12. Load and save scenarios
13. Display bundled help and localized strings

Use a command pattern for all mutations, with commands such as:

```text
CreateObjectCommand
MoveObjectCommand
ChangeVelocityCommand
CreateEventCommand
DeleteEventCommand
ChangeReferenceFrameCommand
SetBirthCommand
SetTerminationCommand
```

## Phase 7: Improve compatibility and usability

After core behavior is correct:

- Match existing keyboard shortcuts and context menus
- Support Windows, macOS, mouse, and trackpad behavior
- Add high-DPI rendering
- Make fonts, colors, and labels theme-aware
- Add accessible table navigation and menu actions
- Handle locale-specific number formatting safely
- Make help files work from source and packaged applications
- Add recent-files support and clearer errors if desired

Avoid changing physics or interaction semantics during this phase unless the change is intentional and documented.

## Phase 8: Package for Windows and macOS

Use a single source tree with platform-specific GitHub Actions jobs.

Build on native runners:

```text
windows-latest
macos-latest
```

Each release job should:

1. Install Python and dependencies.
2. Run unit and integration tests.
3. Build with PyInstaller.
4. Bundle resources, translations, help, and example scenarios.
5. Run a smoke test.
6. Upload the platform artifact.

Outputs:

- Windows `.exe` application, optionally with an installer
- macOS `.app`, optionally packaged as a `.dmg`

For macOS distribution outside a local machine, add Apple code signing and notarization. For Windows distribution, consider executable signing and an installer built with Inno Setup or WiX.

Briefcase is an alternative packaging approach if native application bundles and installers are preferred, but PyInstaller is the lower-risk initial choice for this application.

## Phase 9: Regression and release strategy

Maintain golden scenarios based on the bundled `.sce` files:

- Twin paradox
- Accelerated twin paradox
- Trip to Alpha
- Simultaneity
- Velocity addition
- Accelerating rods
- Light-flash and beacon scenarios

For each scenario, verify:

- It opens successfully.
- Object and event counts match.
- Worldline data is preserved.
- Frame transformations remain valid.
- Clock readings are consistent.
- Decorations render without errors.
- Saving and reopening produces equivalent state.

Release in stages:

1. Physics library prototype
2. Scenario-file-compatible command-line validator
3. Basic GUI with both displays
4. Feature-complete desktop beta
5. Windows/macOS packaged beta
6. Compatibility and usability release

## Key architectural principle

Keep the relativity model, persistence layer, undo/redo system, and GUI independent. This makes the physics testable without a window, preserves compatibility with existing scenarios, and reduces the risk that interface or packaging changes alter program behavior.
