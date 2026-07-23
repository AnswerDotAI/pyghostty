#!/usr/bin/env python3
"Build libghostty-vt from a ghostty checkout and bundle the shared lib into pyghostty/_lib."
import os,shutil,subprocess,sys,tempfile
from pathlib import Path

def _shim_developer_dir(tmp):
    # zig 0.15.x can't link against Xcode >=26.4 SDKs (arm64e TBD entries; ziglang/zig#31658,
    # fixed only in 0.16, which ghostty doesn't build with yet). Workaround: an xcrun shim that
    # answers SDK queries with a pre-26.4 SDK, reached via DEVELOPER_DIR since /usr/bin/xcrun
    # re-execs $DEVELOPER_DIR/usr/bin/xcrun. Delete when ghostty moves to zig >=0.16.
    sdk = Path(os.environ.get('GHOSTTY_SDK', '/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk'))
    if not sdk.exists(): sys.exit(f"No pre-26.4 SDK at {sdk}; set GHOSTTY_SDK")
    bindir = tmp/'usr'/'bin'
    bindir.mkdir(parents=True)
    xcrun = bindir/'xcrun'
    xcrun.write_text(f"#!/bin/sh\necho {sdk}\n")
    xcrun.chmod(0o755)
    return tmp

def ghostty_src():
    "The ghostty checkout to build from: $GHOSTTY_SRC, defaulting to a sibling clone."
    src = Path(os.environ.get('GHOSTTY_SRC', '../ghostty')).expanduser().resolve()
    if not (src/'build.zig').exists(): sys.exit(f"No ghostty checkout at {src}; set GHOSTTY_SRC")
    return src

def main():
    src = ghostty_src()
    env = dict(os.environ)
    if sys.platform=='darwin':
        with tempfile.TemporaryDirectory() as tmp:
            env['DEVELOPER_DIR'] = str(_shim_developer_dir(Path(tmp)))
            res = _zig_build(src, env)
    else: res = _zig_build(src, env)
    # The xcrun shim breaks the static-lib/xcframework packaging steps (they need real lipo);
    # only the shared lib matters here, so success is judged by the artifact, not the exit code.
    dest = Path(__file__).parent/'pyghostty'/'_lib'
    dest.mkdir(exist_ok=True)
    libs = [p for p in (src/'zig-out'/'lib').iterdir()
            if p.suffix in ('.so','.dylib','.dll') and p.is_file() and not p.is_symlink()]
    if not libs: sys.exit(f"No shared library found in {src/'zig-out'/'lib'} (zig exit {res.returncode})")
    for p in libs:
        name = 'libghostty-vt'+p.suffix
        shutil.copy2(p, dest/name)
        print(f'Bundled: {name} (from {p.name})')

def _zig_build(src, env):
    return subprocess.run([sys.executable, '-m', 'ziglang', 'build', '-Demit-lib-vt=true', '-Doptimize=ReleaseFast'],
                          cwd=src, env=env)

if __name__=='__main__': main()
