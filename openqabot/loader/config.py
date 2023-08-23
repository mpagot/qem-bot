# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
from logging import getLogger
from pathlib import Path
from typing import List, Set, Union

from ruamel.yaml import YAML  # type: ignore

from ..errors import NoTestIssues
from ..types import Data
from ..types.aggregate import Aggregate
from ..types.incidents import Incidents

log = getLogger("bot.loader.config")


def get_yml_list(path: Path) -> List[Path]:
    yml_list = []
    if path.is_file() and path.match("*.yml"):
        yml_list.append(path)
    else:
        yml_list = [p for p in path.glob("*.yml")]
    return yml_list


def load_metadata(
    path: Path, aggregate: bool, incidents: bool, extrasettings: Set[str]
) -> List[Union[Aggregate, Incidents]]:
    ret: List[Union[Aggregate, Incidents]] = []
    log.debug("Run load_metadata aggregate:%s incidents:%s", aggregate, incidents)
    loader = YAML(typ="safe")

    for p in get_yml_list(path):
        log.debug("Processing YML %s", p)
        try:
            data = loader.load(p)
        except Exception as e:
            log.exception(e)
            continue

        try:
            settings = data.get("settings")
        except AttributeError:
            log.debug("not valid yaml %s for bot settings", p)
            continue

        if "product" not in data:
            log.debug("Skipping invalid config %s" % p)
            continue

        if not settings:
            log.debug("No settings in %s", p)
            continue

        for key in data:
            log.debug("Processing key:%s", key)
            if key == "incidents" and not incidents:
                log.debug("Append incident")
                ret.append(
                    Incidents(data["product"], settings, data[key], extrasettings)
                )
            elif key == "aggregate" and not aggregate:
                try:
                    log.debug("Append aggregate")
                    ret.append(Aggregate(data["product"], settings, data[key]))
                except NoTestIssues:
                    log.warning("No 'test_issues' in %s config" % data["product"])
            else:
                log.debug("Nothing to append for key %s", key)
                continue
    log.debug("Number of workers:%d", len(ret))
    return ret


def read_products(path: Path) -> List[Data]:
    loader = YAML(typ="safe")
    ret = []

    for p in get_yml_list(path):
        data = loader.load(p)

        if not data:
            log.info("Skipping invalid config %s - empty config" % str(p))
            continue
        if not isinstance(data, dict):
            log.info("Skipping invalid config %s - invalid format" % str(p))
            continue

        try:
            flavor = data["aggregate"]["FLAVOR"]
        except KeyError:
            log.info("Config %s does not have aggregate" % str(p))
            continue

        try:
            distri = data["settings"]["DISTRI"]
            version = data["settings"]["VERSION"]
            product = data["product"]
        except Exception as e:
            log.exception(e)
            continue

        for arch in data["aggregate"]["archs"]:
            ret.append(Data(0, 0, flavor, arch, distri, version, "", product))

    return ret


def get_onearch(path: Path) -> Set[str]:
    loader = YAML(typ="safe")

    try:
        data = loader.load(path)
    except Exception as e:
        log.exception(e)
        return set()

    return set(data)
