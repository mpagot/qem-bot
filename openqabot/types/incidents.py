# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
from logging import getLogger
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from . import ArchVer, ProdVer, Repos
from .. import QEM_DASHBOARD
from ..pc_helper import (
    apply_pc_tools_image,
    apply_publiccloud_pint_image,
    apply_sles4sap_pint_image,
)
from ..utils import retry3 as requests
from .baseconf import BaseConf
from .incident import Incident

log = getLogger("bot.types.incidents")


class Incidents(BaseConf):
    def __init__(self, product: str, settings, config, extrasettings: Set[str]) -> None:
        super().__init__(product, settings, config)
        self.flavors = self.normalize_repos(config["FLAVOR"])
        self.singlearch = extrasettings

    def __repr__(self):
        return f"<Incidents product: {self.product}>"

    @staticmethod
    def normalize_repos(config):
        ret = {}
        for flavor, data in config.items():
            ret[flavor] = {}
            for key, value in data.items():
                if key == "issues":
                    ret[flavor][key] = {
                        template: ProdVer(channel.split(":")[0], channel.split(":")[1])
                        for template, channel in value.items()
                    }
                else:
                    ret[flavor][key] = value

        return ret

    @staticmethod
    def _repo_osuse(chan: Repos) -> Union[Repos, Tuple[str, str]]:
        if chan.product == "openSUSE-SLE":
            return chan.product, chan.version
        return chan

    @staticmethod
    def _is_scheduled_job(
        token: Dict[str, str], inc: Incident, arch: str, ver: str, flavor: str
    ) -> bool:
        jobs = {}
        try:
            jobs = requests.get(
                f"{QEM_DASHBOARD}api/incident_settings/{inc.id}",
                headers=token,
            ).json()
        except Exception as e:
            log.exception(e)

        if not jobs:
            return False

        if isinstance(jobs, dict) and "error" in jobs:
            return False

        for job in jobs:
            try:
                if (
                    job["flavor"] == flavor
                    and job["arch"] == arch
                    and job["settings"]["REPOHASH"] == inc.revisions[ArchVer(arch, ver)]
                ):
                    return True
            except KeyError:
                log.debug(
                    "Incident %s does not have %s arch in SLE-12 module version"
                    % (inc.id, arch)
                )
                continue

        return False

    def __call__(
        self,
        incidents: List[Incident],
        token: Dict[str, str],
        ci_url: Optional[str],
        ignore_onetime: bool,
    ) -> List[Dict[str, Any]]:
        DOWNLOAD_BASE = "http://download.suse.de/ibs/SUSE:/Maintenance:/"
        BASE_PRIO = 50
        ret = []

        for flavor, data in self.flavors.items():
            for arch in data["archs"]:
                log.debug("Incidents:%s", incidents)
                for inc in incidents:
                    if self.filter_embargoed() and inc.embargoed:
                        log.debug(
                            "Incident %s is embargoed and filtering embargoed updates enabled",
                            inc.id,
                        )
                        continue
                    full_post: Dict[str, Any] = {}
                    full_post["api"] = "api/incident_settings"
                    full_post["qem"] = {}
                    full_post["openqa"] = {}
                    full_post["openqa"].update(self.settings)
                    full_post["qem"]["incident"] = inc.id
                    full_post["openqa"]["ARCH"] = arch
                    full_post["qem"]["arch"] = arch
                    full_post["openqa"]["FLAVOR"] = flavor
                    full_post["qem"]["flavor"] = flavor
                    full_post["openqa"]["VERSION"] = self.settings["VERSION"]
                    full_post["qem"]["version"] = self.settings["VERSION"]
                    full_post["openqa"]["DISTRI"] = self.settings["DISTRI"]
                    full_post["openqa"]["_ONLY_OBSOLETE_SAME_BUILD"] = "1"
                    full_post["openqa"]["_OBSOLETE"] = "1"
                    full_post["openqa"]["INCIDENT_ID"] = inc.id

                    if ci_url:
                        full_post["openqa"]["__CI_JOB_URL"] = ci_url

                    if inc.staging:
                        continue

                    if "packages" in data:
                        if not inc.contains_package(data["packages"]):
                            continue

                    if "excluded_packages" in data:
                        if inc.contains_package(data["excluded_packages"]):
                            continue

                    if inc.livepatch:
                        full_post["openqa"]["KGRAFT"] = "1"

                    full_post["openqa"]["BUILD"] = f":{inc.id}:{inc.packages[0]}"

                    if inc.rrid:
                        full_post["openqa"]["RRID"] = inc.rrid

                    # old bot used variable "REPO_ID"
                    revs = inc.revisions_with_fallback(arch, self.settings["VERSION"])
                    if not revs:
                        continue
                    full_post["openqa"]["REPOHASH"] = revs
                    channels_set = set()
                    issue_dict = {}

                    for issue, channel in data["issues"].items():
                        f_channel = Repos(channel.product, channel.version, arch)
                        log.info("===> issue:%s channel:%s f_channel:%s inc.channels:%s", issue, channel, f_channel, inc.channels)
                        if f_channel in inc.channels:
                            issue_dict[issue] = inc
                            channels_set.add(f_channel)

                    if not issue_dict:
                        log.debug(
                            "No channels in %s for %s on %s" % (inc.id, flavor, arch)
                        )
                        continue

                    if "required_issues" in data:
                        if set(issue_dict.keys()).isdisjoint(data["required_issues"]):
                            continue

                    if not ignore_onetime and self._is_scheduled_job(
                        token, inc, arch, self.settings["VERSION"], flavor
                    ):
                        log.info(
                            "not scheduling: Flavor: %s, version: %s incident: %s , arch: %s  - exists in openQA "
                            % (flavor, self.settings["VERSION"], inc.id, arch)
                        )
                        continue

                    if (
                        "Kernel" in flavor
                        and not inc.livepatch
                        and not flavor.endswith("Azure")
                    ):
                        if set(issue_dict.keys()).isdisjoint(
                            set(
                                [
                                    "OS_TEST_ISSUES",  # standard product dir
                                    "LTSS_TEST_ISSUES",  # LTSS product dir
                                    "BASE_TEST_ISSUES",  # GA product dir SLE15+
                                    "RT_TEST_ISSUES",  # realtime kernel
                                ]
                            )
                        ):
                            log.warning(
                                "Kernel incident %s doesn't have product repository"
                                % str(inc)
                            )
                            continue

                    for key, value in issue_dict.items():
                        full_post["openqa"][key] = str(value.id)

                    repos = (
                        f"{DOWNLOAD_BASE}{inc.id}/SUSE_Updates_{'_'.join(self._repo_osuse(chan))}"
                        for chan in channels_set
                    )
                    full_post["openqa"]["INCIDENT_REPO"] = ",".join(
                        sorted(repos)
                    )  # sorted for testability

                    full_post["qem"]["withAggregate"] = True
                    aggregate_job = data.get("aggregate_job", True)

                    if not aggregate_job:
                        pos = set(data.get("aggregate_check_true", []))
                        neg = set(data.get("aggregate_check_false", []))

                        if pos and not pos.isdisjoint(full_post["openqa"].keys()):
                            full_post["qem"]["withAggregate"] = False
                            log.info("Aggregate not needed for incident %s" % inc.id)
                        if neg and neg.isdisjoint(full_post["openqa"].keys()):
                            full_post["qem"]["withAggregate"] = False
                            log.info("Aggregate not needed for incident %s" % inc.id)
                        if not (neg and pos):
                            full_post["qem"]["withAggregate"] = False

                    # some arch specific packages doesn't have aggregate tests
                    if not self.singlearch.isdisjoint(set(inc.packages)):
                        full_post["qem"]["withAggregate"] = False

                    delta_prio = data.get("override_priority", 0)

                    if delta_prio:
                        delta_prio -= 50
                    else:
                        if flavor.endswith("Minimal"):
                            delta_prio -= 5
                        if not inc.staging:
                            delta_prio += 10
                        if inc.emu:
                            delta_prio = -20
                        # override default prio only for specific jobs
                        if delta_prio:
                            full_post["openqa"]["_PRIORITY"] = BASE_PRIO + delta_prio

                    # add custom vars to job settings
                    if "params_expand" in data:
                        full_post["openqa"].update(data["params_expand"])

                    full_post["openqa"][
                        "__SMELT_INCIDENT_URL"
                    ] = f"https://smelt.suse.de/incident/{inc.id}"
                    full_post["openqa"][
                        "__DASHBOARD_INCIDENT_URL"
                    ] = f"{QEM_DASHBOARD}incident/{inc.id}"

                    settings = full_post["openqa"].copy()

                    # if set, we use this query to detect latest public cloud tools image which used for running
                    # all public cloud related tests in openQA
                    if "PUBLIC_CLOUD_TOOLS_IMAGE_QUERY" in settings:
                        settings = apply_pc_tools_image(settings)
                        if not settings.get("PUBLIC_CLOUD_TOOLS_IMAGE_BASE", False):
                            continue

                    # parse Public-Cloud pint query if present
                    if "PUBLIC_CLOUD_PINT_QUERY" in settings:
                        settings = apply_publiccloud_pint_image(settings)
                        if not settings.get("PUBLIC_CLOUD_IMAGE_ID", False):
                            continue

                    full_post["openqa"] = settings
                    full_post["qem"]["settings"] = settings
                    ret.append(full_post)
        return ret
