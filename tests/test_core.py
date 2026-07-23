from pyghostty import Terminal

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
