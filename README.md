*static analysis:*

[![Total alerts](https://img.shields.io/lgtm/alerts/g/sonic-net/sonic-utilities.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/sonic-net/sonic-utilities/alerts/)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/sonic-net/sonic-utilities.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/sonic-net/sonic-utilities/context:python)

*sonic-utilities builds:*

[![master build](https://dev.azure.com/mssonic/build/_apis/build/status/Azure.sonic-utilities?branchName=master&label=master)](https://dev.azure.com/mssonic/build/_build/latest?definitionId=55&branchName=master)

[![202205 build](https://dev.azure.com/mssonic/build/_apis/build/status/Azure.sonic-utilities?branchName=202205&label=202205)](https://dev.azure.com/mssonic/build/_build/latest?definitionId=55&branchName=202205)

[![202012 build](https://dev.azure.com/mssonic/build/_apis/build/status/Azure.sonic-utilities?branchName=202012&label=202012)](https://dev.azure.com/mssonic/build/_build/latest?definitionId=55&branchName=202012)


# SONiC: Software for Open Networking in the Cloud

## sonic-utilities

Command-line utilities for SONiC

This repository produces two packages, as follows:

### sonic-utilities

A Python wheel package, containing all the Python source code for the command-line utilities

#### Setting up a build/test environment

The sonic-utilities package depends on a number of other packages, many of which are available via PyPI, but some are part of the SONiC codebase. When building/testing the package, setuptools/pip will attempt to install the packages available from PyPI. However, you will need to manually build and install the SONiC dependencies before attempting to build or test the package.

Currently, this list of dependencies is as follows:


- libyang_1.0.73_amd64.deb
- libyang-cpp_1.0.73_amd64.deb
- python3-yang_1.0.73_amd64.deb
- redis_dump_load-1.1-py3-none-any.whl
- sonic_py_common-1.0-py3-none-any.whl
- sonic_config_engine-1.0-py3-none-any.whl
- sonic_yang_mgmt-1.0-py3-none-any.whl
- sonic_yang_models-1.0-py3-none-any.whl
- python-swsscommon_1.0.0_amd64.deb


A convenient alternative is to let the SONiC build system configure a build enviroment for you. This can be done by cloning the [sonic-buildimage](https://github.com/sonic-net/sonic-buildimage) repo, building the sonic-utilities package inside the Debian Buster slave container, and staying inside the container once the build finishes. During the build process, the SONiC build system will build and install all the necessary dependencies inside the container. After following the instructions to clone and initialize the sonic-buildimage repo, this can be done as follows:

1. Configure the build environment for an ASIC type (any type will do, here we use `generic`)
    ```
    make configure PLATFORM=generic
    ```

2. Build the sonic-utilities Python wheel package inside the Bullseye slave container, and tell the build system to keep the container alive when finished
    ```
    make -f Makefile.work BLDENV=bookworm KEEP_SLAVE_ON=yes target/python-wheels/bookworm/sonic_utilities-1.2-py3-none-any.whl
    ```

3. When the build finishes, your prompt will change to indicate you are inside the slave container. Change into the `src/sonic-utilities/` directory
    ```
    user@911799f161a0:/sonic$ cd src/sonic-utilities/
    ```

4. You can now make changes to the sonic-utilities source and build the package or run unit tests with the commands below. When finished, you can exit the container by calling `exit`.

#### To build

```
python3 setup.py bdist_wheel
```
Note: This command by default will not update the wheel package in target/. To specify the destination location of wheel package, use "-d" option.

#### To run unit tests

```
python3 setup.py test
```

#### To install the package on a SONiC machine
```
sudo pip uninstall sonic-utilities
sudo pip install YOUR_WHEEL_PACKAGE
```
Note: Don't use "--force-reinstall".

### sonic-utilities-data

A Debian package, containing data files needed by the utilities (bash_completion files, Jinja2 templates, etc.)

#### To build

Instructions for building the sonic-utilities-data package can be found in [sonic-utilities-data/README.md](https://github.com/sonic-net/sonic-utilities/blob/master/sonic-utilities-data/README.md)

---

## Contribution guide

Please read the [contributor guide](https://github.com/sonic-net/SONiC/wiki/Becoming-a-contributor) for more details on how to contribute.

All contributors must sign an [Individual Contributor License Agreement (ICLA)](https://docs.linuxfoundation.org/lfx/easycla/v2-current/contributors/individual-contributor) before contributions can be accepted. This process is now automated via a GitHub bot when submitting new pull request. If the contributor has not yet signed a CLA, the bot will create a comment on the pull request containing a link to electronically sign the CLA.

### GitHub Workflow

We're following basic GitHub Flow. If you have no idea what we're talking about, check out [GitHub's official guide](https://guides.github.com/introduction/flow/). Note that merge is only performed by the repository maintainer.

Guide for performing commits:

* Isolate each commit to one component/bugfix/issue/feature
* Use a standard commit message format:

>     [component/folder touched]: Description intent of your changes
>
>     [List of changes]
>
> 	  Signed-off-by: Your Name your@email.com

For example:

>     swss-common: Stabilize the ConsumerTable
>
>     * Fixing autoreconf
>     * Fixing unit-tests by adding checkers and initialize the DB before start
>     * Adding the ability to select from multiple channels
>     * Health-Monitor - The idea of the patch is that if something went wrong with the notification channel,
>       we will have the option to know about it (Query the LLEN table length).
>
>       Signed-off-by: John Doe user@dev.null


* Each developer should fork this repository and [add the team as a Contributor](https://help.github.com/articles/adding-collaborators-to-a-personal-repository)
* Push your changes to your private fork and do "pull-request" to this repository
* Use a pull request to do code review
* Use issues to keep track of what is going on
