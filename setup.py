from setuptools import setup, find_packages

setup(
    name='twotuft2count',
    version='0.1',
    description='A CLI pipeline for combining, segmenting, quantifying, and visualizing multiplexed imaging data.',
    author='Pascal Flüchter',
    author_email='pascal.fluechter@uzh.ch',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.9,<3.12',
    install_requires=[
        'numpy>=1.24,<2',
        'pandas>=1.5,<3',
        'tifffile>=2023.9.26',
        'scipy>=1.10,<2',
        'napari[all]>=0.5.6,<0.7',
        'magicgui>=0.8,<0.11',
        'click>=8,<9',
        'tifftools>=1.5,<2',
        'instanseg-torch>=0.1.1,<0.2',
        'fcswrite>=0.6,<0.7',
        'scikit-image>=0.21,<0.26'
    ],
    entry_points={
        'console_scripts': [
            'twotuft2count=twotuft2count.cli:main',
        ],
    },
)
