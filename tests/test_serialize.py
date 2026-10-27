import pytest
from pyghostty import Terminal, GhosttyError, UnknownSequence
from pyghostty._ffi import ffi, lib, check


def visual_style(t, x, y):
    style = t.style(x, y)
    cell = ffi.new('GhosttyCell*')
    check(lib.ghostty_grid_ref_cell(t.ref(x, y), cell), 'cell')
    tag = ffi.new('GhosttyCellContentTag*')
    check(lib.ghostty_cell_get(cell[0], lib.GHOSTTY_CELL_DATA_CONTENT_TAG, tag), 'tag')
    if tag[0] == lib.GHOSTTY_CELL_CONTENT_BG_COLOR_PALETTE:
        color = ffi.new('uint8_t*')
        check(lib.ghostty_cell_get(cell[0], lib.GHOSTTY_CELL_DATA_COLOR_PALETTE, color), 'palette')
        style['bg'] = ('palette', color[0])
    elif tag[0] == lib.GHOSTTY_CELL_CONTENT_BG_COLOR_RGB:
        color = ffi.new('GhosttyColorRgb*')
        check(lib.ghostty_cell_get(cell[0], lib.GHOSTTY_CELL_DATA_COLOR_RGB, color), 'rgb')
        style['bg'] = ('rgb', (color.r, color.g, color.b))
    return style


def assert_screen(a, b):
    assert a.text() == b.text()
    assert a.contents() == b.contents()
    assert a.cursor == b.cursor
    for y in range(a.size[1]):
        for x in range(a.size[0]):
            assert visual_style(a, x, y) == visual_style(b, x, y), (x, y)


@pytest.mark.parametrize('data', [
    b'', b'hello', b'hello\r\n\r\n', b'\x1b[31mhello\x1b[0m\r\nprompt> ',
    b'abcdefghijklmnopqrst', b'abcdefghijklmnopqrstuvwxyz' * 4, b' '*60, '日本語🙂e\u0301'.encode(),
    b''.join(f'line {i}\r\n'.encode() for i in range(40)),
    b'\x1b[44m\x1b[2J\x1b[Hhello', b'\x1b[48;2;10;20;30m\x1b[2J',
    b'\x1b[2;4r\x1b[?6hhello', b'\x1b[4hhello',
    b'\x1b[?2004h\x1b[?25lhello',
])
def test_serialize_screen(data):
    with Terminal(20, 5) as source, Terminal(20, 5) as restored:
        source.feed(data)
        restored.feed('stale\x1b[?1049hstale alternate\x1b]2;unfinished')
        before = (source.text(), source.contents(), source.cursor)
        snapshot = source.serialize()
        assert isinstance(snapshot, bytes)
        assert before == (source.text(), source.contents(), source.cursor)
        restored.feed(snapshot)
        assert_screen(source, restored)
        assert source.mode(2004) == restored.mode(2004)
        assert source.mode(25) == restored.mode(25)
        source.feed('!'); restored.feed('!')
        assert_screen(source, restored)


@pytest.mark.parametrize('prefix, suffix', [
    (b'hello\x1b[31', b'mRED'),
    (b'hello\x1b]2;ti', b'tle\x07world'),
    (b'hello\xe6', b'\x97\xa5world'),
    (b'hello\x1bP', b'abc\x1b\\world'),
])
@pytest.mark.parametrize('alternate', [False, True])
def test_serialize_continuation(prefix, suffix, alternate):
    with Terminal(20, 5) as source, Terminal(20, 5) as restored:
        if alternate: source.feed('primary\x1b[?1049h')
        source.feed(prefix)
        restored.feed(source.serialize())
        assert_screen(source, restored)
        source.feed(suffix); restored.feed(suffix)
        assert_screen(source, restored)
        if alternate:
            source.feed('\x1b[?1049l'); restored.feed('\x1b[?1049l')
            assert_screen(source, restored)


@pytest.mark.parametrize('entry', [47, 1047, 1049])
def test_serialize_alternate(entry):
    with Terminal(20, 5) as source, Terminal(20, 5) as restored:
        source.feed(''.join(f'line {i}\r\n' for i in range(12)))
        source.feed(f'\x1b[?{entry}h\x1b[H\x1b[32mALT\x1b[3;4H')
        before = source.serialize()
        restored.feed(before)
        assert source.serialize() == before
        assert_screen(source, restored)
        source.feed(f'\x1b[?{entry}l'); restored.feed(f'\x1b[?{entry}l')
        assert_screen(source, restored)
        source.feed('after'); restored.feed('after')
        assert_screen(source, restored)


def test_serialize_continuation_limit():
    with Terminal(20, 5, continuation_limit=4) as t:
        t.feed(b'\x1b]2;long unfinished')
        with pytest.raises(GhosttyError): t.serialize()
        t.feed(b'\x07')
        assert isinstance(t.serialize(), bytes)


@pytest.mark.parametrize('primary', [
    '\x1b[31;44mprimary',
    '\x1b[2;4r\x1b[?6hprimary',
    '\x1b[4hprimary',
])
def test_serialize_alternate_with_primary_modes(primary):
    with Terminal(20, 5) as source, Terminal(20, 5) as restored:
        source.feed(primary + '\x1b[?1049h\x1b[0m\x1b[HALT')
        restored.feed(source.serialize())
        assert_screen(source, restored)
        source.feed('\x1b[?1049lafter'); restored.feed('\x1b[?1049lafter')
        assert_screen(source, restored)


def test_serialize_palette_and_tabs():
    with Terminal(20, 5) as source, Terminal(20, 5) as restored:
        source.feed('\x1b]4;1;rgb:12/34/56\x1b\\\x1b[31mred\x1b[0m')
        source.feed('\x1b[3g\x1b[6G\x1bH\r')
        restored.feed(source.serialize(palette=True))
        replies = [[], []]
        for t, out in zip((source, restored), replies):
            t.on_reply(out.append)
            t.feed('\x1b]4;1;?\x07\t!')
        assert replies[0] == replies[1]
        assert_screen(source, restored)


def test_serialize_does_not_fire_source_callbacks():
    with Terminal(20, 5) as t:
        replies, unknown = [], []
        t.on_reply(replies.append)
        t.on_unknown_sequence(unknown.append)
        t.feed('primary\x1b[?1049h\x1b]7770;unfinished')
        t.serialize()
        assert not replies and not unknown
        t.feed('\x07')
        assert unknown == [UnknownSequence('osc', b'7770;unfinished', False, 'bel')]


def test_xterm_roundtrip():
    "Optional comparison with xterm.js, including live output after restoration."
    import base64
    import json
    import os
    from pathlib import Path
    import subprocess

    if not os.environ.get('PYGHOSTTY_XTERM_MODULE'):
        pytest.skip('set PYGHOSTTY_XTERM_MODULE to the installed @xterm/headless path')
    cases = []
    for label, data, suffix in [
        ('prompt', b'\x1b[31mhello\x1b[0m\r\nprompt> ', b'text'),
        ('history', b''.join(f'line {i}\r\n'.encode() for i in range(40)), b'next'),
        ('wrap', b'abcdefghijklmnopqrstuvwxyz'*4, b'next'),
        ('background', b'\x1b[44m\x1b[2Jhello', b'next'),
        ('origin', b'\x1b[2;4r\x1b[?6hhello', b'\r\nnext'),
        ('alternate', b'primary\x1b[?1049hALT', b'\x1b[?1049lafter'),
        ('partial CSI', b'hello\x1b[31', b'mRED'),
        ('partial UTF8', b'hello\xe6', b'\x97\xa5world'),
        ('wide wrap', ('日本語'*20).encode(), b'next'),
        ('pending wrap', b'x'*100, b'next'),
        ('alternate colors', b'\x1b[31;44mprimary\x1b[?1049h\x1b[0m\x1b[2J\x1b[HALT', b'\x1b[?1049lafter'),
        ('alternate partial UTF8', b'primary\x1b[?1049hhello\xe6', b'\x97\xa5\x1b[?1049lafter'),
    ]:
        with Terminal(20, 5) as t:
            t.feed(data)
            encoded = [base64.b64encode(v).decode() for v in (data, t.serialize(), suffix)]
            cases.append(dict(zip(('label', 'data', 'snapshot', 'suffix'), (label, *encoded))))
    result = subprocess.run(
        ['node', str(Path(__file__).with_name('xterm_roundtrip.cjs'))],
        input=json.dumps(cases), text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_serialize_tracking_disabled():
    with Terminal(20, 5, continuation_limit=0) as t:
        t.feed('hello')
        assert t.serialize()
        t.feed('\x1b[')
        with pytest.raises(GhosttyError): t.serialize()


@pytest.mark.parametrize('data', [
    '日本語🙂' * 15,
    'x' * 100,
    '\x1b[?69h\x1b[3;15s\x1b[2;4r\x1b[?6hhello',
    '\x1b]8;;https://example.com\x1b\\hello',
    '\x1b(0lqqk\x1b(B',
])
def test_serialize_special_state(data):
    with Terminal(20, 5) as source, Terminal(20, 5) as restored:
        source.feed(data)
        restored.feed(source.serialize())
        assert_screen(source, restored)
        source.feed('next'); restored.feed('next')
        assert_screen(source, restored)
        source.resize(12, 8); restored.resize(12, 8)
        assert_screen(source, restored)
