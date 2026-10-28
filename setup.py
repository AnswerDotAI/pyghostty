import subprocess,sys
from pathlib import Path
from setuptools import Command,Distribution,setup
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
from setuptools.command.build import build as _build

class BuildNative(Command):
    user_options = []

    def initialize_options(self): pass
    def finalize_options(self): pass
    def get_source_files(self): return ['build_lib.py']

    def run(self):
        subprocess.run([sys.executable, str(Path(__file__).with_name('build_lib.py'))], check=True)

class Build(_build):
    sub_commands = [('build_native', None)] + _build.sub_commands

class BinaryDistribution(Distribution):
    def has_ext_modules(self): return True

class BinaryWheel(_bdist_wheel):
    def get_tag(self):
        _,_,plat = super().get_tag()
        return 'py3','none',plat

setup(cmdclass={'build': Build, 'build_native': BuildNative, 'bdist_wheel': BinaryWheel}, distclass=BinaryDistribution)
