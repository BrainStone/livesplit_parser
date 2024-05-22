from setuptools import setup, find_packages
import codecs
import os

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

VERSION = '0.2.1.1'
DESCRIPTION = 'Parse LiveSplit data'


setup(
    name="livesplit_parser",
    version=VERSION,
    author="Trevor Bushnell",
    author_email="<tbushnell11@gmail.com>",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=long_description,
    packages=find_packages(),
    install_requires=['pandas', 'numpy', 'xmltodict', 'matplotlib', 'seaborn', 'datetime', 'xlsxwriter'],
    keywords=['python', 'speedrunning', 'livesplit']
)
