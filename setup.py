#!/usr/bin/env python
import codecs
import os
import sys

from setuptools import find_packages
from setuptools import setup

import versioneer


# Change to source's directory prior to running any command
try:
    SETUP_DIRNAME = os.path.dirname(__file__)
except NameError:
    # We're most likely being frozen and __file__ triggered this NameError
    # Let's work around that
    SETUP_DIRNAME = os.path.dirname(sys.argv[0])

if SETUP_DIRNAME != "":
    os.chdir(SETUP_DIRNAME)


def read(fname):
    """
    Read a file from the directory where setup.py resides
    """
    file_path = os.path.join(SETUP_DIRNAME, fname)
    with codecs.open(file_path, encoding="utf-8") as rfh:
        return rfh.read()


def parse_requirements():
    requirements = []
    requirements_file_path = os.path.join(SETUP_DIRNAME, "requirements", "base.txt")
    for line in read(requirements_file_path).splitlines():
        if line.startswith("#"):
            continue
        requirements.append(line.strip())
    return requirements


setup(
    name="pytest-salt-factories",
    version=versioneer.get_version(),
    author="Pedro Algarvio",
    author_email="pedro@algarvio.me",
    maintainer="Pedro Algarvio",
    maintainer_email="pedro@algarvio.me",
    license="Apache Software License 2.0",
    url="https://github.com/saltstack/pytest-salt-factories",
    description="Pytest Salt Plugin",
    long_description=read("README.rst"),
    packages=find_packages(),
    cmdclass=versioneer.get_cmdclass(),
    install_requires=parse_requirements(),
    extras_require={"docker": ["docker"], "salt": ["salt>=3000.1"]},
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Apache Software License",
    ],
    entry_points={
        "pytest11": [
            "salt-factories = saltfactories.plugin",
            "salt-factories-factories = saltfactories.plugins.factories",
            "salt-factories-markers = saltfactories.plugins.markers",
            "salt-factories-sysinfo = saltfactories.plugins.sysinfo",
            "salt-factories-sysstats = saltfactories.plugins.sysstats",
        ]
    },
)
