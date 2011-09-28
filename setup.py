import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "repositoryhandler",
    version = "0.3.6.3",
    author = "Chris Lewis",
    author_email = "cflewis@soe.ucsc.edu",
    description = ("A Python library for accessing source control repositories"),
    license = "GPL",
    keywords = "cvs svn git source sourcecontrol scm",
    url = "https://github.com/Lewisham/repositoryhandler",
    packages=['repositoryhandler', 'repositoryhandler/backends', 'tests'],
    long_description=read('README.mdown'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Version Control",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Environment :: Console"
    ],
)
