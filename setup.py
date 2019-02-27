#!/usr/bin/env python3

from pathlib import Path

import setuptools
import setuptools.config
from pkg_resources import get_distribution, DistributionNotFound

CONFIG_FILE = Path(__file__).with_name("setup.cfg")


def use_rpm_installer_if_necessary(install_requires):
    """Replace rpm requirement with rpm-py-installer if the rpm package
    is not already available.

    https://github.com/junaruga/rpm-py-installer/blob/master/tests/sample/setup.py
    """

    for candidate in "rpm", "rpm-python":
        try:
            rpm_requirement = get_distribution(candidate).project_name
            break
        except DistributionNotFound:
            continue
    else:
        rpm_requirement = "rpm-py-installer"

    yield from map(
        lambda req: rpm_requirement if req.startswith("rpm") else req, install_requires
    )


install_requires = (
    setuptools.config.read_configuration(CONFIG_FILE)
    .get("options", {})
    .get("install_requires", [])
)
install_requires = use_rpm_installer_if_necessary(install_requires)

setuptools.setup(use_scm_version=True, install_requires=list(install_requires))
