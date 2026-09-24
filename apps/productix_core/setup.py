from setuptools import setup, find_packages

setup(
    name="productix_core",
    version="1.0.0",
    description="Productix Core platform — settings, licensing/tenancy, module registry, shared audit log, shared utilities",
    author="TechoHub",
    author_email="support@techohub.net",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[],
)