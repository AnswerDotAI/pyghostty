"Layer 1: Pythonic API over the raw binding -- only what current consumers need."
import weakref
from typing import NamedTuple
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

class UnknownSequence(NamedTuple):
    "A complete APC or OSC sequence that libghostty-vt does not implement, as passed to `Terminal.on_unknown_sequence` handlers."
    kind: str        # 'apc' or 'osc'
    content: bytes   # Everything between the introducer and the terminator. For OSC it starts with the command number
    truncated: bool  # Whether `content` was cut at the handler's `max_bytes`
    terminator: str  # How an OSC ended, 'bel' or 'st', or None for APC. End any reply the same way

def _unknown_seq(s):
    "`UnknownSequence` copied out of the borrowed C struct `s`, or None for a sequence kind this binding does not know."
    if s.tag == lib.GHOSTTY_TERMINAL_UNKNOWN_SEQUENCE_OSC: v,kind = s.value.osc,'osc'
    elif s.tag == lib.GHOSTTY_TERMINAL_UNKNOWN_SEQUENCE_APC: v,kind = s.value.apc,'apc'
    else: return None
    content = ffi.buffer(v.content.ptr, v.content.len)[:] if v.content.len else b''
    term = ('bel' if v.terminator == lib.GHOSTTY_OSC_TERMINATOR_BEL else 'st') if kind == 'osc' else None
    return UnknownSequence(kind, content, bool(v.truncated), term)

class Terminal:
    "A headless Ghostty terminal: feed VT bytes, inspect the emulated state."
    def __init__(
        self,
        cols=80, # Width in cells
        rows=24, # Height in cells
        scrollback=10_000, # Most scrollback lines kept
        fg=None, # Default foreground colour as an `(r, g, b)` tuple, or None to leave it unset
        bg=None, # Default background colour as an `(r, g, b)` tuple, or None to leave it unset
    ):
        self._t = ffi.new('GhosttyTerminal*')
        check(lib.ghostty_terminal_new(ffi.NULL, self._t, cols, rows), 'terminal_new')
        check(lib.ghostty_terminal_set(self._t[0], lib.GHOSTTY_TERMINAL_OPT_SCROLLBACK_MAX_LINES, ffi.new('size_t*', scrollback)), 'set scrollback')
        for opt, rgb in ((lib.GHOSTTY_TERMINAL_OPT_COLOR_FOREGROUND, fg), (lib.GHOSTTY_TERMINAL_OPT_COLOR_BACKGROUND, bg)):
            if rgb is not None: check(lib.ghostty_terminal_set(self._t[0], opt, ffi.new('GhosttyColorRgb*', dict(zip('rgb', rgb)))), 'set color')
        self._unknown_cb = self._reply_cb = self._cb_err = None
        self._free = weakref.finalize(self, lib.ghostty_terminal_free, self._t[0])

    def feed(self, data):
        if isinstance(data, str): data = data.encode()
        lib.ghostty_terminal_vt_write(self._t[0], data, len(data))
        self._raise_cb_err()

    def feed_until_ground(self, data):
        """Feed only the shortest prefix of `data` that finishes the sequence in progress, returning how many bytes it consumed.
        Returns 0 when the parser is already outside any sequence, and None when all of `data` was consumed without finishing it."""
        if isinstance(data, str): data = data.encode()
        n = ffi.new('size_t*')
        res = lib.ghostty_terminal_vt_write_until_ground(self._t[0], data, len(data), n)
        self._raise_cb_err()
        if res == lib.GHOSTTY_NO_VALUE: return None
        check(res, 'vt_write_until_ground')
        return n[0]

    def on_unknown_sequence(self, fn, max_bytes=4096):
        """Call `fn(UnknownSequence)` for each complete APC or OSC sequence libghostty-vt does not implement. Keep at most
        `max_bytes` of each. `fn=None` stops reporting. An exception from `fn` is raised by the `feed` call that triggered it."""
        def _cb(t, u, s):
            if (seq := _unknown_seq(s)) is not None: fn(seq)
        self._unknown_cb = ffi.NULL if fn is None else ffi.callback('GhosttyTerminalUnknownSequenceFn', _cb, onerror=self._on_cb_err)
        check(lib.ghostty_terminal_set(self._t[0], lib.GHOSTTY_TERMINAL_OPT_UNKNOWN_SEQUENCE, self._unknown_cb), 'set unknown_sequence')
        mx = ffi.new('size_t*', 0 if fn is None else max_bytes)
        check(lib.ghostty_terminal_set(self._t[0], lib.GHOSTTY_TERMINAL_OPT_UNKNOWN_MAX_BYTES, mx), 'set unknown_max_bytes')

    def on_reply(self, fn):
        """Call `fn(bytes)` for each reply the terminal writes back to the program, such as a cursor position report
        (`GHOSTTY_TERMINAL_OPT_WRITE_PTY`). `fn=None` stops reporting. An exception from `fn` is raised by the `feed` call that triggered it."""
        self._reply_cb = ffi.NULL if fn is None else ffi.callback('GhosttyTerminalWritePtyFn', lambda t, u, d, n: fn(ffi.buffer(d, n)[:]),
            onerror=self._on_cb_err)
        check(lib.ghostty_terminal_set(self._t[0], lib.GHOSTTY_TERMINAL_OPT_WRITE_PTY, self._reply_cb), 'set write_pty')

    def _on_cb_err(self, exc, val, tb):
        "Keep the first exception a callback raised, for `_raise_cb_err`. cffi calls this as the callback's `onerror`."
        if self._cb_err is None: self._cb_err = val

    def _raise_cb_err(self):
        if (e := self._cb_err) is not None:
            self._cb_err = None
            raise e

    def get(self, key, ctype='uint16_t'):
        "One `ghostty_terminal_get` value; `key` names a GHOSTTY_TERMINAL_DATA_* suffix, e.g. 'cursor_x'."
        out = ffi.new(ctype+'*')
        check(lib.ghostty_terminal_get(self._t[0], getattr(lib, f'GHOSTTY_TERMINAL_DATA_{key.upper()}'), out), f'terminal_get {key}')
        return out[0]

    def mode(self, n, ansi=False):
        "Whether mode `n` is set: a DEC private mode such as 2004 (bracketed paste), or with `ansi` an ANSI mode such as 4 (insert)."
        c = ffi.new('GhosttyTerminalModeConfig*')
        c.mode = (n & 0x7FFF) | (ansi << 15)  # ghostty_mode_new's packing, done here because the C function is static inline
        check(lib.ghostty_terminal_get(self._t[0], lib.GHOSTTY_TERMINAL_DATA_MODE, c), f'terminal_get mode {n}')
        return bool(c.value)

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

    _STYLE_ATTRS = ('bold','italic','faint','blink','inverse','invisible','strikethrough','overline')

    def style(self, x, y, tag='active'):
        """The style at (`x`,`y`) as a dict: the boolean attributes, `underline` (0 = none), and
        `fg`/`bg`/`underline_color` as None, `('palette', n)`, or `('rgb', (r,g,b))`."""
        st = init_sized('GhosttyStyle')
        check(lib.ghostty_grid_ref_style(self.ref(x, y, tag), st), f'style {x},{y}')
        def color(c):
            if c.tag == lib.GHOSTTY_STYLE_COLOR_PALETTE: return ('palette', c.value.palette)
            if c.tag == lib.GHOSTTY_STYLE_COLOR_RGB: return ('rgb', (c.value.rgb.r, c.value.rgb.g, c.value.rgb.b))
            return None
        d = {a: bool(getattr(st, a)) for a in self._STYLE_ATTRS}
        return d | dict(underline=st.underline, fg=color(st.fg_color), bg=color(st.bg_color),
                        underline_color=color(st.underline_color))

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
        "Free the native terminal now. Garbage collection frees it otherwise."
        self._free()
        self._t = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
