# CasaDNS for Home Assistant

[![Static Badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge\&logo=homeassistantcommunitystore\&logoColor=white)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/emtronictech/casadns-homeassistant?include_prereleases\&style=for-the-badge)](https://github.com/emtronictech/casadns-homeassistant/releases)

CasaDNS is a dynamic DNS service for smart homes. This custom Home Assistant integration keeps your configured CasaDNS records in sync with the public IP address of your Home Assistant instance.

The integration periodically checks your public IP address and only sends an update to CasaDNS when the IP address has changed. You can also force an update manually using the `casadns.update_now` action.

## Features

* UI-based configuration through the Home Assistant config flow
* Automatic public IP detection
* Periodic update checks
* DNS updates only when the public IP address changes
* Support for a single CasaDNS domain or multiple comma-separated domains
* Manual update action: `casadns.update_now`
* Sensor attributes for status, last HTTP status, last error and last check time
* Optional response data for manual update actions

## How it works

CasaDNS periodically retrieves the current public IP address using `https://api64.ipify.org`.

If the public IP address has changed since the previous check, the integration sends an update request to CasaDNS. If the IP address is unchanged, no CasaDNS update is sent.

The integration can also be triggered manually with the `casadns.update_now` action. A manual update always forces a CasaDNS update request, even if the cached IP address has not changed.

## Installation through HACS

This integration is currently available as a HACS custom repository.

1. Open HACS in Home Assistant.

2. Go to Integrations.

3. Open the three-dot menu.

4. Choose Custom repositories.

5. Add this repository URL:

   ```text
   https://github.com/emtronictech/casadns-homeassistant
   ```

6. Select Integration as the category.

7. Click Add.

8. Install the CasaDNS integration from HACS.

9. Restart Home Assistant.

10. Go to Settings → Devices & services → Add integration.

11. Search for CasaDNS and follow the setup steps.

## Configuration

Configuration is handled entirely through the Home Assistant UI.

You will be asked for the following values.

### Domains

Enter one CasaDNS subdomain or multiple comma-separated CasaDNS subdomains.

Do not enter a full domain name. Only enter the CasaDNS subdomain part.

Examples:

```text
username
```

Or multiple domains:

```text
username,username.camera,username.nas
```

### Token

Enter your CasaDNS API token.

Keep this token private. Anyone with access to this token may be able to update your CasaDNS records.

### Interval

The update interval in minutes.

The default interval is 15 minutes. During each interval, the integration checks the public IP address and only sends an update to CasaDNS when the IP address has changed.

## Entities

This integration creates one sensor.

| Entity                     | Description                                                     |
| -------------------------- | --------------------------------------------------------------- |
| `sensor.casadns_public_ip` | Shows the last known public IP address used for CasaDNS updates |

The sensor includes these attributes.

| Attribute      | Description                           |
| -------------- | ------------------------------------- |
| `status`       | Current CasaDNS status                |
| `public_ip`    | Last known public IP address          |
| `last_status`  | Last HTTP status returned by CasaDNS  |
| `last_error`   | Last error message, if any            |
| `last_updated` | Timestamp of the last check or update |

## Status values

The `status` attribute can have these values.

| Status         | Meaning                                                                |
| -------------- | ---------------------------------------------------------------------- |
| `ok`           | CasaDNS was updated successfully                                       |
| `unchanged`    | The public IP address has not changed, so no CasaDNS update was needed |
| `ip_error`     | The integration could not determine the current public IP address      |
| `update_error` | The CasaDNS update request failed                                      |

## Manual update action

You can force a CasaDNS update from Home Assistant with this action:

```yaml
action: casadns.update_now
```

When response data is requested, the action returns the current CasaDNS state.

Example response:

```yaml
status: ok
public_ip: 203.0.113.10
last_status: 200
last_error: null
last_updated: "2026-06-08T12:00:00+00:00"
domains: home
interval_minutes: 15
```

This can be useful for debugging, scripts or automations.

## Troubleshooting

### The sensor shows `ip_error`

The integration could not determine the current public IP address.

Check whether Home Assistant has internet access and can reach:

```text
https://api64.ipify.org
```

### The sensor shows `update_error`

The CasaDNS update request failed.

Check the following:

* Your CasaDNS token
* The configured CasaDNS domains
* Whether CasaDNS is reachable from Home Assistant
* The Home Assistant logs for the exact HTTP status or error message

### The status is `unchanged`

This is normal.

It means the public IP address is the same as during the previous check, so no CasaDNS update was needed.

### The action `casadns.update_now` does not appear

Restart Home Assistant after installing or updating the integration.

Also check whether the integration is loaded successfully under Settings → Devices & services.

## Security

Your CasaDNS token is stored in Home Assistant's config entry storage.

The token is sent to CasaDNS using an `Authorization: Bearer` header. It is not included in the request URL. This helps prevent the token from appearing in URL logs, proxy logs or browser-style request logs.

Do not share Home Assistant diagnostics or configuration files publicly if they may contain private CasaDNS details.

Debug logs may include configured domain names and CasaDNS status information, but the CasaDNS token is not included in the integration's debug output.

## Support

Issues and feature requests can be reported on GitHub:

```text
https://github.com/emtronictech/casadns-homeassistant/issues
```
