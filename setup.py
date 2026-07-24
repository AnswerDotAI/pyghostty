import subprocess,sys
from pathlib import Path
from setuptools import Distribution,setup
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel

class BinaryDistribution(Distribution):
    def has_ext_modules(self): return True

class BinaryWheel(_bdist_wheel):
    def get_tag(self):
        _,_,plat = super().get_tag()
        return 'py3','none',plat

    def run(self):
        subprocess.run([sys.executable, str(Path(__file__).with_name('build_lib.py'))], check=True)
        super().run()

setup(cmdclass={'bdist_wheel': BinaryWheel}, distclass=BinaryDistribution)
