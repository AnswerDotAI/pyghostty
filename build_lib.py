#!/usr/bin/env python3
"Build libghostty-vt from a ghostty checkout and bundle the shared lib into pyghostty/_lib."
import importlib.metadata,os,re,shlex,shutil,subprocess,sys,tempfile,tomllib
from pathlib import Path

ROOT = Path(__file__).parent

def build_config():
    with open(ROOT/'pyproject.toml', 'rb') as f: return tomllib.load(f)['tool']['pyghostty']

def _sdk_version(path):
    m = re.search(r'MacOSX(\d+(?:\.\d+)*)\.sdk$', str(path.resolve()))
    return tuple(int(o) for o in m.group(1).split('.')) if m else ()

def _current_sdk_version():
    res = subprocess.run(['xcrun', '--sdk', 'macosx', '--show-sdk-version'], capture_output=True, text=True)
    if res.returncode: sys.exit(res.stderr.strip())
    return tuple(int(o) for o in res.stdout.strip().split('.'))

# Zig 0.15 cannot link against macOS SDK 26.4+, so route xcrun to the newest older SDK.
def _legacy_sdk():
    if p := os.environ.get('GHOSTTY_SDK'): candidates = [Path(p).expanduser()]
    else:
        candidates = list(Path('/Applications').glob('Xcode*.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX*.sdk'))
        candidates += list(Path('/Library/Developer/CommandLineTools/SDKs').glob('MacOSX*.sdk'))
    candidates = [p.resolve() for p in candidates if p.exists() and _sdk_version(p) and _sdk_version(p) < (26,4)]
    if not candidates: sys.exit("No pre-26.4 macOS SDK found; set GHOSTTY_SDK")
    return max(candidates, key=_sdk_version)

def _shim_developer_dir(tmp, sdk):
    if not sdk.exists(): sys.exit(f"No pre-26.4 SDK at {sdk}; set GHOSTTY_SDK")
    bindir = tmp/'usr'/'bin'
    bindir.mkdir(parents=True)
    xcrun = bindir/'xcrun'
    xcrun.write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(str(sdk))}\n")
    xcrun.chmod(0o755)
    return tmp

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

def _zig_build(src, env, prefix):
    return subprocess.run([sys.executable, '-m', 'ziglang', 'build', '-Demit-lib-vt=true', '-Doptimize=ReleaseFast', '--prefix', str(prefix)],
        cwd=src, env=env)

def main():
    cfg = build_config()
    try: zig_version = importlib.metadata.version('ziglang')
    except importlib.metadata.PackageNotFoundError: sys.exit(f"Install ziglang=={cfg['zig-version']}")
    if zig_version != cfg['zig-version']: sys.exit(f"ziglang is {zig_version}; expected {cfg['zig-version']}")
    src,env = ghostty_src(),dict(os.environ)
    with tempfile.TemporaryDirectory() as tmp:
        tmp,prefix = Path(tmp),Path(tmp)/'out'
        if sys.platform == 'darwin' and _current_sdk_version() >= (26,4):
            env['DEVELOPER_DIR'] = str(_shim_developer_dir(tmp/'developer', _legacy_sdk()))
        # Ghostty also builds static/xcframework outputs which may fail; this package only needs the shared artifact.
        res = _zig_build(src, env, prefix)
        lib,name = _built_lib(prefix, res.returncode)
        dest = ROOT/'pyghostty'/'_lib'
        dest.mkdir(exist_ok=True)
        for old in dest.glob('libghostty-vt*'): old.unlink()
        shutil.copy2(lib, dest/name)
        print(f'Bundled: {name} (from {lib.name})')

if __name__=='__main__': main()
