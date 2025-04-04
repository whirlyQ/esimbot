from setuptools import setup, find_packages

setup(
    name="esimbot",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "httpx==0.23.3",  # Pin to version compatible with solana
        "python-telegram-bot==20.8",
        "python-dotenv==1.0.1",
        "requests==2.31.0",
        "aiohttp==3.9.3",
        "certifi==2024.2.2",
        "solders==0.19.0",
        "base58==2.1.1",
        # solana is installed separately
    ],
    # Prevent automatic dependency resolution for these packages
    dependency_links=[],
)
