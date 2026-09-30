import pytest
from pyghostty import Terminal, UnknownSequence

def test_feed_cursor_text():
    with Terminal(40, 10) as t:
        assert t.size == (40, 10)
        t.feed('Hello from \x1b[1;35mpyghostty\x1b[0m!\r\nsecond line')
        assert t.cursor == (11, 1)
        assert t.text() == 'Hello from pyghostty!\nsecond line'

def test_wrap():
    with Terminal(10, 4) as t:
        t.feed('abcdefghijklm')
        assert t.text() == 'abcdefghij\nklm'
        assert t.cursor == (3, 1)

def test_cursor_movement():
    with Terminal(20, 5) as t:
        t.feed('\x1b[3;5Hx')
        assert t.cursor == (5, 2)  # 0-indexed; CUP is 1-indexed

def test_wide_chars():
    with Terminal(20, 5) as t:
        t.feed('日本語')
        assert t.cursor == (6, 0)  # three double-width cells
        assert t.text() == '日本語'

def test_history_readback():
    "30 lines into 10 rows: text() is the visible screen, contents() includes scrollback."
    with Terminal(20, 10, scrollback=1000) as t:
        t.feed('\r\n'.join(f'line {i}' for i in range(30)))
        assert t.text().splitlines() == [f'line {i}' for i in range(20, 30)]
        assert t.contents().splitlines() == [f'line {i}' for i in range(30)]

def test_empty():
    with Terminal(10, 5) as t:
        assert t.text() == ''
        assert t.contents() == ''

def test_resize_reflow():
    with Terminal(10, 5) as t:
        t.feed('abcdefghijklmnop')
        assert t.text() == 'abcdefghij\nklmnop'
        t.resize(30, 5)
        assert t.size == (30, 5)
        assert t.text() == 'abcdefghijklmnop'
        assert t.cursor == (16, 0)

def test_resize_history_survives():
    with Terminal(20, 10, scrollback=1000) as t:
        t.feed('\r\n'.join(f'line {i}' for i in range(30)))
        t.resize(40, 5)
        assert t.contents().splitlines() == [f'line {i}' for i in range(30)]

def test_style_readback():
    with Terminal(20, 5) as t:
        t.feed('\x1b[2mdim\x1b[0m \x1b[1;31mboldred\x1b[0m plain')
        assert t.style(0, 0)['faint'] and not t.style(0, 0)['bold']
        br = t.style(4, 0)
        assert br['bold'] and br['fg'] == ('palette', 1) and not br['faint']
        pl = t.style(15, 0)
        assert not any(pl[a] for a in Terminal._STYLE_ATTRS) and pl['fg'] is None

def test_unknown_sequence_and_ground():
    "`on_unknown_sequence` receives an unimplemented OSC whole, even when it arrives split. `feed_until_ground` reports where it ends."
    with Terminal(20, 5) as t:
        seen = []
        t.on_unknown_sequence(seen.append)
        t.feed(b'a\x1b]7770;0;/tmp/')
        assert t.feed_until_ground(b'xy') is None     # still inside the OSC
        assert t.feed_until_ground(b'z\x07bc') == 2   # the BEL ends it, and b'bc' stays unfed
        assert seen == [UnknownSequence('osc', b'7770;0;/tmp/xyz', False, 'bel')]
        assert t.text() == 'a'
        assert t.feed_until_ground(b'bc') == 0        # already outside any sequence
        t.feed('\x1b]2;title\x07')                    # OSC 2 is implemented, so it is not reported
        assert len(seen) == 1
        t.on_unknown_sequence(lambda s: 1/0)
        with pytest.raises(ZeroDivisionError): t.feed('\x1b]7770;1;/\x07')

def test_modes_replies_and_colors():
    "`mode` reads DEC private and ANSI modes. `on_reply` receives the terminal's answers to queries, including colours set with `fg` and `bg`."
    with Terminal(20, 5, fg=(0xee, 0xee, 0xee), bg=(0x10, 0x20, 0x30)) as t:
        replies = []
        t.on_reply(replies.append)
        assert not t.mode(2004)
        t.feed('\x1b[?2004h')
        assert t.mode(2004)
        assert not t.mode(4, ansi=True)
        t.feed('\x1b[4h')                             # ANSI insert mode
        assert t.mode(4, ansi=True) and not t.mode(4)  # DEC mode 4 is a different mode
        t.feed('\x1b[6n\x1b]10;?\x07\x1b]11;?\x07')
        assert replies == [b'\x1b[1;1R', b'\x1b]10;rgb:eeee/eeee/eeee\x07', b'\x1b]11;rgb:1010/2020/3030\x07']
        t.on_reply(lambda r: 1/0)
        with pytest.raises(ZeroDivisionError): t.feed('\x1b[6n')
