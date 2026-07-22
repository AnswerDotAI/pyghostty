# pyghostty

Python bindings for [libghostty](https://mitchellh.com/writing/libghostty-is-coming), Ghostty's embeddable terminal emulation core — a headless, high-fidelity VT emulator for Python: terminal state, screen and scrollback snapshots, kitty graphics, and everything else Ghostty's production terminal core handles.

The binding is ABI-stable: pure Python (cffi ABI mode) over a bundled `libghostty-vt` shared library, so one wheel per platform covers every Python version. No compiler is needed at install time.

## Building the library

The shared library is built from a ghostty checkout with the Zig toolchain (installed via pip as `ziglang`):

```bash
GHOSTTY_SRC=/path/to/ghostty python build_lib.py
```

This runs `zig build -Demit-lib-vt=true` in the checkout and copies the resulting shared library into `pyghostty/_lib/`, where the package loader and wheel builds pick it up.

## Development

```bash
pip install -e .[dev]
```

## Versioning

Version lives in `pyghostty/__init__.py` as `__version__`.
Bump it with:

```bash
ship-bump --part 2   # patch
ship-bump --part 1   # minor
ship-bump --part 0   # major
```

## Release

1) Ensure your GitHub issues are labeled (`bug`, `enhancement`, `breaking`).
2) Run:

```bash
ship-gh
ship-pypi
```
