"""
CARPI REDIS DATA BUS
(C) 2018, Raphael "rGunti" Guntersweiler
Licensed under MIT
"""

from setuptools import setup

with open('README.md', 'r') as f:
    long_description = f.read()

setup(name='carpi-dashdaemon',
      version='0.1.0',
      description='Daemon that processes data from different sources for a digital car dashboard.',
      long_description=long_description,
      url='https://github.com/rGunti/CarPi-DashDaemon',
      keywords='carpi dash daemon',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3.6'
      ],
      author='Raphael "rGunti" Guntersweiler',
      author_email='raphael@rgunti.ch',
      license='MIT',
      packages=['dashdaemon'],
      install_requires=[
          'wheel',
          'carpi-redisdatabus',
          'carpi-redisdatabus',
          'carpi-daemoncommons'
      ],
      zip_safe=False,
      include_package_data=True)
