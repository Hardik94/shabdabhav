from setuptools import setup, find_packages

setup(
    name="shabdabhav",
    version="0.1.0",
    packages=find_packages(include=["api", "api.*"]),  # ✅ only package `api`
    include_package_data=True,
)

