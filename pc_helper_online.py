#!/usr/bin/env python3
# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
import logging
from argparse import ArgumentParser
from pathlib import Path
from ruamel.yaml import YAML
from openqabot.pc_helper import apply_pc_tools_image, apply_publiccloud_pint_image, sles4sap_query_flavor
from openqabot.utils import create_logger, get_yml_list

log = create_logger("pc_helper_online")

def main():
    """
    This code is used only for testing purpose.
    Allowing to prove that Public Cloud related logic is actually working without executing
    a lot of code which is unrelated to pc_helper.
    As input it getting directory with openqabot configuration metadata (same folder as bot-ng )
    but processing only variables related to openqabot.pc_helper module
    """
    parser = ArgumentParser(
        prog="pc_helper_online",
        description="Dummy code to test functionality related to pc_helper code",
    )
    parser.add_argument(
        "-c",
        "--configs",
        type=Path,
        default=Path("/etc/openqabot"),
        help="Directory with openqabot configuration metadata",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug output"
    )
    args = parser.parse_args()
    if args.debug:
        log.setLevel(logging.DEBUG)
        logging.getLogger("openqabot.pc_helper").setLevel(logging.DEBUG)
    log.info(f"Parsing configuration files from {args.configs}")
    loader = YAML(typ="safe")
    for p in get_yml_list(Path(args.configs)):
        try:
            data = loader.load(p)
            log.info(f"Processing {p}")
            if "settings" in data:
                settings = data["settings"]
                log.info("Settings:%s", settings)
                if "PUBLIC_CLOUD_TOOLS_IMAGE_QUERY" in settings:
                    apply_pc_tools_image(settings)
                    if "PUBLIC_CLOUD_TOOLS_IMAGE_BASE" not in settings:
                        log.error(
                            f"Failed to get PUBLIC_CLOUD_TOOLS_IMAGE_BASE from {data}"
                        )
                if "PUBLIC_CLOUD_PINT_QUERY" in settings:
                    apply_publiccloud_pint_image(settings)
                    if "PUBLIC_CLOUD_IMAGE_ID" not in settings:
                        log.error(f"Failed to get PUBLIC_CLOUD_IMAGE_ID from {data}")
                if "SLES4SAP_PINT_QUERY" in settings and 'incidents' in data:
                    for flavor in data['incidents']["FLAVOR"]:
                        if 'pint_name_regexp' not in data['incidents']["FLAVOR"][flavor]:
                            continue
                        out_settings = sles4sap_query_flavor(flavor, settings["SLES4SAP_PINT_QUERY"], data['incidents']["FLAVOR"][flavor]['pint_name_regexp'])
                        if not out_settings or not out_settings.get("SLES4SAP_QESAP_OS_VER", False):
                            log.error("Nothing valid in out_settings:%s", out_settings)
                            continue
                        log.debug("Valid out_settings:%s", out_settings)
        except Exception as e:
            log.exception(e)
            continue


if __name__ == "__main__":
    main()
