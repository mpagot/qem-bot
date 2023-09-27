# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
from functools import lru_cache
from logging import getLogger
import re

from .utils import retry5 as requests

log = getLogger("openqabot.pc_helper")


def get_latest_tools_image(query):
    """
    'publiccloud_tools_<BUILD NUM>.qcow2' is a generic name for an image used by Public Cloud tests to run
    in openQA. A query is supposed to look like this "https://openqa.suse.de/group_overview/276.json" to get
    a value for <BUILD NUM>
    """

    ## Get the first not-failing item
    build_results = requests.get(query).json()["build_results"]
    for build in build_results:
        if build["failed"] == 0:
            return "publiccloud_tools_{}.qcow2".format(build["build"])
    return None


def apply_pc_tools_image(settings):
    """
    Use PUBLIC_CLOUD_TOOLS_IMAGE_QUERY to get latest tools image and set it into
    PUBLIC_CLOUD_TOOLS_IMAGE_BASE
    """
    try:
        if "PUBLIC_CLOUD_TOOLS_IMAGE_QUERY" in settings:
            settings["PUBLIC_CLOUD_TOOLS_IMAGE_BASE"] = get_latest_tools_image(
                settings["PUBLIC_CLOUD_TOOLS_IMAGE_QUERY"]
            )
    except BaseException as e:
        log_error = f"PUBLIC_CLOUD_TOOLS_IMAGE_BASE handling failed"
        if "PUBLIC_CLOUD_TOOLS_IMAGE_QUERY" in settings:
            log_error += f" PUBLIC_CLOUD_TOOLS_IMAGE_QUERY={settings['PUBLIC_CLOUD_TOOLS_IMAGE_QUERY']}"
        log.warning(f"{log_error} : {e}")
    finally:
        del settings["PUBLIC_CLOUD_TOOLS_IMAGE_QUERY"]
    return settings


@lru_cache(maxsize=None)
def pint_query(query):
    """
    Perform a pint query. Successive queries are cached
    """
    return requests.get(query).json()


def apply_publiccloud_pint_image(settings):
    """
    Applies PUBLIC_CLOUD_IMAGE_LOCATION based on the given PUBLIC_CLOUD_IMAGE_REGEX
    """
    try:
        region = (
            settings["PUBLIC_CLOUD_PINT_REGION"]
            if "PUBLIC_CLOUD_PINT_REGION" in settings
            else None
        )
        # We need to include active and inactive images. Active images have precedence
        # inactive images are maintained PC images which only receive security updates.
        # See https://www.suse.com/c/suse-public-cloud-image-life-cycle/
        image = None
        for state in ["active", "inactive", "deprecated"]:
            images = pint_query(f"{settings['PUBLIC_CLOUD_PINT_QUERY']}{state}.json")[
                "images"
            ]
            image = get_recent_pint_image(
                images, settings["PUBLIC_CLOUD_PINT_NAME"], region, state=state
            )
            if image is not None:
                break
        if image is None:
            raise ValueError("Cannot find matching image in pint")
        settings["PUBLIC_CLOUD_IMAGE_ID"] = image[settings["PUBLIC_CLOUD_PINT_FIELD"]]
        settings["PUBLIC_CLOUD_IMAGE_NAME"] = image["name"]
        settings["PUBLIC_CLOUD_IMAGE_STATE"] = image["state"]
    except BaseException as e:
        log_error = "PUBLIC_CLOUD_PINT_QUERY handling failed"
        if "PUBLIC_CLOUD_PINT_NAME" in settings:
            log_error += f' for {settings["PUBLIC_CLOUD_PINT_NAME"]}'
        log.warning(f"{log_error}: {e}")
        settings["PUBLIC_CLOUD_IMAGE_ID"] = None
    finally:
        if "PUBLIC_CLOUD_PINT_QUERY" in settings:
            del settings["PUBLIC_CLOUD_PINT_QUERY"]
        if "PUBLIC_CLOUD_PINT_NAME" in settings:
            del settings["PUBLIC_CLOUD_PINT_NAME"]
        if "PUBLIC_CLOUD_PINT_REGION" in settings:
            # If we define a region for the pint query, propagate this value
            settings["PUBLIC_CLOUD_REGION"] = settings["PUBLIC_CLOUD_PINT_REGION"]
            del settings["PUBLIC_CLOUD_PINT_REGION"]
        if "PUBLIC_CLOUD_PINT_FIELD" in settings:
            del settings["PUBLIC_CLOUD_PINT_FIELD"]
    return settings


def get_pint_image(name_filter, field, state, query, region=None):
    """
    get list of images, search the one with name
    matching the filter and return the newest one.

    Return dictionary has NAME and ID
    """
    settings = {}
    try:
        image = None
        url = f"{query}{state}.json"
        log.debug("Pint url:%s name_filter:%s region:%s", url, name_filter, region)
        images = pint_query(url)["images"]
        image = get_recent_pint_image(images, name_filter, region=region, state=state)
        if image is None:
            raise ValueError(
                f"Cannot find matching image in PINT with name:[{name_filter}] and state:{state}"
            )
        if field not in image.keys() or "name" not in image.keys():
            raise ValueError(
                f"Cannot find expected keys in the selected image dictionary {image}"
            )
        settings["ID"] = image[field]
        settings["NAME"] = image["name"]
    except BaseException as e:
        log.warning(f"get_pint_image handling failed: {e}")
    log.debug("settings:%s", settings)
    return settings


def pint_url(pint_base_url, csp_name):
    url = '/'.join([pint_base_url] + [csp_name, 'images']) + '/'
    log.debug("PINT url:%s", url)
    return url


def sles4sap_pint_azure(name_filter, state, pint_base_url):
    """
    Query PINT about Azure images and retrieve the latest one
    """
    job_settings = {}
    ret = get_pint_image(
        name_filter=name_filter, field="urn", state=state, query=pint_url(pint_base_url, "microsoft")
    )
    if any(ret):
        job_settings["SLES4SAP_QESAP_OS_VER"] = ret["ID"]
        job_settings["SLES4SAP_QESAP_OS_STATE"] = state
    return job_settings


def sles4sap_pint_gce(name_filter, state, pint_base_url):
    """
    Query PINT about GCE images and retrieve the latest one
    """
    job_settings = {}
    ret = get_pint_image(
        name_filter=name_filter,
        field="project",
        state=state,
        query=pint_url(pint_base_url, "google"),
    )
    if any(ret):
        job_settings["SLES4SAP_QESAP_OS_VER"] = f"{ret['ID']}/{ret['NAME']}"
        job_settings["SLES4SAP_QESAP_OS_STATE"] = state
    return job_settings


def sles4sap_pint_ec2(name_filter, state, pint_base_url, region_list):
    """
    Query PINT about EC2 images and retrieve the latest one
    for each of the requested regions.
    Returned data is organized in a different way from sles4sap_pint_azure
    and sles4sap_pint_gce
    """
    job_settings = {}
    images_list = {}
    for this_region in region_list:
        ret = get_pint_image(
            name_filter=name_filter,
            field="id",
            state=state,
            query=pint_url(pint_base_url, "amazon"),
            region=this_region,
        )
        if any(ret):
            images_list[this_region] = ret
    if any(images_list):
        # All element should have same name, just get the first
        job_settings["SLES4SAP_QESAP_OS_VER"] = next(iter(images_list.items()))[1][
            "NAME"
        ]
        job_settings["SLES4SAP_QESAP_OS_VER_STATE"] = state
        job_settings["SLES4SAP_QESAP_OS_OWNER"] = "aws-marketplace"
        # Pack all pairs region/AMI in a ';' separated values string
        setting_regions = []
        setting_ami = []
        for image_region, image_settings in images_list.items():
            setting_regions.append(image_region)
            setting_ami.append(image_settings["ID"])
        job_settings["SLES4SAP_QESAP_OS_VER_REGIONS"] = ";".join(setting_regions)
        job_settings["SLES4SAP_QESAP_OS_VER_ID"] = ";".join(setting_ami)
    return job_settings


def apply_sles4sap_pint_image(
    cloud_provider, pint_base_url, name_filter, region_list=None
):
    """
    Applies OS_IMAGE relates settings based on the given SLES4SAP_IMAGE_REGEX
    """
    job_settings = {}
    for state in ["active", "inactive"]:
        if "AZURE" in cloud_provider:
            job_settings = sles4sap_pint_azure(name_filter, state, pint_base_url)
        elif "GCE" in cloud_provider:
            job_settings = sles4sap_pint_gce(name_filter, state, pint_base_url)
        elif "EC2" in cloud_provider:
            job_settings = sles4sap_pint_ec2(
                name_filter, state, pint_base_url, region_list
            )
        if any(job_settings):
            break
    log.debug("Sles4sap job settings:%s", job_settings)
    return job_settings


def sles4sap_query_flavor(flavor, base_url, version):
    log.info("Flavor:%s", flavor)
    pc_cloud_provider = None
    if 'azure' in flavor.lower():
        pc_cloud_provider = "AZURE"
        pint_cloud_provider = "microsoft"
    if not pc_cloud_provider:
        return None
    url = '/'.join([base_url] + [pint_cloud_provider, 'images']) + '/'
    log.info("url:%s", url)
    return apply_sles4sap_pint_image(pc_cloud_provider, url, version.lower())


def get_recent_pint_image(images, name_regex, region=None, state="active"):
    """
    From the given set of images (received json from pint),
    get the latest one that matches the given criteria:
     - name given as regular expression,
     - region given as string,
     - state given the state of the image

    Get the latest one based on 'publishedon'
    """

    def is_newer(date1, date2):
        # Checks if date1 is newer than date2. Expected date format: YYYYMMDD
        # Because for the format, we can do a simple int comparison
        return int(date1) > int(date2)

    name = re.compile(name_regex)
    if region == "":
        region = None
    recentimage = None
    for image in images:
        # Apply selection criteria: state and region criteria
        # can be omitted by setting the corresponding variable to None
        # This is required, because certain public cloud providers
        # do not make a distinction on e.g. the region
        # and thus this check is not needed there
        if name.match(image["name"]) is None:
            continue
        if (state is not None) and (image["state"] != state):
            continue
        if (region is not None) and (region != image["region"]):
            continue
        # Get latest one based on 'publishedon'
        if recentimage is None or is_newer(
            image["publishedon"], recentimage["publishedon"]
        ):
            recentimage = image
    return recentimage
