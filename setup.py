#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import sys
import os
from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(['--doctest-modules', 'tests', 'prbot'])
        sys.exit(errno)


version = os.environ.get('TSUNAMI_CLI_VERSION', '0.0.2')

setup(name='prbot',
      version=version,
      description='Automates Github PRs',
      tests_require=['pytest', 'requests-mock', 'mock'],
      install_requires=[],
      packages=['prbot'],
      scripts=['prbot'],
      cmdclass={'test': PyTest})
