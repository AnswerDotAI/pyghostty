#!/usr/bin/env python3
"Build libghostty-vt from a ghostty checkout and bundle the shared lib into pyghostty/_lib."
import importlib.metadata,os,shutil,subprocess,sys,tempfile,tomllib
from pathlib import Path

ROOT = Path(__file__).parent

def build_config():
    with open(ROOT/'pyproject.toml', 'rb') as f: return tomllib.load(f)['tool']['pyghostty']

def ghostty_src():
    "The ghostty checkout to build from: $GHOSTTY_SRC, defaulting to a sibling clone."
    src = Path(os.environ.get('GHOSTTY_SRC', '../ghostty')).expanduser().resolve()
    if not (src/'build.zig').exists(): sys.exit(f"No ghostty checkout at {src}; set GHOSTTY_SRC")
    res = subprocess.run(['git', '-C', str(src), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    if res.returncode: sys.exit(res.stderr.strip())
    expected = build_config()['ghostty-rev']
    if (rev := res.stdout.strip()) != expected: sys.exit(f"Ghostty checkout is {rev}; expected {expected}")
    return src

def _built_lib(prefix, returncode):
    if sys.platform == 'win32': root,pattern,name = prefix/'bin','ghostty-vt.dll','libghostty-vt.dll'
    elif sys.platform == 'darwin': root,pattern,name = prefix/'lib','libghostty-vt*.dylib','libghostty-vt.dylib'
    else: root,pattern,name = prefix/'lib','libghostty-vt.so*','libghostty-vt.so'
    found = [p for p in root.glob(pattern) if p.is_file() and not p.is_symlink()]
    if len(found) != 1: sys.exit(f"Expected one shared library in {root}, found {found} (zig exit {returncode})")
    return found[0],name

def _zig_build(src, prefix):
    return subprocess.run([sys.executable, '-m', 'ziglang', 'build', '-Demit-lib-vt=true', '-Doptimize=ReleaseFast', '-Dcpu=baseline', '--prefix', str(prefix)],
        cwd=src)

def main():
    cfg = build_config()
    try: zig_version = importlib.metadata.version('ziglang')
    except importlib.metadata.PackageNotFoundError: sys.exit(f"Install ziglang=={cfg['zig-version']}")
    if zig_version != cfg['zig-version']: sys.exit(f"ziglang is {zig_version}; expected {cfg['zig-version']}")
    src = ghostty_src()
    with tempfile.TemporaryDirectory() as tmp:
        prefix = Path(tmp)/'out'
        # Ghostty also builds static/xcframework outputs which may fail; this package only needs the shared artifact.
        res = _zig_build(src, prefix)
        lib,name = _built_lib(prefix, res.returncode)
        dest = ROOT/'pyghostty'/'_lib'
        dest.mkdir(exist_ok=True)
        for old in dest.glob('libghostty-vt*'): old.unlink()
        shutil.copy2(lib, dest/name)
        print(f'Bundled: {name} (from {lib.name})')

if __name__=='__main__': main()
