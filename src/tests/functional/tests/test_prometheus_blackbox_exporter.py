"""Encapsulate prometheus-blackbox-exporter testing."""
import logging
import time
import unittest

import zaza.model as model


CURL_TIMEOUT = 180
REQ_TIMEOUT = 12
DEFAULT_API_PORT = "9115"
DEFAULT_API_URL = "/metrics"


class BasePrometheusBlackboxExporterTest(unittest.TestCase):
    """Base for Prometheus-blackbox-exporter charm tests."""

    @classmethod
    def setUpClass(cls):
        """Set up tests."""
        super(BasePrometheusBlackboxExporterTest, cls).setUpClass()
        cls.model_name = model.get_juju_model()
        cls.application_name = "prometheus-blackbox-exporter"
        cls.lead_unit_name = model.get_lead_unit_name(
            cls.application_name, model_name=cls.model_name
        )
        cls.units = model.get_units(cls.application_name, model_name=cls.model_name)
        cls.prometheus_blackbox_exporter_ip = model.get_app_ips(cls.application_name)[0]


class CharmOperationTest(BasePrometheusBlackboxExporterTest):
    """Verify operations."""

    def test_01_api_ready(self):
        """Verify if the API is ready.

        Curl the api endpoint.
        We'll retry until the CURL_TIMEOUT.
        """
        curl_command = "curl http://localhost:{}/metrics".format(DEFAULT_API_PORT)
        timeout = time.time() + CURL_TIMEOUT
        while time.time() < timeout:
            response = model.run_on_unit(self.lead_unit_name, curl_command)
            if response["Code"] == "0":
                return
            logging.warning(
                "Unexpected curl response: {}. Retrying in 30s.".format(response)
            )
            time.sleep(30)

        # we didn't get rc=0 in the allowed time, fail the test
        self.fail(
            "Prometheus-blackbox-exporter didn't respond to the command \n"
            "'{curl_command}' as expected.\n"
            "Result: {result}".format(curl_command=curl_command, result=response)
        )

    def test_02_nrpe_http_check(self):
        """Verify nrpe check exists."""
        expected_nrpe_check = (
            "command[check_prometheus_blackbox_exporter_http]={} -I 127.0.0.1 "
            "-p {} -u {}"
        ).format(
            "/usr/lib/nagios/plugins/check_http", DEFAULT_API_PORT, DEFAULT_API_URL
        )
        logging.debug(
            "Verify the nrpe check is created and has the required content..."
        )
        cmd = "cat /etc/nagios/nrpe.d/check_prometheus_blackbox_exporter_http.cfg"
        result = model.run_on_unit(self.lead_unit_name, cmd)
        code = result.get("Code")
        if code != "0":
            raise model.CommandRunFailed(cmd, result)
        content = result.get("Stdout")
        self.assertTrue(expected_nrpe_check in content)
