from setuptools import setup, find_packages

setup(
    name="aps-cli",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "aps_cli=aps_cli.main:cli",
        ],
    },
)
