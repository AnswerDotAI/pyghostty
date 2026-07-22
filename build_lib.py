"Build libghostty-vt from a ghostty checkout and bundle the shared lib into pyghostty/_lib."
import os,shutil,subprocess,sys
from pathlib import Path

def main():
    src = Path(os.environ.get('GHOSTTY_SRC', '../ghostty')).expanduser().resolve()
    if not (src/'build.zig').exists(): sys.exit(f"No ghostty checkout at {src}; set GHOSTTY_SRC")
    subprocess.run([sys.executable, '-m', 'ziglang', 'build', '-Demit-lib-vt=true', '-Doptimize=ReleaseFast'], cwd=src, check=True)
    dest = Path(__file__).parent/'pyghostty'/'_lib'
    dest.mkdir(exist_ok=True)
    libs = [p for p in (src/'zig-out'/'lib').iterdir() if p.suffix in ('.so','.dylib','.dll')]
    if not libs: sys.exit(f"No shared library found in {src/'zig-out'/'lib'}")
    for p in libs: shutil.copy2(p, dest/p.name)
    print('Bundled:', ', '.join(p.name for p in libs))

if __name__=='__main__': main()
