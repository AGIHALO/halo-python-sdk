from setuptools import setup, find_packages
import os

# Read README if available
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r") as f:
        long_description = f.read()

setup(
    name="halo-sdk",
    version="0.1.3",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "web3>=6.0.0",
        "google-generativeai>=0.3.0",
        "eth-account>=0.5.9"
    ],
    author="Halo Team",
    description="Python SDK for Halo API with built-in x402 auto-payment",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="halo, x402, payment, ai, llm, gemini",
    python_requires=">=3.7",
)
