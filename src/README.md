# Juju prometheus Blackbox exporter charm

This charm provides the [Prometheus Blackbox exporter](https://github.com/prometheus/blackbox_exporter), part of the [Prometheus](https://prometheus.io/) monitoring system

The charm should be related to the prometheus charm

## Configuration

To configure the blackbox exporter `modules` use the charm's `modules` config option.

As an example, if you store your exporter config in a local file called `modules.yaml`
you can update the charm's configuration using:

    juju config prometheus-blackbox-exporter modules=@modules.yaml

To confirm configuration was set:

    juju config prometheus-blackbox-exporter

## Testing

# This directory needs to be create in the charm path prior to testing
```
mkdir -p report/lint
```

## Deployment

# To avail of the metrics in grafana the following steps can be used
```
juju deploy grafana
juju deploy prometheus2
juju add-relation prometheus-blackbox-exporter:scrape prometheus2:target
juju add-relation prometheus-blackbox-exporter:dashboards grafana:dashboards
```

# To setup reporting with nagios
```
juju deploy nrpe
juju add-relation prometheus-blackbox-exporter:nrpe-external-master  nrpe:nrpe-external-master
```

# Change or update dashboards
```
# To provide your own dashboards, create a zip file and attach it as a resource 
zip grafana-dashboards.zip blackbox-simple.json blackbox-advanced.json
juju attach-resource prometheus-blackbox-exporter dashboards=./grafana-dashboards.zip
```

# Contact Information
- Charm bugs: https://bugs.launchpad.net/charm-prometheus-blackbox-exporter
