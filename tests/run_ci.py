"""Run the wheel tests with headless xterm.js available."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix='pyghostty-xterm-') as directory:
        subprocess.run([
            'npm', 'install', '--prefix', directory, '--ignore-scripts',
            '--no-audit', '--no-fund', '--package-lock=false', '@xterm/headless@6.0.0',
        ], check=True)
        env = os.environ | {
            'PYGHOSTTY_XTERM_MODULE': str(Path(directory) / 'node_modules' / '@xterm' / 'headless'),
        }
        return subprocess.run(
            [sys.executable, '-m', 'pytest', *sys.argv[1:]], env=env,
        ).returncode


if __name__ == '__main__':
    raise SystemExit(main())
