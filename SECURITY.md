# Security policy

## Supported versions

Security fixes are applied to the latest published Storm Detector release. Before reporting a problem, reproduce it on that release when it is safe to do so.

## Reporting a vulnerability

Do **not** open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting for this repository:

https://github.com/petrvnk/storm-detector/security/advisories/new

Include:

- the affected Storm Detector and Home Assistant versions;
- the impact and required preconditions;
- minimal reproduction steps or a proof of concept;
- suggested remediation, if known.

Do not include Home Assistant access tokens, exact home coordinates, private entity IDs, addresses, or unrelated logs. The maintainer aims to acknowledge a complete report within seven days. A fix and disclosure timeline depends on severity, reproducibility, and maintainer availability.

## Scope

Relevant reports include vulnerabilities in the integration backend, bundled custom card, configuration flow, diagnostics redaction, external URL validation, and release/update path.

Availability or data-quality problems in third-party services such as RainViewer or a lightning provider are normally upstream support issues unless Storm Detector handles them insecurely.
