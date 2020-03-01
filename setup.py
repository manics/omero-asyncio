import setuptools

setuptools.setup(
    name="omero-asyncio",
    url="https://github.com/manics/omero-asyncio",
    author="Simon Li",
    description="OMERO.py client and services that works with asyncio.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    use_scm_version={"write_to": "omero_asyncio/_version.py"},
    packages=setuptools.find_packages(),
    setup_requires=["setuptools_scm"],
    install_requires=["omero-py>=5.6.0"],
    # tests_require=["pytest"],
    python_requires=">=3.5",
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering",
    ],
)
