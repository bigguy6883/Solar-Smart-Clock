"""Setup script for Solar Smart Clock."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="solar-clock",
    version="2.0.0",
    author="Solar Clock Contributors",
    description="A Raspberry Pi solar clock with multiple views",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bigguy6883/Solar-Smart-Clock",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.9",
    install_requires=[
        "Pillow>=10.0.0",
        "requests>=2.31.0",
        "astral>=3.2",
        "ephem>=4.1.0",
    ],
    extras_require={
        "touch": ["evdev>=1.6.0"],
        "dev": [
            "pytest>=7.4.0",
            "pytest-mock>=3.11.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "mypy>=1.5.0",
            "flake8>=6.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "solar-clock=solar_clock.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Home Automation",
        "Topic :: Scientific/Engineering :: Astronomy",
    ],
    keywords="raspberry-pi solar clock weather display framebuffer",
)
