"Layer 1: Pythonic API over the raw binding -- only what current consumers need."
from ._ffi import ffi,lib,check,GhosttyError,union_fn

def init_sized(ctype):
    "`ffi.new` a struct following the size-field convention, setting nested sizes recursively."
    p = ffi.new(ctype+'*')
    _set_sizes(p)
    return p

def _set_sizes(p):
    t = ffi.typeof(p).item
    for name,f in t.fields:
        if name=='size': p.size = ffi.sizeof(t)
        elif f.type.kind=='struct': _set_sizes(ffi.addressof(p[0], name))

def read_buf(call, what='format'):
    "Run the C API's query-size-then-fill buffer dance over `call(buf, buf_len, n_out)`, returning the bytes decoded."
    n = ffi.new('size_t*')
    call(ffi.NULL, 0, n)  # size query: OUT_OF_SPACE, with the required size in n
    buf = ffi.new('uint8_t[]', max(n[0], 1))
    check(call(buf, len(buf), n), what)
    return ffi.buffer(buf, n[0])[:].decode()

class Terminal:
    "A headless Ghostty terminal: feed VT bytes, inspect the emulated state."
    def __init__(self, cols=80, rows=24, scrollback=10_000):
        self._t = ffi.new('GhosttyTerminal*')
        opts = ffi.new('GhosttyTerminalOptions*', dict(cols=cols, rows=rows, max_scrollback=scrollback))
        check(lib.ghostty_terminal_new(ffi.NULL, self._t, opts[0]), 'terminal_new')

    def feed(self, data):
        if isinstance(data, str): data = data.encode()
        lib.ghostty_terminal_vt_write(self._t[0], data, len(data))

    def get(self, key, ctype='uint16_t'):
        "One `ghostty_terminal_get` value; `key` names a GHOSTTY_TERMINAL_DATA_* suffix, e.g. 'cursor_x'."
        out = ffi.new(ctype+'*')
        check(lib.ghostty_terminal_get(self._t[0], getattr(lib, f'GHOSTTY_TERMINAL_DATA_{key.upper()}'), out), f'terminal_get {key}')
        return out[0]

    @property
    def cursor(self): return self.get('cursor_x'), self.get('cursor_y')
    @property
    def size(self): return self.get('cols'), self.get('rows')

    def ref(self, x, y, tag='active'):
        "Untracked grid ref for (`x`,`y`) in coordinate system `tag` (active/viewport/screen/history); valid only until the next terminal mutation."
        fn = union_fn('ghostty_terminal_grid_ref', 'GhosttyResult(*)(GhosttyTerminal, GhosttyPointS, GhosttyGridRef*)')
        pt = ffi.new('GhosttyPointS*')
        pt.tag = getattr(lib, f'GHOSTTY_POINT_TAG_{tag.upper()}')
        pt.value.x, pt.value.y = x, y
        ref = init_sized('GhosttyGridRef')
        check(fn(self._t[0], pt[0], ref), f'grid_ref {tag} {x},{y}')
        return ref

    def _format_sel(self, sel, unwrap=False):
        "Plain-text rendering of `sel`, trailing whitespace trimmed."
        opts = init_sized('GhosttyTerminalSelectionFormatOptions')
        opts.emit = lib.GHOSTTY_FORMATTER_FORMAT_PLAIN
        opts.unwrap, opts.trim, opts.selection = unwrap, True, sel
        return read_buf(lambda b,l,n: lib.ghostty_terminal_selection_format_buf(self._t[0], opts[0], b, l, n))

    def text(self):
        "Plain-text of the visible screen (active area) only; rows as displayed, soft-wraps kept."
        cols,rows = self.size
        sel = init_sized('GhosttySelection')
        sel.start = self.ref(0, 0)[0]
        sel.end = self.ref(cols-1, rows-1)[0]
        return self._format_sel(sel)

    def contents(self):
        "Plain-text of everything: scrollback plus screen, soft-wraps unwrapped (Ghostty copy semantics)."
        sel = init_sized('GhosttySelection')
        r = lib.ghostty_terminal_select_all(self._t[0], sel)
        if r == lib.GHOSTTY_NO_VALUE: return ''
        check(r, 'select_all')
        return self._format_sel(sel, unwrap=True)

    def resize(self, cols, rows, cell_width_px=8, cell_height_px=16):
        "Resize, reflowing the primary screen; pixel cell size matters only for size reports and images."
        check(lib.ghostty_terminal_resize(self._t[0], cols, rows, cell_width_px, cell_height_px), 'resize')

    def close(self):
        if self._t is not None:
            lib.ghostty_terminal_free(self._t[0])
            self._t = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
