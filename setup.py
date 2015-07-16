from setuptools import setup

setup(
    name = 'ptmod-gui',
    version = '0.0.1',
    author = 'Rendaw',
    author_email = 'spoo@zarbosoft.com',
    url = 'https://github.com/Rendaw/ptmod-gui',
    download_url = 'https://github.com/Rendaw/ptmod-gui/tarball/v0.0.1',
    license = 'BSD',
    description = 'A GUI for editing polytaxis tags.',
    long_description = open('readme.md', 'r').read(),
    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
    ],
    install_requires = [
    ],
    packages = [
        'ptmod_gui', 
    ],
    entry_points = {
        'console_scripts': [
            'ptmod-gui = ptmod_gui.main:main',
        ],
    },
    include_package_resources=True,
    package_data={
        '': ['data/*.svg'],
    },
)
