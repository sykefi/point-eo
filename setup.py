from setuptools import setup, find_packages

setup(
    name='point_eo',
    version='0.1.dev',
    packages=find_packages(include=['point_eo']),
    package_dir={'':'src'},
    entry_points={
        "console_scripts": [
            "point_eo=point_eo:main",
            "point-eo=point_eo:main"
        ]
    }
)