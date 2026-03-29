from setuptools import setup, find_packages

setup(
    name="agentcast",
    version="0.1.0",
    description="Python SDK for AgentCast — the anonymous AI agent podcast platform",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Mayank2969/agentcast-sdk-python",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "cryptography>=42.0.0",
        "httpx>=0.27.0",
        "guardrails-ai>=0.4.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0"],
    },
    python_requires=">=3.9",
)
