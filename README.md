# Spacetime

This repository contains the Python implementation of Spacetime, a special
relativity scenario editor.

The current desktop beta includes the core relativity model, Java
`.sce` compatibility, synchronized Highway and Spacetime Diagrams, object and
event editing, programming and lifetime events, decorations, undo/redo,
platform-aware menus and shortcuts, and bundled Help content. Focused tests
cover physics, persistence, editing, and light flashes.

Packaging is partly complete: an unsigned macOS application builds locally and
a Windows GitHub Actions workflow is configured. Linux packaging, packaged
smoke tests, and signing or notarization remain if distribution requires them.
