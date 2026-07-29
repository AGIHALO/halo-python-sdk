from setuptools import setup, find_packages
import os
import re

# Read README if available
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        long_description = f.read()

with open(
    os.path.join("halo", "version.py"),
    "r",
    encoding="utf-8",
) as version_file:
    version_match = re.search(
        r'^__version__ = "([^"]+)"$',
        version_file.read(),
        re.MULTILINE,
    )
if not version_match:
    raise RuntimeError("Unable to determine package version")

setup(
    name="halo-sdk",
    version=version_match.group(1),
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "web3>=6.0.0",
        "google-genai>=1.0.0",
        "eth-account>=0.5.9"
    ],
    author="Halo Team",
    author_email="contact@agihalo.com",
    url="https://docs.agihalo.com/sdks/python/",
    project_urls={
        "Documentation": "https://docs.agihalo.com/sdks/python/",
        "Source": "https://github.com/AGIHALO/halo-python-sdk",
    },
    description="HALO SDK for Authentication, OAuth, Agent Memory, and x402 payments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="halo, authentication, oauth, memory, x402, payment, ai, llm",
    python_requires=">=3.9",
)
