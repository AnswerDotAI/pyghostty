# pyghostty

Unofficial (but complete) python bindings for [libghostty-vt](https://mitchellh.com/writing/libghostty-is-coming). `libghostty` is Ghostty's embeddable terminal emulation core, a headless, high-fidelity VT emulator. These bindings cover terminal state, screen and scrollback snapshots, kitty graphics, and everything else Ghostty's production terminal core handles.

The binding is Python-ABI-independent: pure Python (cffi ABI mode) over a bundled `libghostty-vt` shared library, so one wheel per platform covers every Python version. No compiler is needed at install time.

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

Source installs, including editable installs, build the shared library automatically. The build fetches the pinned Ghostty revision into
`build/ghostty/<revision>/` and uses the Zig toolchain supplied by the package's build dependencies. Git and network access are needed for the first build;
later builds reuse the checkout and Zig's compilation cache. A sibling Ghostty checkout is not needed.

To build from an existing checkout instead:

```bash
GHOSTTY_SRC=/path/to/ghostty python build_lib.py
```

The checkout must be at the revision pinned in `pyproject.toml`; the build never changes it. Running `build_lib.py` directly requires the pinned
`ziglang` version in your Python environment. This runs `zig build -Demit-lib-vt=true` and copies the resulting shared library into `pyghostty/_lib/`.

## Development

```bash
pip install -e .[dev]
pytest -q
```

After changing the Ghostty pin, reinstall the editable package (`ws-sync` does this in a uv workspace). After changing a checkout supplied with
`GHOSTTY_SRC`, rerun `build_lib.py`. Regenerate `_cdef.py` with `gen_cdef.py` when updating the pinned revision.

### Versioning

Version lives in `pyghostty/__init__.py` as `__version__`.

### Releases

Pushing a `v*` tag runs `.github/workflows/release.yml`, which builds and tests one Python-ABI-independent wheel for each supported platform and publishes the wheels to GitHub and PyPI. Releases are wheel-only; source remains available from the corresponding GitHub tag.
