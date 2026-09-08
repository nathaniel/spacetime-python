# Python port

All Python reimplementation code for Spacetime belongs under this directory.

The existing Java sources remain under `../spacetime/` and should not be modified as part of the Python port unless explicitly required for comparison or compatibility work.

The current Python desktop beta includes the core relativity model, Java
`.sce` compatibility, synchronized Highway and spacetime diagrams, object and
event editing, programming and lifetime events, decorations, undo/redo,
platform-aware menus and shortcuts, and bundled Help content. Focused tests
cover physics, persistence, editing, and light flashes.

Packaging is the remaining major delivery stage. Windows and macOS application
artifacts still need to be built and smoke-tested on their native runners,
with signing and notarization added if distribution requires them.
