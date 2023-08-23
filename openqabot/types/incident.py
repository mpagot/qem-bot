# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
import re
from logging import getLogger
from typing import Dict, List, Tuple

from . import ArchVer, Repos
from ..errors import EmptyChannels, EmptyPackagesError, NoRepoFoundError
from ..loader.repohash import get_max_revision

log = getLogger("bot.types.incident")
version_pattern = re.compile(r"(\d+(?:[.-](?:SP)?\d+)?)")


class Incident:
    def __init__(self, incident):
        log.debug("Incident %d with %d channels", incident['number'], len(incident['channels']))
        self.rr = incident["rr_number"]
        self.project = incident["project"]
        self.id = incident["number"]
        self.rrid = f"{self.project}:{self.rr}" if self.rr else None
        self.staging = not incident["inReview"]
        self.embargoed = incident["embargoed"]

        no_update_channels = [r for r in incident['channels'] if not r.startswith("SUSE:Updates")]
        log.debug("Channels not starting with 'SUSE:Updates' are %d", len(no_update_channels))

        no_3_val = [
                val for val in (
                    r.split(":")[2:]
                    for r in incident["channels"]
                    if r.startswith("SUSE:Updates")
                )
                if len(val) != 3
        ]
        log.debug("Channels not having the right name lenght are %d", len(no_3_val))

        smdto_channels = [
            p
            for p, v, a in (
                val
                for val in (
                    r.split(":")[2:]
                    for r in incident["channels"]
                    if r.startswith("SUSE:Updates")
                )
                if len(val) == 3
            )
            if p == "SLE-Module-Development-Tools-OBS"
        ]
        log.debug("Channels 'SLE-Module-Development-Tools-OBS' are %d", len(smdto_channels))

        self.channels = [
            Repos(p, v, a)
            for p, v, a in (
                val
                for val in (
                    r.split(":")[2:]
                    for r in incident["channels"]
                    if r.startswith("SUSE:Updates")
                )
                if len(val) == 3
            )
            if p != "SLE-Module-Development-Tools-OBS"
        ]
        # set openSUSE-SLE arch as x86_64 by default
        # for now is simplification as we now test only on x86_64
        self.channels += [
            Repos(p, v, "x86_64")
            for p, v in (
                val
                for val in (
                    r.split(":")[2:]
                    for r in (
                        i for i in incident["channels"] if i.startswith("SUSE:Updates")
                    )
                )
                if len(val) == 2
            )
        ]

        # remove Manager-Server on aarch64 from channels
        self.channels = [
            chan
            for chan in self.channels
            if not (
                chan.product == "SLE-Module-SUSE-Manager-Server"
                and chan.arch == "aarch64"
            )
        ]

        log.debug("Check for empty channels")
        if not self.channels:
            raise EmptyChannels(self.project)

        log.debug("Check for empty packages")
        self.packages = sorted(incident["packages"], key=len)
        if not self.packages:
            raise EmptyPackagesError(self.project)

        self.emu = incident["emu"]
        self.revisions = self._rev(self.channels, self.project)
        self.livepatch: bool = self._is_livepatch(self.packages)
        log.debug("Incident %d DONE", incident['number'])

    @staticmethod
    def _rev(channels: List[Repos], project: str) -> Dict[ArchVer, int]:
        rev: Dict[ArchVer, int] = {}
        tmpdict: Dict[ArchVer, List[Tuple[str, str]]] = {}

        for repo in channels:
            version = repo.version
            v = re.match(version_pattern, repo.version)
            if v:
                version = v.group(0)

            if ArchVer(repo.arch, version) in tmpdict:
                tmpdict[ArchVer(repo.arch, version)].append(
                    (repo.product, repo.version)
                )
            else:
                tmpdict[ArchVer(repo.arch, version)] = [(repo.product, repo.version)]

        if tmpdict:
            for archver, lrepos in tmpdict.items():
                try:
                    max_rev = get_max_revision(lrepos, archver.arch, project)
                    if max_rev > 0:
                        rev[archver] = max_rev
                except NoRepoFoundError as e:
                    raise e

        return rev

    def __repr__(self):
        if self.rrid:
            return f"<Incident: {self.rrid}>"
        return f"<Incident: {self.project}>"

    def __str__(self):
        return str(self.id)

    @staticmethod
    def _is_livepatch(packages: List[str]) -> bool:
        kgraft = False

        for package in packages:
            if (
                package.startswith("kernel-default")
                or package.startswith("kernel-source")
                or package.startswith("kernel-azure")
            ):
                return False
            if package.startswith("kgraft-patch-") or package.startswith(
                "kernel-livepatch"
            ):
                kgraft = True

        return kgraft

    def contains_package(self, requires: List[str]) -> bool:
        for package in self.packages:
            for req in requires:
                if package.startswith(req) and package != "kernel-livepatch-tools":
                    return True
        return False
