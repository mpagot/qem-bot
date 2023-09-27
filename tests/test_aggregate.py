# Copyright SUSE LLC
# SPDX-License-Identifier: MIT

from openqabot.types.aggregate import Aggregate
from unittest import mock
import pytest


def test_aggregate_constructor():
    """
    What is the bare minimal set of arguments
    needed by the constructor?
    """
    config = {}
    config["FLAVOR"] = None
    config["archs"] = None
    config["test_issues"] = {}
    acc = Aggregate("", None, config)


def test_aggregate_printable():
    """
    Try the printable
    """
    config = {}
    config["FLAVOR"] = None
    config["archs"] = None
    config["test_issues"] = {}
    acc = Aggregate("hello", None, config)
    assert "<Aggregate product: hello>" == str(acc)


def test_aggregate_call():
    """
    What is the bare minimal set of arguments
    needed by the callable?
    """
    config = {}
    config["FLAVOR"] = None
    config["archs"] = []
    config["test_issues"] = {}
    acc = Aggregate("", None, config)
    res = acc(None, None, None)
    assert res == []


@pytest.fixture
def request_mock(monkeypatch):
    """
    Aggregate is using requests to get old jobs
    from the QEM dashboard.
    At the moment the mock returned value
    is harcoded to [{}]
    """

    class MockResponse:
        # mock json() method always returns a specific testing dictionary
        @staticmethod
        def json():
            return [{}]

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(
        "openqabot.types.aggregate.requests.get",
        mock_get
    )


def test_aggregate_call_with_archs(request_mock):
    """
    Configure an archs to enter in the function main loop
    """
    my_config = {}
    my_config["FLAVOR"] = None
    my_config["archs"] = ["ciao"]
    my_config["test_issues"] = {}
    acc = Aggregate("", settings={}, config=my_config)
    res = acc(incidents=[], token=None, ci_url=None)
    assert res == []


@pytest.fixture
def incident_mock(monkeypatch):
    """
    Simulate an incident class, reimplementing it in the simplest
    possible way that is accepted by Aggregate
    """
    from typing import NamedTuple

    class Repos(NamedTuple):
        product: str
        version: str
        arch: str

    class MockIncident:
        def __init__(self, repo, embargoed):
            self.livepatch = None
            self.staging = None
            self.channels = [repo]
            self.embargoed = embargoed

    def _func(product, version, arch, embargoed=False):
        repo = Repos(product=product, version=version, arch=arch)
        return MockIncident(repo, embargoed=embargoed)

    return _func


def test_aggregate_call_with_test_issues(request_mock, incident_mock, monkeypatch):
    """
    Test with a valid incident
    """
    my_config = {}
    my_config["FLAVOR"] = None
    my_config["archs"] = ["ciao"]
    my_config["test_issues"] = {"AAAAAAA": "BBBBBBBBB:CCCCCCCC"}
    acc = Aggregate("", settings={}, config=my_config)
    res = acc(
        incidents=[incident_mock(product="BBBBBBBBB", version="CCCCCCCC", arch="ciao")],
        token=None,
        ci_url=None,
    )
    assert len(res) == 1


def test_aggregate_call_pc_pint(request_mock, monkeypatch):
    """
    Test with setting PUBLIC_CLOUD_PINT_QUERY to call apply_publiccloud_pint_image
    """

    def mockreturn(settings):
        return {"PUBLIC_CLOUD_IMAGE_ID": "Hola"}

    monkeypatch.setattr(
        "openqabot.types.aggregate.apply_publiccloud_pint_image",
        mockreturn,
    )

    my_config = {}
    my_config["FLAVOR"] = None
    my_config["archs"] = ["ciao"]
    my_config["test_issues"] = {}
    my_settings = {"PUBLIC_CLOUD_PINT_QUERY": None}
    acc = Aggregate("", settings=my_settings, config=my_config)
    acc(incidents=[], token=None, ci_url=None)


def test_aggregate_call_pc_pint_with_incidents(
    request_mock, incident_mock, monkeypatch
):
    """
    Test with incident and setting PUBLIC_CLOUD_PINT_QUERY to call apply_publiccloud_pint_image
    """

    def mockreturn(settings):
        return {"PUBLIC_CLOUD_IMAGE_ID": "Hola"}

    monkeypatch.setattr(
        "openqabot.types.aggregate.apply_publiccloud_pint_image",
        mockreturn,
    )
    my_config = {}
    my_config["FLAVOR"] = None
    my_config["archs"] = ["ciao"]
    my_config["test_issues"] = {"AAAAAAA": "BBBBBBBBB:CCCCCCCC"}
    my_settings = {"PUBLIC_CLOUD_PINT_QUERY": None}
    acc = Aggregate("", settings=my_settings, config=my_config)
    ret = acc(
        incidents=[incident_mock(product="BBBBBBBBB", version="CCCCCCCC", arch="ciao")],
        token=None,
        ci_url=None,
    )
    assert ret[0]["openqa"]["PUBLIC_CLOUD_IMAGE_ID"] == "Hola"


@mock.patch('openqabot.types.aggregate.apply_sles4sap_pint_image')
def test_aggregate_call_sles4sap_pint_image(mocked, request_mock, incident_mock):
    def mockreturn(*args, **kwargs):
        return {"SLES4SAP_QESAP_OS_VER": "Hola"}

    mocked.side_effect = mockreturn
    my_config = {}
    my_config["FLAVOR"] = 'Azure-SAP-BYOS-Incidents-saptune'
    my_config["archs"] = ["ciao"]
    my_config["test_issues"] = {"AAAAAAA": "BBBBBBBBB:CCCCCCCC"}
    base_url = 'https://susepubliccloudinfo.suse.com/v1'
    my_settings = {"SLES4SAP_PINT_QUERY": base_url}

    # call the code
    acc = Aggregate("", settings=my_settings, config=my_config)
    ret = acc(incidents=[incident_mock(product="BBBBBBBBB", version="CCCCCCCC", arch="ciao")], token=None, ci_url=None)

    # Check that Aggregate class is able to use FLAVOR to calculate
    # apply_sles4sap_pint_image first argument
    mocked.assert_called_with('AZURE', base_url, '')
    assert len(ret) == 1
    assert ret[0]['openqa']['SLES4SAP_QESAP_OS_VER'] == 'Hola'
