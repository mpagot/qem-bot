# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
"""Common type definitions."""

from typing import NamedTuple

from openqabot.config import OBS_REPO_TYPE


class Repos(NamedTuple):
    """Product and version information for a repository."""

    product: str
    version: str  # for SLFO it is the OBS project name; for others it is the product version
    arch: str
    product_version: str = ""  # if non-empty, "version" is the codestream version or OBS project


class ProdVer(NamedTuple):
    """Product and version details."""

    product: str
    version: str  # for SLFO it is the OBS project name; for others it is the product version
    product_version: str = ""  # if non-empty, "version" is the codestream version or OBS project

    def compute_url(
        self,
        base: str,
        product_name: str,
        arch: str,
        path: str = "repodata/repomd.xml",
    ) -> str:
        """Construct the repository URL for a Gitea submission."""
        # return codestream repo if product name is empty
        product = self.product.replace(":", ":/")
        version = self.version.replace(":", ":/")
        start = f"{base}/{product}:/{version}/{OBS_REPO_TYPE}"
        # for empty product assign something like `http://download.suse.de/ibs/SUSE:/SLFO:/1.1.99:/PullRequest:/166/standard/repodata/repomd.xml`
        # otherwise return product repo for specified product
        # assing something like `https://download.suse.de/ibs/SUSE:/SLFO:/1.1.99:/PullRequest:/166:/SLES/product/repo/SLES-15.99-x86_64/repodata/repomd.xml`
        if not product_name:
            return f"{start}/{path}"
        if not self.product_version:
            msg = f"Product version must be provided for {product_name}"
            raise ValueError(msg)
        return f"{start}/repo/{product_name}-{self.product_version}-{arch}/{path}"


class Data(NamedTuple):
    """Common data for dashboard and openQA."""

    submission: int
    submission_type: str
    settings_id: int
    flavor: str
    arch: str
    distri: str
    version: str
    build: str
    product: str


class ArchVer(NamedTuple):
    """Architecture and version details."""

    arch: str
    version: str  # the product version (and not the codestream version) if present in the context ArchVer is used


class OBSBinary(NamedTuple):
    """OBS binary coordinates."""

    project: str
    package: str
    repo: str
    arch: str
