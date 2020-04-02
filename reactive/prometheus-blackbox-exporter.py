#!/usr/bin/python3
"""Installs and configures prometheus-blackbox-exporter."""

import os
from pathlib import Path
import shutil
from zipfile import BadZipFile, ZipFile

from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.core import hookenv, host
from charmhelpers.core.templating import render
from charms.layer import snap
from charms.reactive import (
    endpoint_from_flag,
    endpoint_from_name,
    hook,
    remove_state,
    set_state,
    when,
    when_all,
    when_not,
)
from charms.reactive.helpers import any_file_changed, data_changed
import yaml


DASHBOARD_PATH = os.getcwd() + '/templates/'
SNAP_NAME = 'prometheus-blackbox-exporter'
SVC_NAME = 'snap.prometheus-blackbox-exporter.daemon'
PORT_DEF = 9115
BLACKBOX_EXPORTER_YML_TMPL = 'blackbox.yaml.j2'
CONF_FILE_PATH = '/var/snap/prometheus-blackbox-exporter/current/blackbox.yml'


def templates_changed(tmpl_list):
    """Return list of changed files."""
    return any_file_changed(['templates/{}'.format(x) for x in tmpl_list])


@when_not('blackbox-exporter.installed')
def install_packages():
    """Installs the snap exporter."""
    hookenv.status_set('maintenance', 'Installing software')
    config = hookenv.config()
    channel = config.get('snap_channel', 'stable')
    snap.install(SNAP_NAME, channel=channel, force_dangerous=False)
    set_state('blackbox-exporter.installed')
    set_state('blackbox-exporter.do-check-reconfig')


@hook('upgrade-charm')
def upgrade():
    """Reset the install state on upgrade, to ensure resource extraction."""
    hookenv.status_set('maintenance', 'Charm upgrade in progress')
    update_dashboards_from_resource()
    set_state('blackbox-exporter.do-restart')


def get_modules():
    """Load the modules."""
    config = hookenv.config()
    try:
        modules = yaml.safe_load(config.get('modules'))
    except yaml.YAMLError as error:
        hookenv.log('Failed to load modules, '.format(error))
        return None

    if 'modules' in modules:
        return yaml.safe_dump(modules['modules'], default_flow_style=False)
    else:
        return yaml.safe_dump(modules, default_flow_style=False)


@when('blackbox-exporter.installed')
@when('blackbox-exporter.do-reconfig-yaml')
def write_blackbox_exporter_config_yaml():
    """Render the template."""
    modules = get_modules()
    render(source=BLACKBOX_EXPORTER_YML_TMPL,
           target=CONF_FILE_PATH,
           context={'modules': modules}
           )
    hookenv.open_port(PORT_DEF)
    set_state('blackbox-exporter.do-restart')
    remove_state('blackbox-exporter.do-reconfig-yaml')


@when('blackbox-exporter.started')
def check_config():
    """Check the config once started."""
    set_state('blackbox-exporter.do-check-reconfig')


@when('blackbox-exporter.do-check-reconfig')
def check_reconfig_blackbox_exporter():
    """Configure the exporter."""
    config = hookenv.config()

    if data_changed('blackbox-exporter.config', config):
        set_state('blackbox-exporter.do-reconfig-yaml')

    if templates_changed([BLACKBOX_EXPORTER_YML_TMPL]):
        set_state('blackbox-exporter.do-reconfig-yaml')

    remove_state('blackbox-exporter.do-check-reconfig')


@when('blackbox-exporter.do-restart')
def restart_blackbox_exporter():
    """Restart the exporter."""
    if not host.service_running(SVC_NAME):
        hookenv.log('Starting {}...'.format(SVC_NAME))
        host.service_start(SVC_NAME)
    else:
        hookenv.log('Restarting {}, config file changed...'.format(SVC_NAME))
        host.service_restart(SVC_NAME)
    hookenv.status_set('active', 'Ready')
    set_state('blackbox-exporter.started')
    remove_state('blackbox-exporter.do-restart')


# Relations
@when('blackbox-exporter.started')
@when('blackbox-exporter.available')
def configure_blackbox_exporter_relation():
    """Configure the http relation."""
    target = endpoint_from_name('blackbox-exporter')
    target.configure(PORT_DEF)
    remove_state('blackbox-exporter.configured')


@when('nrpe-external-master.changed')
def nrpe_changed():
    """Trigger nrpe update."""
    remove_state('blackbox-exporter.configured')


@when('blackbox-exporter.changed')
def prometheus_changed():
    """Trigger prometheus update."""
    remove_state('blackbox-exporter.prometheus_relation_configured')
    remove_state('blackbox-exporter.configured')


@when('nrpe-external-master.available')
@when_not('blackbox-exporter.configured')
def update_nrpe_config(svc):
    """Configure the nrpe check for the service."""
    if not os.path.exists('/var/lib/nagios'):
        hookenv.status_set('blocked', 'Waiting for nrpe package installation')
        return

    hookenv.status_set('maintenance', 'Configuring nrpe checks')

    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe_setup.add_check(shortname='prometheus_blackbox_exporter_http',
                         check_cmd='check_http -I 127.0.0.1 -p {} -u /metrics'.format(PORT_DEF),
                         description='Prometheus blackbox Exporter HTTP check')
    nrpe_setup.write()
    hookenv.status_set('active', 'ready')
    set_state('blackbox-exporter.configured')


@when('blackbox-exporter.configured')
@when_not('nrpe-external-master.available')
def remove_nrpe_check():
    """Remove the nrpe check."""
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe_setup.remove_check(shortname="prometheus_blackbox_exporter_http")
    remove_state('blackbox-exporter.configured')


@when_all('endpoint.dashboards.joined')
def register_grafana_dashboards():
    """After joining to grafana, push the dashboard."""
    grafana_endpoint = endpoint_from_flag('endpoint.dashboards.joined')

    if grafana_endpoint is None:
        return

    hookenv.log('Grafana relation joined, push dashboard')

    # load pre-distributed dashboards, that may havew been overwritten by resource
    dash_dir = Path(DASHBOARD_PATH)
    for dash_file in dash_dir.glob('*.json'):
        dashboard = dash_file.read_text()
        grafana_endpoint.register_dashboard(dash_file.stem, dashboard)
        hookenv.log('Pushed {}'.format(dash_file))


def update_dashboards_from_resource():
    """Extract resource zip file into templates directory."""
    dashboards_zip_resource = hookenv.resource_get('dashboards')
    if not dashboards_zip_resource:
        hookenv.log('No dashboards resource found', hookenv.DEBUG)
        # no dashboards zip found, go with the default distributed dashboard
        return

    hookenv.log('Installing dashboards from resource', hookenv.DEBUG)
    try:
        shutil.copy(dashboards_zip_resource, DASHBOARD_PATH)
    except IOError as error:
        hookenv.log('Problem copying resource: {}'.format(error), hookenv.ERROR)
        return

    try:
        with ZipFile(dashboards_zip_resource, 'r') as zipfile:
            zipfile.extractall(path=DASHBOARD_PATH)
            hookenv.log('Extracted dashboards from resource', hookenv.DEBUG)
    except BadZipFile as error:
        hookenv.log('BadZipFile: {}'.format(error), hookenv.ERROR)
        return
    except PermissionError as error:
        hookenv.log('Unable to unzip the provided resource: {}'.format(error), hookenv.ERROR)
        return

    register_grafana_dashboards()
