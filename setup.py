from setuptools import setup, find_packages
import os

# Read README if available
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r") as f:
        long_description = f.read()

setup(
    name="halo-sdk",
    version="0.1.4",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "web3>=6.0.0",
        "google-generativeai>=0.3.0",
        "eth-account>=0.5.9"
    ],
    author="Halo Team",
    url="https://docs.agihalo.com/sdks/python/",
    project_urls={
        "Documentation": "https://docs.agihalo.com/sdks/python/",
        "Source": "https://github.com/AGIHALO/halo-python-sdk",
    },
    description="HALO SDK for Authentication, OAuth, Agent Memory, and x402 payments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="halo, authentication, oauth, memory, x402, payment, ai, llm",
    python_requires=">=3.7",
)
