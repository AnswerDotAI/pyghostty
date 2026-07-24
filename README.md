# pyghostty

Unofficial (but complete) python bindings for [libghostty-vt](https://mitchellh.com/writing/libghostty-is-coming). `libghostty` is Ghostty's embeddable terminal emulation core, a headless, high-fidelity VT emulator for Python. These bindings cover terminal state, screen and scrollback snapshots, kitty graphics, and everything else Ghostty's production terminal core handles.

The binding is ABI-stable: pure Python (cffi ABI mode) over a bundled `libghostty-vt` shared library, so one wheel per platform covers every Python version. No compiler is needed at install time.

## Usage

```python
from pyghostty import Terminal

with Terminal(cols=80, rows=24) as t:
    t.feed('hello\r\nworld')
    t.cursor      # (x, y), 0-indexed
    t.text()      # plain text of the visible screen only
    t.contents()  # everything: scrollback plus screen, soft-wraps unwrapped
    t.resize(120, 24)  # reflows the primary screen
```

The base layer, `pyghostty._cdef`/`_ffi`, exposes the complete generated C API as raw `ffi`/`lib` (regenerate with `gen_cdef.py` after moving the pinned ghostty rev).

`pyghostty.core.Terminal` provides an ergonomic wrapper for commonly used parts.

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

### Versioning

Version lives in `pyghostty/__init__.py` as `__version__`.
