# CasaDNS - Dynamic DNS service for smart homes

## Custom component for HACS in Home Assistant

![Static Badge](https://img.shields.io/badge/HACS-Custom-blue?style=flat)

CasaDNS is a lightweight Dynamic DNS integration for Home Assistant.
It updates your CasaDNS DNS records automatically whenever your Home Assistant system’s public IP address changes.

This integration provides:

* UI-based configuration (Config Flow)
* Automatic public IP detection
* Periodic update checks
* DNS updates only when the IP changes
* Support for a single label or multiple comma-separated labels
* A manual service casadns.update_now for automations

## Features

**Automatic updates**

The integration periodically retrieves the system’s current public IPv4 address (via api.ipify.org).
If the IP has changed since the last check, a request is sent to:

`https://casadns.eu/update?domains=<labels>&token=<token>`

_CasaDNS uses the source IP of the request to update your DNS records._

**Manual update service**

A manual service is provided:

`casadns.update_now`

_This forces an update regardless of the cached IP address. Useful for testing or for use in automations._

## Installation (HACS — Custom Repository)

* Open HACS → Integrations
* Click ⋮ → Custom repositories
* Add the repository URL: `https://github.com/emtronictech/casadns-homeassistant`
* Select Integration
* Click Add
* Install the integration from HACS
* Restart Home Assistant
* Go to Settings → Devices & Services → Add Integration
* Choose CasaDNS

## Configuration

Configuration is handled entirely through the UI (config flow). You will be asked for:

**Domains**

_Comma separated values (subdomains) managed by CasaDNS. Do not include the .casadns.eu suffix. The CasaDNS backend applies the domain automatically._

**Token**

_Your API token for CasaDNS._

**Interval**

_Update interval in minutes (default: 5). During each interval the integration checks the public IP and updates CasaDNS only if the IP has changed._
