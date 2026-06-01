# shared/types/setup.py
from setuptools import setup, find_packages

setup(
    name="agriculture-ai-shared",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.13.4",
        "pydantic-settings>=2.14.1",
        "sqlalchemy>=2.0.50",
        "psycopg2-binary>=2.9.12",
    ],
)