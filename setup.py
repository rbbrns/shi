from setuptools import setup, find_packages

s = setup(
    name="shi",
    version="0.1.0",
    packages=find_packages(),
    author="Gemini",
    author_email="",
    description="A new Python library.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/shi",
    install_requires=[
        "lazy_object_proxy",
        "rich",
    ],
)
