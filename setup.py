from setuptools import setup

setup(name='lazy_drums',
      version='0.1',
      description='Minimal playback of MIDI drum sequences',
      url='http://github.com/erl-j/lazy-drums',
      author='erl-j',
      author_email='njona@kth.se',
      install_requires=[
          'numpy',
          'pedalboard',
          'matplotlib'
      ],
      license='MIT',
      packages=['lazy_drums'],
      include_package_data=True,
      zip_safe=False)