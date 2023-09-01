import re
import responses
from openqabot.pc_helper import (
    apply_pc_tools_image,
    apply_publiccloud_pint_image,
    get_latest_tools_image,
    get_recent_pint_image,
    apply_sles4sap_pint_image,
)
import openqabot.pc_helper


def test_apply_pc_tools_image(monkeypatch):
    known_return = "test"
    monkeypatch.setattr(
        openqabot.pc_helper,
        "get_latest_tools_image",
        lambda *args, **kwargs: known_return,
    )

    settings = {"PUBLIC_CLOUD_TOOLS_IMAGE_QUERY": "test"}
    apply_pc_tools_image(settings)
    assert "PUBLIC_CLOUD_TOOLS_IMAGE_BASE" in settings
    assert settings["PUBLIC_CLOUD_TOOLS_IMAGE_BASE"] == known_return
    assert "PUBLIC_CLOUD_TOOLS_IMAGE_QUERY" not in settings


def test_apply_publiccloud_pint_image(monkeypatch):
    monkeypatch.setattr(
        openqabot.pc_helper, "pint_query", lambda *args, **kwargs: {"images": []}
    )
    monkeypatch.setattr(
        openqabot.pc_helper,
        "get_recent_pint_image",
        lambda *args, **kwargs: {"name": "test", "state": "active", "image_id": "111"},
    )
    settings = {}
    apply_publiccloud_pint_image(settings)
    assert settings["PUBLIC_CLOUD_IMAGE_ID"] is None
    assert "PUBLIC_CLOUD_PINT_QUERY" not in settings
    assert "PUBLIC_CLOUD_PINT_NAME" not in settings
    assert "PUBLIC_CLOUD_PINT_REGION" not in settings
    assert "PUBLIC_CLOUD_PINT_FIELD" not in settings
    assert "PUBLIC_CLOUD_REGION" not in settings

    settings = {
        "PUBLIC_CLOUD_PINT_QUERY": "test",
        "PUBLIC_CLOUD_PINT_NAME": "test",
        "PUBLIC_CLOUD_PINT_FIELD": "image_id",
    }
    apply_publiccloud_pint_image(settings)
    assert settings["PUBLIC_CLOUD_IMAGE_ID"] == "111"
    assert "PUBLIC_CLOUD_PINT_QUERY" not in settings
    assert "PUBLIC_CLOUD_PINT_NAME" not in settings
    assert "PUBLIC_CLOUD_PINT_REGION" not in settings
    assert "PUBLIC_CLOUD_PINT_FIELD" not in settings
    assert "PUBLIC_CLOUD_REGION" not in settings

    settings = {
        "PUBLIC_CLOUD_PINT_QUERY": "test",
        "PUBLIC_CLOUD_PINT_NAME": "test",
        "PUBLIC_CLOUD_PINT_FIELD": "image_id",
        "PUBLIC_CLOUD_PINT_REGION": "south",
    }
    apply_publiccloud_pint_image(settings)
    assert settings["PUBLIC_CLOUD_IMAGE_ID"] == "111"
    assert "PUBLIC_CLOUD_PINT_QUERY" not in settings
    assert settings["PUBLIC_CLOUD_REGION"] == "south"
    assert "PUBLIC_CLOUD_PINT_NAME" not in settings
    assert "PUBLIC_CLOUD_PINT_REGION" not in settings
    assert "PUBLIC_CLOUD_PINT_FIELD" not in settings

    monkeypatch.setattr(
        openqabot.pc_helper, "get_recent_pint_image", lambda *args, **kwargs: None
    )
    settings = {
        "PUBLIC_CLOUD_PINT_QUERY": "test",
        "PUBLIC_CLOUD_PINT_NAME": "test",
        "PUBLIC_CLOUD_PINT_FIELD": "image_id",
        "PUBLIC_CLOUD_PINT_REGION": "south",
    }
    apply_publiccloud_pint_image(settings)
    assert settings["PUBLIC_CLOUD_IMAGE_ID"] is None
    assert "PUBLIC_CLOUD_PINT_QUERY" not in settings
    assert settings["PUBLIC_CLOUD_REGION"] == "south"
    assert "PUBLIC_CLOUD_PINT_NAME" not in settings
    assert "PUBLIC_CLOUD_PINT_REGION" not in settings
    assert "PUBLIC_CLOUD_PINT_FIELD" not in settings


def test_apply_sles4sap_pint_image_invalid_csp():
    res = apply_sles4sap_pint_image(
        cloud_provider="Guybrush", pint_query=None, name_filter=None
    )
    assert res == {}


def test_apply_sles4sap_pint_image_invalid_url(monkeypatch):
    res = apply_sles4sap_pint_image(
        cloud_provider="AZURE", pint_query="DinkyIsland", name_filter=None
    )
    assert res == {}


def test_apply_sles4sap_pint_image_none_match_pint(monkeypatch):
    monkeypatch.setattr(
        openqabot.pc_helper, "pint_query", lambda *args, **kwargs: {"images": []}
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="AZURE",
        pint_query="http://DinkyIsland/",
        name_filter="StanStanman",
    )
    assert res == {}


def test_apply_sles4sap_pint_image_unexpected_format(monkeypatch):
    """
    What is happening when the JSON structure returned
    by PINT does not have fields that the script expect to be
    present in Azure images?
    """
    monkeypatch.setattr(
        openqabot.pc_helper,
        "pint_query",
        lambda *args, **kwargs: {"images": [{"Elaine": "Marley"}]},
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="AZURE",
        pint_query="http://DinkyIsland/",
        name_filter="StanStanman",
    )
    assert res == {}


def test_apply_sles4sap_pint_image_none_match_name(monkeypatch):
    """
    What is happening when the JSON structure returned
    by PINT does not have the name matching with requested filter?
    """
    monkeypatch.setattr(
        openqabot.pc_helper,
        "pint_query",
        lambda *args, **kwargs: {
            "images": [{"name": "ElaineMarley", "urn": "TriIslandArea"}]
        },
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="AZURE",
        pint_query="http://DinkyIsland/",
        name_filter="StanStanman",
    )
    assert res == {}


def test_apply_sles4sap_pint_image_azure(monkeypatch):
    monkeypatch.setattr(
        openqabot.pc_helper,
        "pint_query",
        lambda *args, **kwargs: {
            "images": [
                {
                    "name": "ElaineMarley",
                    "urn": "TriIslandArea",
                    "publishedon": "1",
                    "state": "active",
                }
            ]
        },
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="AZURE", pint_query="http://DinkyIsland/", name_filter="Elaine"
    )
    assert res["SLES4SAP_QESAP_OS_VER"] == "TriIslandArea"


def test_apply_sles4sap_pint_image_gce(monkeypatch):
    monkeypatch.setattr(
        openqabot.pc_helper,
        "pint_query",
        lambda *args, **kwargs: {
            "images": [
                {
                    "name": "ElaineMarley",
                    "project": "TriIslandArea",
                    "publishedon": "1",
                    "state": "active",
                }
            ]
        },
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="GCE", pint_query="http://DinkyIsland/", name_filter="Elaine"
    )
    assert res["SLES4SAP_QESAP_OS_VER"] == "TriIslandArea/ElaineMarley"


def test_apply_sles4sap_pint_image_ec2(monkeypatch):
    """
    Simulate PINT only to have one active image in one region.
    Request images using matching name and region
    """
    monkeypatch.setattr(
        openqabot.pc_helper,
        "pint_query",
        lambda *args, **kwargs: {
            "images": [
                {
                    "name": "ElaineMarley",
                    "id": "RootBeer",
                    "publishedon": "1",
                    "state": "active",
                    "region": "TriIslandArea",
                }
            ]
        },
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="EC2",
        pint_query="http://DinkyIsland/",
        name_filter="Elaine",
        region_list=["TriIslandArea"],
    )
    assert res["SLES4SAP_QESAP_OS_VER"] == "ElaineMarley"


def test_apply_sles4sap_pint_image_ec2_multiple_regions(monkeypatch):
    """
    Simulate PINT to have same image in two regions.
    In AWS it is tipical to have same image available in multiple regions: all of the image
    has the same name but different AMI (recorded in PINT under 'id' key)
    Request images using matching name and region list
    """
    monkeypatch.setattr(
        openqabot.pc_helper,
        "pint_query",
        lambda *args, **kwargs: {
            "images": [
                {
                    "name": "ElaineMarley",
                    "id": "RootBeer",
                    "publishedon": "1",
                    "state": "active",
                    "region": "MêléeIsland",
                },
                {
                    "name": "ElaineMarley",
                    "id": "BananaPicker",
                    "publishedon": "1",
                    "state": "active",
                    "region": "HookIsle",
                },
            ]
        },
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="EC2",
        pint_query="http://DinkyIsland/",
        name_filter="Elaine",
        region_list=["MêléeIsland", "HookIsle"],
    )
    assert res["SLES4SAP_QESAP_OS_VER"] == "ElaineMarley"
    assert res["SLES4SAP_QESAP_OS_VER_REGIONS"] == "MêléeIsland;HookIsle"
    assert res["SLES4SAP_QESAP_OS_VER_ID"] == "RootBeer;BananaPicker"


def test_apply_sles4sap_pint_image_ec2_multiple_regions_filtered(monkeypatch):
    """
    Simulate PINT to have same image in two regions AAA and BBB.
    Request images using matching name but region list like AAA and CCC.
    Expected result is that only AAA image is returned
    """
    monkeypatch.setattr(
        openqabot.pc_helper,
        "pint_query",
        lambda *args, **kwargs: {
            "images": [
                {
                    "name": "ElaineMarley",
                    "id": "RootBeer",
                    "publishedon": "1",
                    "state": "active",
                    "region": "MêléeIsland",
                },
                {
                    "name": "ElaineMarley",
                    "id": "BananaPicker",
                    "publishedon": "1",
                    "state": "active",
                    "region": "HookIsle",
                },
            ]
        },
    )
    res = apply_sles4sap_pint_image(
        cloud_provider="EC2",
        pint_query="http://DinkyIsland/",
        name_filter="Elaine",
        region_list=["MêléeIsland", "MonkeyIsland"],
    )
    assert res["SLES4SAP_QESAP_OS_VER"] == "ElaineMarley"
    assert res["SLES4SAP_QESAP_OS_VER_REGIONS"] == "MêléeIsland"
    assert res["SLES4SAP_QESAP_OS_VER_ID"] == "RootBeer"


def test_get_recent_pint_image():
    images = []
    ret = get_recent_pint_image(images, "test")
    assert ret is None

    img1 = {
        "name": "test",
        "state": "active",
        "publishedon": "20231212",
        "region": "south",
    }
    images.append(img1)
    ret = get_recent_pint_image(images, "test")
    assert ret == img1

    ret = get_recent_pint_image(images, "AAAAA")
    assert ret is None

    ret = get_recent_pint_image(images, "test", "north")
    assert ret is None

    ret = get_recent_pint_image(images, "test", "south")
    assert ret == img1

    ret = get_recent_pint_image(images, "test", "south", "inactive")
    assert ret is None

    img2 = {
        "name": "test",
        "state": "inactive",
        "publishedon": "20231212",
        "region": "south",
    }
    images.append(img2)
    ret = get_recent_pint_image(images, "test", "south", "inactive")
    assert ret == img2

    img3 = {
        "name": "test",
        "state": "inactive",
        "publishedon": "30231212",
        "region": "south",
    }
    images.append(img3)
    ret = get_recent_pint_image(images, "test", "south", "inactive")
    assert ret == img3


@responses.activate
def test_get_latest_tools_image():
    responses.add(
        responses.GET,
        re.compile(r"http://url/.*"),
        json={"build_results": []},
    )
    ret = get_latest_tools_image("http://url/results")
    assert ret is None

    responses.add(
        responses.GET,
        re.compile(r"http://url/.*"),
        json={
            "build_results": [
                {"failed": 10, "build": "AAAAA"},
                {"failed": 0, "build": "test"},
            ]
        },
    )
    ret = get_latest_tools_image("http://url/results")
    assert ret == "publiccloud_tools_test.qcow2"
