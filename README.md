<p align="center">
  <pre align="center">
██╗███╗   ███╗ █████╗ ██████╗     ████████╗ ██████╗  ██████╗ ██╗     
╚═╝████╗ ████║██╔══██╗██╔══██╗    ╚══██╔══╝██╔═══██╗██╔═══██╗██║     
██║██╔████╔██║███████║██████╔╝       ██║   ██║   ██║██║   ██║██║     
██║██║╚██╔╝██║██╔══██║██╔═══╝        ██║   ██║   ██║██║   ██║██║     
██║██║ ╚═╝ ██║██║  ██║██║            ██║   ╚██████╔╝╚██████╔╝███████╗
╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝            ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝
                                                                     
  </pre>
</p>

<p align="center">
  <strong>Unified IMAP Operational Suite</strong><br>
  <sub>Discover • Clean • Probe • Analyse • Report</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Cross--Platform-2f81f7?style=for-the-badge" alt="Cross Platform">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Version-2.6.0-orange?style=for-the-badge" alt="Version 2.6.0">
  <img src="https://img.shields.io/badge/Dependencies-Standard%20Library-success?style=for-the-badge" alt="Standard Library">
</p>

<p align="center">
  <em>A polished, high-concurrency terminal toolkit for authorised IMAP infrastructure discovery, cleanup, service analysis and reporting.</em>
</p>

---

## ⚡ What is iMapTool?

**iMapTool** is the evolution of **iMapPing** — rebuilt as a complete operational suite instead of a single connectivity checker.

It is designed for large domain lists and mail infrastructure that you **own or are explicitly authorised to assess**.

Instead of authentication or credential testing, iMapTool focuses on **network-level service discovery**:

```text
                    ┌─────────────────────────┐
                    │       DOMAIN LIST        │
                    └────────────┬────────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ iMap Scraper │ │  iMap Purge  │ │   iMap Ping  │
        │   Discover   │ │ Clean / Sort │ │ Service Probe│
        └──────────────┘ └──────────────┘ └──────┬───────┘
                                                 │
                           ┌─────────────────────┼─────────────────────┐
                           ▼                     ▼                     ▼
                    ┌────────────┐       ┌────────────┐       ┌────────────┐
                    │ TLS / CERT │       │ POP3/SMTP  │       │ IP / GeoIP │
                    │  Analysis  │       │   Mapping  │       │  Enrichment│
                    └────────────┘       └────────────┘       └────────────┘
                           │                     │                     │
                           └─────────────────────┼─────────────────────┘
                                                 ▼
                                      ┌────────────────────┐
                                      │  CSV + HTML + JSON │
                                      │  Dashboard / Logs  │
                                      └────────────────────┘
```

### The short version

**One tool. One workflow. A lot less manual work.**

---

## ✨ Feature Highlights

<table>
<tr>
<td width="50%" valign="top">

### 🔎 iMap Scraper
Discover conventional IMAP hostnames from a domain list.

- `imap.`
- `mail.`
- `secure.`
- `webmail.`
- `email.`
- `imap4.`
- `imapmail.`
- `mailserver.`

</td>
<td width="50%" valign="top">

### 🧹 iMap Purge
Clean large domain lists without having to write one-off scripts.

- Provider filtering
- Host / port stripping
- Duplicate removal
- Alphabetical sorting
- Full cleanup pipeline
- File statistics preview
- Automatic `.bak` backups

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📡 iMap Ping
Concurrent IMAP service discovery with live terminal feedback.

- IMAP banners
- Capabilities
- Authentication mechanisms
- TLS detection
- Provider fingerprints
- DNS / socket errors
- Timeout / refusal classification
- Bounded concurrency
- Resume support

</td>
<td width="50%" valign="top">

### 🔐 TLS & Certificate Analysis
Go beyond a simple "port open" result.

- TLS versions
- Security grading
- Weak cipher indicators
- STARTTLS support
- Certificate subject / issuer
- Validity dates
- Expired / self-signed flags
- Wildcard detection & coverage

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🌍 IP / ASN / GeoIP
Optional enrichment for resolved mail hosts.

- IP address
- ASN
- Organisation / hosting provider
- Country
- City
- Local result cache
- Disabled by default

</td>
<td width="50%" valign="top">

### 📬 POP3 / SMTP Mapping
Optional mail-service discovery alongside IMAP.

**POP3**
- `110`
- `995` TLS

**SMTP**
- `25`
- `465` TLS
- `587` Submission

Banner / service discovery only — no authentication.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📊 Offline HTML Reports
Turn Ping output into a standalone report you can open locally.

- Global search
- Status filtering
- Provider filtering
- TLS grade filtering
- Sortable columns
- Pagination
- TLS distribution
- Auth mechanism distribution
- Host distribution
- Summary cards

</td>
<td width="50%" valign="top">

### 🖥️ Polished CLI
Built to feel like a real application rather than a collection of scripts.

- Unified menus
- Multiple themes
- Live progress
- Run history
- Settings system
- Debug logging
- CLI automation
- CI/CD friendly operation
- Discord-compatible webhooks

</td>
</tr>
</table>

---

## 🎨 The UI

The terminal interface was deliberately redesigned around a **minimal, sleek and easy-on-the-eyes** layout.

### Available themes

```text
Classic    Midnight    Soft
Graphite   Ocean       Aurora
```

The default theme is **Midnight**.

```text
╭───  iMap Tool  ────────────────────────────────────────────────────╮
│  Unified IMAP Operational Suite                                    │
╰──────────────────────────────────────────────────────────────────╯

MAIN MENU

  [1]  iMap Scraper       Discover conventional IMAP hostnames.
  [2]  iMap Purge        Clean, filter, sort and normalise lists.
  [3]  iMap Ping         Probe IMAP services concurrently.
  [4]  Ping Dashboard    Review historical run statistics.
  [5]  Settings          Configure appearance and behaviour.
  [6]  Run History       Review previous runs.
  [0]  Exit              Close iMapTool.
```

The same visual language is used across Scraper, Purge, Ping, Dashboard and Settings.

---

## 🧰 Requirements

- **Python 3.10+ recommended**
- Windows, Linux or macOS
- No external `pip` packages required for normal operation
- Network access is required for live service probing
- Optional GeoIP enrichment uses the configured external endpoint

> **Authorisation:** Only use iMapTool against systems, domains and infrastructure that you own or have explicit permission to assess.

---

## 🚀 Getting Started

### 1. Download / clone the project

```bash
git clone <your-repository-url>
cd iMapTool
```

Or simply place `iMapTool.py` and your configuration file in the same working directory.

### 2. Check the installation

```bash
python iMapTool.py self-test
```

A successful self-test should report all checks passing.

### 3. Start the application

```bash
python iMapTool.py
```

That's it.

---

## 📁 Input Formats

The tool accepts simple domain lists:

```text
example.com
example.org
mail.example.net
```

Ping also understands explicit routing records:

```text
example.com | imap.example.com | 993
example.org | mail.example.org | 143
```

This makes it possible to feed Scraper → Purge → Ping as a continuous workflow.

---

# 🔎 iMap Scraper

The Scraper takes a domain list and generates candidate IMAP hostnames using the configured prefix list.

### Interactive

```bash
python iMapTool.py
```

Select:

```text
[1] iMap Scraper
```

### CLI

```bash
python iMapTool.py scraper \
  --input domains.txt \
  --output results/new_domains.txt
```

Sample a smaller portion of a large input:

```bash
python iMapTool.py scraper \
  --input domains.txt \
  --output results/new_domains.txt \
  --sample-size 100
```

---

# 🧹 iMap Purge

Purge provides six operations:

```text
[1] Filter providers
    Remove common consumer, cloud and hosted-mail providers.

[2] Strip IMAP host / port
    Convert "domain | host | port" records back to base domains.

[3] Remove duplicates
    Case-insensitive deduplication while preserving useful ordering.

[4] Sort alphabetically
    Sort domain records cleanly while keeping comments grouped.

[5] Full cleanup pipeline
    Strip IMAP details → deduplicate → filter providers → sort.

[6] Preview file statistics
    Inspect totals and duplicates without modifying the file.
```

### CLI example

```bash
python iMapTool.py purge \
  --input domains.txt \
  --output results/cleaned.txt \
  --mode 5
```

When an in-place purge is used and backups are enabled, iMapTool creates a `.bak` backup before modifying the original file.

---

# 📡 iMap Ping

Ping is the core service-discovery engine.

It performs bounded concurrent probes rather than creating an unbounded number of worker tasks for a huge input file.

### Basic usage

```bash
python iMapTool.py ping --input domains.txt
```

### Sample a large list

```bash
python iMapTool.py ping \
  --input domains.txt \
  --sample-size 100
```

### Dry run

Validate the input and planned workload without performing live probes:

```bash
python iMapTool.py ping \
  --input domains.txt \
  --dry-run
```

### Protocol selection

IMAP is enabled by default. Optional POP3 / SMTP mapping can be enabled:

```bash
python iMapTool.py ping \
  --input domains.txt \
  --protocols imap,pop3,smtp
```

### Optional GeoIP enrichment

```bash
python iMapTool.py ping \
  --input domains.txt \
  --geoip
```

### Disable deeper analysis

```bash
python iMapTool.py ping \
  --input domains.txt \
  --no-certificate-analysis \
  --no-tls-analysis \
  --no-html
```

---

## 🔐 What Ping Checks

Depending on configuration, iMap Ping can record:

```text
Host / domain
Port
Connection status
Response / banner
IMAP capabilities
Authentication mechanisms
Provider fingerprint
TLS used
TLS version
Cipher information
STARTTLS support
TLS security grade
Certificate subject
Certificate issuer
Certificate validity
Certificate flags
Resolved IP
ASN / organisation
Country / city
Protocol mapping results
```

### What it does NOT do

```text
✗ No mailbox login
✗ No password testing
✗ No credential guessing
✗ No brute-force authentication
✗ No mailbox content access
```

The protocol mapping features are limited to **service/banner discovery** on the standard mail ports supported by the application.

---

# 🛡️ TLS Security Analysis

iMapTool can inspect the TLS characteristics exposed by a mail service.

Example fields include:

```text
TLSv1
TLSv1.1
TLSv1.2
TLSv1.3
STARTTLS
Cipher
Security grade
Weak cipher indicators
```

The tool can flag legacy TLS versions and other weak indicators so you can quickly identify infrastructure that deserves attention.

---

# 📜 Certificate Analysis

Certificate inspection can include:

```text
Subject
Issuer / CA
Not Before
Not After
Expired
Self-signed
Wildcard
Wildcard coverage
```

This is particularly useful when the service is reachable but the certificate configuration is unexpected.

---

# 🌍 IP / ASN / GeoIP

GeoIP enrichment is **optional and disabled by default**.

When enabled, iMapTool can enrich resolved IP addresses with:

```text
IP
ASN
Organisation / hosting provider
Country
City
```

Results are cached locally to reduce repeated lookups.

The endpoint is configurable:

```json
{
  "geoip_enabled": false,
  "geoip_endpoint": "https://ipapi.co/{ip}/json/",
  "geoip_timeout_seconds": 3.0,
  "geoip_cache_file": "results/geoip_cache.json"
}
```

> Enabling GeoIP means IP addresses may be sent to the configured external service. Review the provider's terms and privacy policy before enabling it.

---

# 📬 POP3 / SMTP Mapping

Optional protocol mapping lets Ping discover additional mail services.

### POP3

```text
110  → POP3
995  → POP3 over TLS
```

### SMTP

```text
25   → SMTP
465  → SMTP over TLS
587  → Submission
```

Enable through Settings → Deep Analysis, or from the CLI:

```bash
python iMapTool.py ping \
  --input domains.txt \
  --protocols imap,pop3,smtp
```

These probes are for **banner / service discovery only**.

---

# 📊 Offline HTML Reports

After a Ping run, iMapTool can generate:

```text
results/
└── ping/
    └── <run-id>/
        ├── ping_report.csv
        ├── run_summary.json
        └── imap_report.html
```

The HTML report is **standalone and offline**.

No CDN.
No external JavaScript.
No external CSS.

Open it locally in any modern browser.

### Report features

```text
┌──────────────────────────────────────────────────────────────┐
│                    iMapTool Report                            │
├──────────────────────────────────────────────────────────────┤
│ Total │ Direct IMAP │ TLS Rows │ Legacy TLS                  │
├──────────────────────────────────────────────────────────────┤
│ Search: [____________________________]                        │
│ Status: [ All ▼ ]  Provider: [ All ▼ ]  TLS: [ All ▼ ]       │
├──────────────────────────────────────────────────────────────┤
│ Sortable results table                                       │
│                                                              │
│                         Page 1 / N                            │
└──────────────────────────────────────────────────────────────┘
```

### Generate a report manually

```bash
python iMapTool.py report \
  --input results/ping/<run-id>/ping_report.csv
```

Or specify the output file:

```bash
python iMapTool.py report \
  --input ping_report.csv \
  --output report.html
```

---

# 📈 Dashboard & Run History

The dashboard provides a quick overview of previous runs and stored result data.

Run History lets you review recent result directories and summaries without manually digging through the filesystem.

```bash
python iMapTool.py dashboard
python iMapTool.py history
```

Typical run data includes:

```text
Tool
Input
Total entries
Working / non-working results
Duration
Run directory
Report paths
```

---

# 🔔 Discord-Compatible Webhooks

iMapTool can send completion notifications to a configured **Discord-compatible incoming webhook**.

No Discord account login is performed.

### Configuration

```json
{
  "webhook_enabled": false,
  "webhook_url": "",
  "webhook_on_completion": true
}
```

### Interactive configuration

```text
Settings
  └── Webhook

      [1] Enable / disable
      [2] Set webhook URL
      [3] Test webhook
      [4] Completion notifications
      [5] Clear webhook URL
```

### Test from the CLI

```bash
python iMapTool.py webhook-test
```

Notifications contain run summaries rather than credentials or mailbox contents.

---

# ⚙️ Settings

The settings area is organised into focused sections:

```text
APPLICATION SETTINGS

  [1] Display & Theme
  [2] Performance
  [3] Run Behaviour
  [4] File Paths
  [5] Deep Analysis
  [6] Webhook
  [7] Restore Defaults
  [0] Back
```

### Deep Analysis

```text
[1] Certificate analysis
[2] TLS security analysis
[3] POP3 mapping
[4] SMTP mapping
[5] GeoIP / ASN mapping
[6] Offline HTML reports
```

### CLI settings

View settings:

```bash
python iMapTool.py settings
```

Change a setting:

```bash
python iMapTool.py settings set ping_workers 100
```

The value can be supplied as JSON or as a raw string where appropriate.

---

# 🧪 Self-Test

Run the built-in checks:

```bash
python iMapTool.py self-test
```

This is useful after editing the configuration or updating the script.

---

# 🤖 CLI / Automation / CI-CD

iMapTool is designed to work interactively **and** as a command-line utility.

### Available commands

```text
python iMapTool.py --help

python iMapTool.py ping --help
python iMapTool.py scraper --help
python iMapTool.py purge --help
python iMapTool.py report --help

python iMapTool.py dashboard
python iMapTool.py history
python iMapTool.py self-test

python iMapTool.py theme midnight
python iMapTool.py settings
python iMapTool.py settings set ping_workers 100

python iMapTool.py webhook-test
```

Because CLI mode does not wait for interactive "Press Enter" prompts, it can be used from scheduled jobs and CI pipelines.

### Example scheduled workflow

```text
domains.txt
     │
     ▼
   Purge
     │
     ▼
 cleaned.txt
     │
     ▼
   Ping
     │
     ├──────────────► ping_report.csv
     ├──────────────► run_summary.json
     ├──────────────► imap_report.html
     └──────────────► webhook notification
```

---

# 💾 Checkpoint & Resume

Large Ping jobs can be resumed when checkpointing is enabled.

```json
{
  "resume_enabled": true,
  "retry_count": 1
}
```

This is useful for long-running jobs where you do not want to start the entire dataset again after an interruption.

---

# 📂 Results Structure

A typical results directory can contain:

```text
results/
├── debug.log
├── geoip_cache.json
├── working.txt
├── dead.txt
├── hosted_provider.txt
├── auth_restricted.txt
├── ping_report.csv
├── ping_checkpoint.json
├── imap_dashboard.json
└── ping/
    └── <run-id>/
        ├── ping_report.csv
        ├── run_summary.json
        └── imap_report.html
```

The exact files produced depend on the enabled features and workflow.

---

# 🧩 Configuration

The application uses JSON configuration.

A minimal example:

```json
{
  "theme": "midnight",
  "ping_workers": 50,
  "scraper_workers": 50,
  "timeout_seconds": 2.5,
  "resume_enabled": true,
  "certificate_analysis": true,
  "tls_analysis": true,
  "geoip_enabled": false,
  "html_report_enabled": true,
  "webhook_enabled": false
}
```

### Core performance settings

```text
scraper_workers
ping_workers
timeout_seconds
progress_refresh_seconds
max_in_flight_multiplier
retry_count
```

### File settings

```text
scraper_input_file
scraper_output_file
ping_input_file
working_output_file
dead_output_file
ping_report_file
ping_checkpoint_file
dashboard_file
debug_log
results_dir
```

### Service settings

```text
ports
prefixes
protocol_mapping
excluded_domains
auto_discover_hosts
```

---

# 🛠️ Troubleshooting

### `getaddrinfo() argument 1 must be string or None`

This normally indicates an invalid host value in the input record.

Use:

```text
domain | host | port
```

For example:

```text
example.com | imap.example.com | 993
```

### Nothing appears to happen

Check:

```bash
python iMapTool.py self-test
```

Then enable debug logging if needed:

```json
{
  "debug": true
}
```

Review:

```text
results/debug.log
```

### Terminal colours look wrong

Check:

```json
{
  "use_color": true,
  "use_unicode": true,
  "theme": "midnight"
}
```

If your terminal has limited ANSI support, try:

```text
theme = classic
```

### A Ping run was interrupted

If resume is enabled, rerun the same job and let iMapTool continue from its checkpoint.

---

# 🔒 Security & Responsible Use

iMapTool is intended for **authorised infrastructure assessment and operational maintenance**.

Use it only against:

- systems you own,
- infrastructure you administer,
- domains you are responsible for, or
- systems where you have explicit permission to test.

The application intentionally avoids mailbox authentication and credential attacks.

It performs service discovery, connectivity checks and optional protocol/TLS analysis. Even non-authenticated probes can generate logs, alerts or rate limits on remote infrastructure, so use sensible concurrency and timeouts for environments you control.

---

# 🧱 Project Layout

A typical project directory:

```text
iMapTool/
├── iMapTool.py
├── config.json
├── domains.txt
├── raw_domains.txt
├── results/
│   ├── ping/
│   ├── debug.log
│   └── ...
└── README.md
```

---

# 🗺️ Recommended Workflow

For a large authorised domain inventory:

```text
        ┌──────────────────┐
        │   Raw Domains    │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │   iMap Scraper   │
        │ Discover Hosts   │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │    iMap Purge    │
        │ Clean / Dedup    │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │     iMap Ping    │
        │ Service Discovery│
        └────────┬─────────┘
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
     TLS      POP3/SMTP   GeoIP
       │         │         │
       └─────────┼─────────┘
                 ▼
        ┌──────────────────┐
        │ CSV / JSON / HTML│
        │ Dashboard / Hook │
        └──────────────────┘
```

**Scrape → Purge → Ping → Analyse → Report**

---

# 🧑‍💻 Development

Before making a release:

```bash
python -m py_compile iMapTool.py
python iMapTool.py self-test
```

Keep the application standard-library-only unless a future release explicitly introduces external dependencies.

---

# 📜 Licence

Add your preferred licence here before publishing the repository.

The previous iMapPing project used the **MIT** licence badge; if this project is intended to remain MIT licensed, include the corresponding `LICENSE` file in the repository.

---

# 💙 Support the Developer

If iMapTool saves you time or makes your workflow easier, supporting development is appreciated.

**Bitcoin (BTC)**

```text
bc1qm427zm2jxmesulwjd4j95k82ck9h7l9n7wqemt
```

**Ethereum (ETH)**

```text
0xf6bf5446Efe20f1404016895c6deaf0F22EF76CE
```

**Stellar (XLM)**

```text
GBDLBCAE75FO3QNB5VWCWMEOIV2GEP7UFPP3CQICPM3KOZ2YVY55E7OJ
```

---

<p align="center">
  <strong>iMapTool 2.6.0</strong><br>
  <sub>Built by REEGZL • Unified IMAP Operational Suite</sub>
</p>

<p align="center">
  ⭐ If you find it useful, consider starring the repository.
</p>

<p align="center">
  <em>Discover. Clean. Probe. Analyse. Report.</em>
</p>
