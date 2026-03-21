from setuptools import setup, find_packages

setup(
    name="gdes",
    version="1.0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": ["gdes=src.gdes:cli"],
    },
    python_requires=">=3.9",
)
