from setuptools import setup, find_packages
from io import open

requirements = []

with open('requirements.txt') as f:
    lines = f.read().splitlines()
    for dependency in lines:
        dependency = dependency.strip()

        requirements.append(dependency)

setup(
    name='migrator',
    version='0.0.1',
    description='Migrator',
    author='Eduardo Cristiano Thums',
    author_email='eduardocristiano01@gmail.com',
    url='https://github.com/EduardoThums/migrator',
    python_requires=">=3.6, <4",
    packages=find_packages(),
    install_requires=requirements,
    include_package_data=True
)
