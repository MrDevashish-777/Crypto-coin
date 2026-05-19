"""
Project Setup Configuration
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="crypto-trading-signal-server",
    version="1.0.0",
    author="Crypto Trading Team",
    description="Professional-grade cryptocurrency trading signal server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        # Dependencies from requirements.txt will be installed via pip install -r requirements.txt
    ],
    entry_points={
        "console_scripts": [
            "crypto-bot=scripts.run_server:main",
        ],
    },
)
