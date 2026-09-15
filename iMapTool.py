import os
import socket
import ssl
import urllib.request
import urllib.parse
import zipfile
import io
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import threading
import subprocess
import shutil
import copy
import json
import csv
import argparse
import sys
import re
from pathlib import Path

APP_VERSION = "2.6.0"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ==================== CONFIG & SETUP ====================
DEFAULT_CONFIG = {
    "debug": False,
    "results_dir": "results",
    "use_unicode": True,
    "use_color": True,
    "ui_style": "minimal",
    "theme": "midnight",
    "purge_backup": True,
    "progress_refresh_seconds": 0.25,
    "max_in_flight_multiplier": 2,
    "scraper_workers": 50,
    "ping_workers": 50,
    "timeout_seconds": 2.5,
    "scraper_input_file": "raw_domains.txt",
    "scraper_output_file": "results/new_domains.txt",
    "ping_input_file": "domains.txt",
    "working_output_file": "results/working.txt",
    "dead_output_file": "results/dead.txt",
    "debug_log": "results/debug.log",
    "ping_report_file": "results/ping_report.csv",
    "ping_checkpoint_file": "results/ping_checkpoint.json",
    "dashboard_file": "results/imap_dashboard.json",
    "hosted_output_file": "results/hosted_provider.txt",
    "restricted_output_file": "results/auth_restricted.txt",
    "retry_count": 1,
    "resume_enabled": True,
    "auto_discover_hosts": True,
    "prefixes": [
        "imap.", "mail.", "secure.", "webmail.", "email.",
        "imap4.", "imapmail.", "mailserver."
    ],
    "ports": [993, 143],
    "webhook_enabled": False,
    "webhook_url": "",
    "webhook_on_completion": True,
    "geoip_enabled": False,
    "geoip_endpoint": "https://ipapi.co/{ip}/json/",
    "geoip_timeout_seconds": 3.0,
    "geoip_cache_file": "results/geoip_cache.json",
    "certificate_analysis": True,
    "tls_analysis": True,
    "protocol_mapping": {"imap": True, "pop3": False, "smtp": False},
    "html_report_enabled": True,
    "html_report_file": "results/imap_report.html",
    "excluded_domains": [
        "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", 
        "outlook.com", "hotmail.com", "live.com", "msn.com", 
        "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", 
        "protonmail.com", "zoho.com", "gmx.com", "mail.com"
    ]
}

def load_config(path="config.json"):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            raise ValueError("configuration root must be a JSON object")
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg.update(loaded)
        return cfg
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"\033[33m[WARN] \033[0mFailed to parse {path} ({e}), falling back to defaults.")
        return copy.deepcopy(DEFAULT_CONFIG)

CFG = load_config()

def _validate_config(cfg):
    errors = []

    for key in ("scraper_workers", "ping_workers"):
        value = cfg.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{key} must be a positive integer")

    timeout = cfg.get("timeout_seconds")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        errors.append("timeout_seconds must be a positive number")

    prefixes = cfg.get("prefixes")
    if not isinstance(prefixes, list) or not all(isinstance(x, str) for x in prefixes):
        errors.append("prefixes must be a list of strings")

    ports = cfg.get("ports")
    if not isinstance(ports, list) or not ports or not all(
        isinstance(p, int) and not isinstance(p, bool) and 1 <= p <= 65535
        for p in ports
    ):
        errors.append("ports must be a non-empty list of integers from 1 to 65535")

    excluded = cfg.get("excluded_domains")
    if not isinstance(excluded, list) or not all(isinstance(x, str) for x in excluded):
        errors.append("excluded_domains must be a list of strings")

    retry_count = cfg.get("retry_count")
    if not isinstance(retry_count, int) or isinstance(retry_count, bool) or retry_count < 0:
        errors.append("retry_count must be a non-negative integer")

    if not isinstance(cfg.get("resume_enabled"), bool):
        errors.append("resume_enabled must be true or false")

    if not isinstance(cfg.get("use_unicode"), bool):
        errors.append("use_unicode must be true or false")

    if not isinstance(cfg.get("use_color"), bool):
        errors.append("use_color must be true or false")

    if cfg.get("ui_style") not in {"minimal", "classic"}:
        errors.append("ui_style must be either 'minimal' or 'classic'")

    if cfg.get("theme") not in {"classic", "midnight", "soft", "graphite", "ocean", "aurora"}:
        errors.append("theme must be one of: classic, midnight, soft, graphite, ocean, aurora")

    if not isinstance(cfg.get("purge_backup"), bool):
        errors.append("purge_backup must be true or false")

    multiplier = cfg.get("max_in_flight_multiplier")
    if not isinstance(multiplier, int) or isinstance(multiplier, bool) or not 1 <= multiplier <= 4:
        errors.append("max_in_flight_multiplier must be an integer from 1 to 4")

    refresh = cfg.get("progress_refresh_seconds")
    if not isinstance(refresh, (int, float)) or isinstance(refresh, bool) or refresh <= 0:
        errors.append("progress_refresh_seconds must be a positive number")

    for key in (
        "results_dir",
        "ping_report_file", "ping_checkpoint_file", "dashboard_file",
        "hosted_output_file", "restricted_output_file"
    ):
        if not isinstance(cfg.get(key), str) or not cfg.get(key).strip():
            errors.append(f"{key} must be a non-empty string")

    if errors:
        raise ValueError("Invalid configuration: " + "; ".join(errors))

_validate_config(CFG)


def _create_run_directory(tool_name):
    """Create a unique, timestamped folder for one tool run."""
    base = Path(CFG["results_dir"]) / tool_name
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    suffix = 1
    while True:
        name = stamp if suffix == 1 else f"{stamp}_{suffix}"
        run_dir = base / name
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            return run_dir
        except FileExistsError:
            suffix += 1


def _write_run_summary(run_dir, tool_name, started, finished, totals, counts):
    non_failures = {
        "imap_reachable", "imap_reachable_auth_advertised",
        "hosted_provider", "auth_restricted", "login_disabled",
        "discovered",
    }
    failures = [
        {"reason": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if name not in non_failures
    ][:5]
    summary = {
        "tool": tool_name,
        "started_at": started,
        "finished_at": finished,
        "duration_seconds": round(finished - started, 2),
        "totals": totals,
        "counts": counts,
        "top_failure_reasons": failures,
    }
    with open(Path(run_dir) / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def _find_resumable_ping_run(input_file, total_lines):
    """Return the newest durable Ping checkpoint compatible with this input."""
    base = Path(CFG["results_dir"]) / "ping"
    if not base.exists():
        return None, set()
    for run_dir in sorted((p for p in base.iterdir() if p.is_dir()), reverse=True):
        checkpoint = run_dir / "ping_checkpoint.json"
        report_file = run_dir / "ping_report.csv"
        try:
            state = json.loads(checkpoint.read_text(encoding="utf-8"))
            if state.get("version") != 3:
                continue
            if state.get("input_file") != os.path.abspath(input_file):
                continue
            if state.get("total") != total_lines:
                continue
            indexes = {
                int(i) for i in state.get("completed_indexes", [])
                if isinstance(i, int) and 0 <= i < total_lines
            }
            if not indexes or not report_file.is_file():
                continue
            # Checkpoints are written only after buffered report data is flushed.
            # Refuse a damaged/incomplete checkpoint rather than silently skipping input.
            with open(report_file, "r", newline="", encoding="utf-8", errors="replace") as f:
                rows = sum(1 for _ in csv.DictReader(f))
            if rows != len(indexes):
                # Never resume when the report is ahead of the checkpoint;
                # doing so could duplicate output rows after a crash.
                continue
            return run_dir, indexes
        except (OSError, ValueError, TypeError, json.JSONDecodeError, csv.Error):
            continue
    return None, set()

def _latest_ping_dashboard():
    dashboards = []
    root = Path(CFG["results_dir"]) / "ping"
    if root.exists():
        dashboards = [p for p in root.glob("*/imap_dashboard.json") if p.is_file()]
    return max(dashboards, default=None, key=lambda path: path.stat().st_mtime)

DEBUG = CFG["debug"]
DEBUG_FILE = (
    str(_create_run_directory("debug") / "debug.log")
    if DEBUG else os.path.abspath(CFG["debug_log"])
)
_debug_proc = None
_debug_lock = threading.Lock()

if DEBUG:
    Path(DEBUG_FILE).parent.mkdir(parents=True, exist_ok=True)
    open(DEBUG_FILE, 'w', encoding='utf-8').close()
    # The old launcher used the Windows `start` shell command unconditionally.
    # Debug logging remains available everywhere, while the live viewer is opened
    # only when PowerShell is actually available.
    if os.name == "nt":
        try:
            powershell = shutil.which("pwsh") or shutil.which("powershell")
            if powershell:
                subprocess.Popen(
                    [powershell, "-NoExit", "-Command",
                     f'Get-Content -Path "{DEBUG_FILE}" -Wait -Tail 50'],
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
                )
        except (OSError, ValueError):
            pass

def dprint(*args, **kwargs):
    if DEBUG:
        msg = " ".join(str(a) for a in args)
        with _debug_lock:
            with open(DEBUG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"[DEBUG] {msg}\n")

HOST_PREFIXES = CFG["prefixes"]
TARGET_PORTS = CFG["ports"]
EXCLUDED_DOMAINS = set(CFG["excluded_domains"])
USE_UNICODE = CFG["use_unicode"]
USE_COLOR = CFG["use_color"]
PROGRESS_REFRESH_SECONDS = CFG["progress_refresh_seconds"]


class _PlainConsole:
    """Remove ANSI colour codes while retaining terminal layout."""
    _ansi = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        return self._stream.write(self._ansi.sub("", text))

    def flush(self):
        return self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


if not USE_COLOR:
    class _PlainConsole:
        # Strip colour SGR sequences only. Keep cursor/line-control sequences so
        # live progress can still hide the cursor and erase its own line.
        _sgr = re.compile(r"\x1B\[[0-9;]*m")
        def __init__(self, stream):
            self._stream = stream
        def write(self, text):
            return self._stream.write(self._sgr.sub("", text))
        def flush(self):
            return self._stream.flush()
        def __getattr__(self, name):
            return getattr(self._stream, name)

    sys.stdout = _PlainConsole(sys.stdout)
    sys.stderr = _PlainConsole(sys.stderr)


class _ThemeConsole:
    """Translate the suite's semantic ANSI palette into the selected theme."""
    PALETTES = {
        "classic": {
            "\033[31m": "\033[31m", "\033[32m": "\033[32m",
            "\033[33m": "\033[33m", "\033[34m": "\033[34m",
            "\033[35m": "\033[35m", "\033[36m": "\033[36m",
            "\033[0m": "\033[0m",
        },
        "midnight": {
            "\033[31m": "\033[91m", "\033[32m": "\033[96m",
            "\033[33m": "\033[37m", "\033[34m": "\033[94m",
            "\033[35m": "\033[96m", "\033[36m": "\033[97m",
            "\033[0m": "\033[0m",
        },
        "soft": {
            "\033[31m": "\033[91m", "\033[32m": "\033[92m",
            "\033[33m": "\033[90m", "\033[34m": "\033[37m",
            "\033[35m": "\033[96m", "\033[36m": "\033[37m",
            "\033[0m": "\033[0m",
        },
        "graphite": {
            "\033[31m": "\033[91m", "\033[32m": "\033[92m",
            "\033[33m": "\033[93m", "\033[34m": "\033[90m",
            "\033[35m": "\033[97m", "\033[36m": "\033[96m",
            "\033[0m": "\033[0m",
        },
        "aurora": {
            "\033[31m": "\033[91m", "\033[32m": "\033[92m",
            "\033[33m": "\033[93m", "\033[34m": "\033[96m",
            "\033[35m": "\033[95m", "\033[36m": "\033[97m",
            "\033[0m": "\033[0m",
        },
        "ocean": {
            "\033[31m": "\033[91m", "\033[32m": "\033[96m",
            "\033[33m": "\033[97m", "\033[34m": "\033[94m",
            "\033[35m": "\033[96m", "\033[36m": "\033[97m",
            "\033[0m": "\033[0m",
        },
    }
    def __init__(self, stream, theme="classic"):
        self._stream = stream
        self.theme = theme if theme in self.PALETTES else "classic"
    def write(self, text):
        if not isinstance(text, str):
            text = str(text)
        for old, new in self.PALETTES[self.theme].items():
            text = text.replace(old, new)
        return self._stream.write(text)
    def flush(self):
        return self._stream.flush()
    def __getattr__(self, name):
        return getattr(self._stream, name)


def _install_theme(theme):
    if USE_COLOR:
        sys.stdout = _ThemeConsole(sys.__stdout__, theme)
        sys.stderr = _ThemeConsole(sys.__stderr__, theme)
    else:
        sys.stdout = _PlainConsole(sys.__stdout__)
        sys.stderr = _PlainConsole(sys.__stderr__)


def _refresh_output_mode():
    _install_theme(CFG.get("theme", "midnight"))


if USE_COLOR:
    _install_theme(CFG["theme"])


def _clear_screen():
    if os.name == "nt":
        os.system("cls")
    else:
        try:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
        except (AttributeError, OSError):
            pass


def _pause(message="Press Enter to return to the main menu..."):
    if globals().get("CLI_MODE", False):
        return
    try:
        input(f"\n\033[36m{message}\033[0m")
    except EOFError:
        return


def _menu_row(key, label, description=""):
    if description:
        print(f"  \033[35m[{key}]\033[0m  {label:<28} \033[33m{description}\033[0m")
    else:
        print(f"  \033[35m[{key}]\033[0m  {label}")


def _section(title):
    print(f"\033[36m{title}\033[0m")


def _print_banner(banner, title):
    """Render the same compact header on every screen."""
    left, right, line = ("╭", "╮", "─") if USE_UNICODE else ("+", "+", "-")
    side = "│" if USE_UNICODE else "|"
    bottom_left, bottom_right = ("╰", "╯") if USE_UNICODE else ("+", "+")
    inner_width = 68
    prefix = f"───  {title}  "
    remaining = max(1, inner_width - len(prefix))
    top = prefix + line * remaining
    subtitle = "  Unified IMAP Operational Suite"
    print(f"\033[36m{left}{top[:inner_width]}{right}\033[0m")
    print(f"\033[36m{side}\033[0m{_fit_box_text(subtitle, inner_width)}\033[36m{side}\033[0m")
    print(f"\033[36m{bottom_left}{line * inner_width}{bottom_right}\033[0m\n")


def _fit_box_text(text, width):
    marker = "…" if USE_UNICODE else "."
    if len(text) > width:
        text = text[:width - len(marker)] + marker
    return text.ljust(width)


def _progress_bar(completed, total, width=28):
    filled = int(width * completed / total) if total else 0
    full, empty = ("█", "─") if USE_UNICODE else ("#", "-")
    return full * filled + empty * (width - filled)


def _start_live_line():
    print("\033[?25l", end="", flush=True)


def _finish_live_line():
    # Always move the cursor onto a fresh line before normal prompts/output.
    print("\033[K\033[?25h", end="", flush=True)
    print(flush=True)


def _print_run_header(tool, total, workers, run_dir):
    left, right, divider = ("╭", "╮", "─") if USE_UNICODE else ("+", "+", "-")
    side = "│" if USE_UNICODE else "|"
    bottom_left, bottom_right = ("╰", "╯") if USE_UNICODE else ("+", "+")
    title = f"───  {tool} RUN  "
    inner_width = 68
    top = title + divider * max(1, inner_width - len(title))
    print(f"\033[36m{left}{top[:inner_width]}{right}\033[0m")
    details = (
        f"  Targets: {total:,}   Workers: {workers}   Timeout: {CFG['timeout_seconds']}s",
        f"  Results: {run_dir}",
    )
    for detail in details:
        print(f"\033[36m{side}\033[0m{_fit_box_text(detail, inner_width)}\033[36m{side}\033[0m")
    print(f"\033[36m{bottom_left}{divider * inner_width}{bottom_right}\033[0m")


def _print_completion_panel(tool, run_dir, duration, primary_label, primary_value):
    print(f"\n\033[32m[DONE]\033[0m {tool} completed in {duration:.1f}s")
    print(f"  \033[36m{primary_label}:\033[0m {primary_value:,}")
    print(f"  \033[36mResults:\033[0m {run_dir}")

# AUTHORIZED-SCOPE NOTICE:
# Use iMapTool only against domains/hosts you own or are explicitly authorized to assess.
# The suite performs service/banner discovery and capability inspection only; it does not
# submit usernames, passwords, app passwords, OAuth tokens, or mailbox commands.

MAIN_BANNER = """\033[35m
██╗███╗   ███╗ █████╗ ██████╗    ████████╗ ██████╗  ██████╗ ██╗     
╚═╝████╗ ████║██╔══██╗██╔══██╗   ╚══██╔══╝██╔═══██╗██╔═══██╗██║     
██║██╔████╔██║███████║██████╔╝      ██║   ██║   ██║██║   ██║██║     
██║██║╚██╔╝██║██╔══██║██╔═══╝       ██║   ██║   ██║██║   ██║██║     
██║██║ ╚═╝ ██║██║  ██║██║           ██║   ╚██████╔╝╚██████╔╝███████╗
╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝           ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝ 
                 [ \033[0mUnified IMAP Operational Suite \033[35m]                 
\033[0m"""

# ==================== TOOL 1: iMap Scraper ====================
SCRAPER_BANNER = """\033[35m
██╗███╗   ███╗ █████╗ ██████╗    ███████╗ ██████╗██████╗  █████╗ ██████╗ ███████╗██████╗ 
╚═╝████╗ ████║██╔══██╗██╔══██╗   ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗
██║██╔████╔██║███████║██████╔╝   ███████╗██║     ██████╔╝███████║██████╔╝█████╗  ██████╔╝
██║██║╚██╔╝██║██╔══██║██╔═══╝    ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗
██║██║ ╚═╝ ██║██║  ██║██║        ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗██║  ██║
╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝        ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝
\033[0m"""

def fetch_and_filter_domains(input_file=None):
    target_file = input_file or CFG["scraper_input_file"]
    print("\033[33m[INFO] \033[0mFetching live bulk domain list from public security repositories...\033[0m")
    url = "https://s3-us-west-1.amazonaws.com/umbrella-static/top-1m.csv.zip"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as zf:
                csv_filename = zf.namelist()[0]
                with zf.open(csv_filename) as f:
                    lines = [line.decode('utf-8', errors='ignore') for line in f.readlines()]
            
        filtered_domains = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            parts = [p.strip() for p in stripped.split(',')]
            if parts:
                domain = parts[-1].lower()
                if domain and domain not in EXCLUDED_DOMAINS:
                    filtered_domains.append(domain)
                    
        Path(target_file).parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(filtered_domains) + "\n")
            
        print(f"\033[32m[SUCCESS] \033[0mDownloaded and filtered \033[34m{len(filtered_domains)} \033[0mindependent/corporate domains into \033[34m'{target_file}'\033[0m.\n")
    except Exception as e:
        print(f"\033[31m[ERROR] \033[0mFailed to fetch live domain list: \033[34m{e}\033[0m")

def verify_imap(host, port, timeout=None):
    t_val = timeout if timeout is not None else CFG["timeout_seconds"]
    try:
        with socket.create_connection((host, port), timeout=t_val) as sock:
            sock.settimeout(t_val)
            if port == 993:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    banner = ssock.read(1024).decode('utf-8', errors='ignore')
                    if '* ok' in banner.lower():
                        return True
            else:
                banner = sock.recv(1024).decode('utf-8', errors='ignore')
                if '* ok' in banner.lower():
                    return True
    except (socket.timeout, socket.gaierror, ConnectionError, OSError, ssl.SSLError) as ex:
        dprint(f"IMAP verification failed for {host}:{port} -> {ex}")
    return False

def probe_domain_hosts(domain):
    domain = domain.strip().lower()
    if not domain or domain.startswith('#') or domain in EXCLUDED_DOMAINS:
        return None

    candidates = []
    seen = set()
    for prefix in HOST_PREFIXES:
        host = f"{prefix}{domain}"
        if host not in seen:
            seen.add(host)
            candidates.append(host)
    if domain not in seen:
        candidates.append(domain)

    for host in candidates:
        for port in TARGET_PORTS:
            dprint(f"Scraper probing {host}:{port} for {domain}...")
            if verify_imap(host, port):
                dprint(f"Scraper IMAP banner OK on {host}:{port}")
                return f"{domain} | {host} | {port}\n"
            else:
                dprint(f"Scraper fail/no banner {host}:{port}")

    return None

def run_scraper(input_file=None, output_file=None, sample_size=None):
    in_file = input_file or CFG["scraper_input_file"]
    _clear_screen()
    _print_banner(SCRAPER_BANNER, "iMap Scraper")
    
    if not os.path.exists(in_file):
        fetch_and_filter_domains(in_file)

    if not os.path.exists(in_file):
        _pause()
        return

    with open(in_file, 'r', encoding='utf-8', errors='ignore') as f:
        domains = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    total_domains = len(domains)
    if total_domains == 0:
        print(f"\033[33m[INFO] \033[34m'{in_file}' \033[0mis empty.\n")
        _pause()
        return

    if sample_size is not None:
        domains = domains[:sample_size]
        total_domains = len(domains)
        print(f"\033[33m[SAMPLE MODE]\033[0m Limiting this run to {total_domains} entries.")

    run_dir = _create_run_directory("scraper")
    out_file = output_file or str(run_dir / "new_domains.txt")

    max_workers = CFG["scraper_workers"]
    print(f"\033[33m[INFO] \033[0mScraping independent IMAP infrastructure across \033[34m{total_domains} \033[0mtargets using \033[34m{max_workers} \033[0mthreads...\n")
    _print_run_header("SCRAPER", total_domains, max_workers, run_dir)
    
    _start_live_line()

    completed_count = 0
    found_count = 0
    lock = threading.Lock()
    results_buffer = []

    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    open(out_file, 'w', encoding='utf-8').close()
    start_time = time.time()
    last_render = [0.0]
    cancelled = [False]

    futures_map = {}
    next_domain = 0
    in_flight_limit = max_workers * max(1, CFG.get("max_in_flight_multiplier", 2))

    def refill(executor):
        nonlocal next_domain
        while next_domain < total_domains and len(futures_map) < in_flight_limit:
            future = executor.submit(probe_domain_hosts, domains[next_domain])
            futures_map[future] = domains[next_domain]
            next_domain += 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        refill(executor)
        while futures_map:
            try:
                done, _ = wait(futures_map, return_when=FIRST_COMPLETED)
                for future in done:
                    domain_key = futures_map.pop(future, None)
                    if domain_key is None:
                        continue
                    try:
                        result = future.result()
                    except Exception as ex:
                        dprint(f"Scraper worker exception for {domain_key} -> {ex}")
                        result = None
                    
                    with lock:
                        completed_count += 1
                        if result:
                            found_count += 1
                            results_buffer.append(result)

                        if len(results_buffer) >= 10:
                            with open(out_file, 'a', encoding='utf-8') as f:
                                f.writelines(results_buffer)
                            results_buffer.clear()

                        now = time.time()
                        if (now - last_render[0] >= PROGRESS_REFRESH_SECONDS
                                or completed_count == total_domains):
                            percent = (completed_count / total_domains) * 100
                            bar = _progress_bar(completed_count, total_domains)
                            
                            elapsed = time.time() - start_time
                            rate = completed_count / elapsed if elapsed > 0 else 0
                            eta_sec = (total_domains - completed_count) / rate if rate > 0 else 0
                            m, s = divmod(int(eta_sec), 60)
                            h, m = divmod(m, 60)
                            eta_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

                            status_str = f"\r\033[36m[{bar}]\033[0m \033[33m{percent:.1f}%\033[0m ({completed_count:,}/{total_domains:,}) | \033[32mFound {found_count:,}\033[0m | \033[35mETA {eta_str}\033[0m\033[K"
                            print(status_str, end="", flush=True)
                            last_render[0] = now

                    refill(executor)

            except KeyboardInterrupt:
                _finish_live_line()
                print("\033[33m[PAUSED] Operation paused by user.\033[0m")
                print("  \033[35m[1]\033[0m Resume / Unpause")
                print("  \033[35m[2]\033[0m Return to Main Menu")
                choice = input("\n\033[36mSelect option > \033[0m").strip()

                if results_buffer:
                    with open(out_file, 'a', encoding='utf-8') as f:
                        f.writelines(results_buffer)
                    results_buffer.clear()

                if choice == '2':
                    for f in list(futures_map.keys()):
                        f.cancel()
                    cancelled[0] = True
                    break
                else:
                    print("\n\n\n", flush=True)
                    _start_live_line()
                    continue

    if results_buffer:
        with open(out_file, 'a', encoding='utf-8') as f:
            f.writelines(results_buffer)

    if cancelled[0]:
        finished = time.time()
        _finish_live_line()
        print(f"\033[33m[CANCELLED]\033[0m Scraper stopped at {completed_count:,}/{total_domains:,} targets.")
        print(f"  Partial results: {out_file}")
        print(f"  Run directory:   {run_dir}")
        _pause()
        return

    finished = time.time()
    _write_run_summary(
        run_dir, "scraper", start_time, finished,
        {"input_entries": total_domains, "discovered": found_count},
        {"discovered": found_count, "no_imap_endpoint": total_domains - found_count}
    )

    _finish_live_line()
    _print_completion_panel("Scraper", run_dir, finished - start_time, "Discovered", found_count)
    print(f"\033[36m[DISCOVERED]\033[0m {out_file}")
    print(f"\033[36m[SUMMARY]\033[0m {run_dir / 'run_summary.json'}")
    _pause()

# ==================== TOOL 2: iMap Purge ====================
PURGE_BANNER = """\033[35m
██╗███╗   ███╗ █████╗ ██████╗    ██████╗ ██╗   ██╗██████╗  ██████╗ ███████╗
╚═╝████╗ ████║██╔══██╗██╔══██╗   ██╔══██╗██║   ██║██╔══██╗██╔════╝ ██╔════╝
██║██╔████╔██║███████║██████╔╝   ██████╔╝██║   ██║██████╔╝██║  ███╗█████╗  
██║██║╚██╔╝██║██╔══██║██╔═══╝    ██╔═══╝ ██║   ██║██╔══██║██║   ██║██╔══╝  
██║██║ ╚═╝ ██║██║  ██║██║        ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝        ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
\033[0m"""

def _domain_matches_keyword(domain, host, keyword):
    text = f"{domain} {host}".lower()
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return re.search(pattern, text) is not None



def _purge_file(input_file, output_file, mode_choice):
    blocked_keywords = [
        "outlook", "office365", "microsoft", "live.com", "hotmail", "google",
        "gmail", "gsuite", "googlemail", "yahoo", "icloud", "me.com", "mac.com",
        "aol.com", "verizon", "att.net", "sbcglobal", "comcast", "xfinity",
        "charter", "spectrum", "btinternet", "virginmedia", "orange.fr", "wanadoo",
        "libero.it", "tiscali", "proton", "tutanota", "tuta.com", "posteo", "riseup",
        "163.com", "126.com", "qq.com", "sina.com", "emailsrvr", "rackspace",
        "ionos", "1und1"
    ]
    with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if not lines:
        raise ValueError("input file is empty")

    def strip_imap(items):
        result = []
        for line in items:
            s = line.strip()
            if not s or s.startswith("#"):
                result.append(line if line.endswith("\n") else line + "\n")
            else:
                result.append(s.split("|", 1)[0].strip() + "\n")
        return result

    def dedupe(items):
        seen, result = set(), []
        for line in items:
            s = line.strip()
            if not s:
                if not result or result[-1].strip():
                    result.append("\n")
            elif s.startswith("#"):
                result.append(line if line.endswith("\n") else line + "\n")
            elif s.casefold() not in seen:
                seen.add(s.casefold())
                result.append(s + "\n")
        return result

    def filter_providers(items):
        result, removed = [], 0
        for line in items:
            s = line.strip()
            if not s or s.startswith("#"):
                result.append(line if line.endswith("\n") else line + "\n")
                continue
            parts = [part.strip() for part in s.split("|")]
            domain = parts[0].casefold() if parts else ""
            host = parts[1].casefold() if len(parts) > 1 else ""
            if any(_domain_matches_keyword(domain, host, keyword) for keyword in blocked_keywords):
                removed += 1
            else:
                result.append(s + "\n")
        return result, removed

    def sort_entries(items):
        comments = [x for x in items if not x.strip() or x.strip().startswith("#")]
        data = sorted(
            (x for x in items if x.strip() and not x.strip().startswith("#")),
            key=lambda x: x.strip().casefold()
        )
        return comments + data

    processed = lines[:]
    removed = 0
    if mode_choice == "1":
        processed, removed = filter_providers(processed)
    elif mode_choice == "2":
        processed = strip_imap(processed)
    elif mode_choice == "3":
        processed = dedupe(processed)
    elif mode_choice == "4":
        processed = sort_entries(processed)
    elif mode_choice == "5":
        processed = strip_imap(processed)
        processed = dedupe(processed)
        processed, removed = filter_providers(processed)
        processed = sort_entries(processed)
    else:
        raise ValueError("invalid purge mode")

    input_abs = os.path.abspath(input_file)
    output_abs = os.path.abspath(output_file)
    backup = None
    if CFG.get("purge_backup", True) and input_abs == output_abs:
        backup = output_abs + ".bak"
        shutil.copy2(output_abs, backup)

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    tmp = output_file + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.writelines(processed)
        os.replace(tmp, output_file)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass

    return {
        "input": len(lines),
        "output": len(processed),
        "filtered": removed,
        "backup": backup
    }


def run_purge(input_file=None, output_file=None, mode=None, interactive=True):
    _clear_screen()
    _print_banner(PURGE_BANNER, "iMap Purge")

    in_default = CFG["scraper_output_file"]
    out_default = "results/domains_cleaned.txt"
    if interactive:
        domains_file = input(f"\033[36mInput file\033[0m [\033[34m{in_default}\033[0m] > ").strip() or in_default
    else:
        domains_file = input_file or in_default

    if not os.path.isfile(domains_file):
        print(f"\n\033[31m[ERROR]\033[0m File not found: \033[34m{domains_file}\033[0m")
        _pause()
        return False

    if interactive:
        out_file = input(f"\033[36mOutput file\033[0m [\033[34m{out_default}\033[0m] > ").strip() or out_default
    else:
        out_file = output_file or out_default

    _section("PURGE OPERATIONS")
    print("  Select an operation below. Descriptions explain exactly what it changes.\n")
    rows = [
        ("1", "Filter providers", "Remove common consumer, cloud and hosted-mail providers."),
        ("2", "Strip IMAP host / port", "Convert 'domain | host | port' records back to base domains."),
        ("3", "Remove duplicates", "Case-insensitive deduplication while preserving useful ordering."),
        ("4", "Sort alphabetically", "Sort domain records cleanly while keeping comments grouped."),
        ("5", "Full cleanup pipeline", "Strip IMAP details, deduplicate, filter providers, then sort."),
        ("6", "Preview file statistics", "Inspect totals and duplicates without modifying the file."),
    ]
    for key, label, description in rows:
        _menu_row(key, label, description)
    _menu_row("0", "Back", "Return to the main menu without changing anything.")

    mode_choice = str(mode) if mode is not None else input("\n\033[36mSelect operation > \033[0m").strip()
    if mode_choice == "0":
        return False
    if mode_choice not in {"1", "2", "3", "4", "5", "6"}:
        print("\033[31m[ERROR]\033[0m Invalid operation.")
        _pause()
        return False

    try:
        if mode_choice == "6":
            with open(domains_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            data = [x.strip() for x in lines if x.strip() and not x.strip().startswith("#")]
            unique = {x.casefold() for x in data}
            _section("FILE STATISTICS")
            print(f"  Total lines:        {len(lines):,}")
            print(f"  Data entries:       {len(data):,}")
            print(f"  Unique entries:     {len(unique):,}")
            print(f"  Duplicate entries:  {len(data) - len(unique):,}")
            print(f"  IMAP-formatted:     {sum('|' in x for x in data):,}")
            _pause()
            return True

        stats = _purge_file(domains_file, out_file, mode_choice)
        print(f"\n\033[32m[DONE]\033[0m Purge operation {mode_choice} completed.")
        print(f"  Input entries:   {stats['input']:,}")
        print(f"  Output entries:  {stats['output']:,}")
        print(f"  Filtered:        {stats['filtered']:,}")
        if stats["backup"]:
            print(f"  Backup:          {stats['backup']}")
        print(f"  Output:          {out_file}")
        if not CLI_MODE:
            _send_run_webhook(
                "Purge",
                Path(out_file),
                [("Input", stats["input"]), ("Output", stats["output"]), ("Filtered", stats["filtered"])]
            )
        _pause()
        return True
    except (OSError, ValueError, UnicodeError) as ex:
        print(f"\n\033[31m[ERROR]\033[0m Could not complete purge: {ex}")
        _pause()
        return False

# ==================== TOOL 3: iMap Ping ====================
PING_BANNER = """\033[35m
██╗███╗   ███╗ █████╗ ██████╗    ██████╗ ██╗███╗   ██╗ ██████╗ 
╚═╝████╗ ████║██╔══██╗██╔══██╗   ██╔══██╗██║████╗  ██║██╔════╝ 
██║██╔████╔██║███████║██████╔╝   ██████╔╝██║██╔██╗ ██║██║  ███╗
██║██║╚██╔╝██║██╔══██║██╔═══╝    ██╔═══╝ ██║██║╚██╗██║██║   ██║
██║██║ ╚═╝ ██║██║  ██║██║        ██║     ██║██║ ╚████║╚██████╔╝
╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝        ╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝ 
\033[0m"""

def is_microsoft_certificate(ssock):
    try:
        cert = ssock.getpeercert()
        if not cert:
            return False
        
        alt_names = cert.get('subjectaltname', ())
        for entry_type, entry_value in alt_names:
            if isinstance(entry_type, str) and entry_type.lower() == 'dns':
                val = entry_value.lower()
                if any(ms_sig in val for ms_sig in ['outlook.com', 'office365.com', 'office.com', 'hotmail.com', 'live.com', 'protection.outlook', 'microsoftonline.com']):
                    dprint(f"Microsoft cert SAN match: {val}")
                    return True
    except Exception as ex:
        dprint(f"Cert parse exception: {ex}")
        pass
    return False


def _provider_hint(domain, host, banner="", capabilities=""):
    """Fingerprint common hosted providers from passive service metadata only."""
    text = f"{domain} {host} {banner} {capabilities}".lower()
    host_domain_text = f"{domain} {host}".lower()
    signatures = {
        "Microsoft": (
            "outlook.com", "office365.com", "office.com", "hotmail.com",
            "live.com", "microsoftonline.com", "protection.outlook",
            "outlook.office365.com"
        ),
        "Google": ("gmail.com", "googlemail.com", "google.com", "aspmx.l.google.com"),
        "Yahoo": ("yahoo.com", "ymail.com"),
        "Apple": ("icloud.com", "me.com", "mac.com"),
        "Proton": ("proton.me", "protonmail.com"),
        "Zoho": ("zoho.com",),
        "AOL": ("aol.com",),
        "GMX": ("gmx.com", "gmx.net"),
        "Rackspace": ("emailsrvr.com", "rackspace.com"),
        "IONOS": ("ionos.com", "1and1.com", "1und1.de"),
    }
    for provider, needles in signatures.items():
        for needle in needles:
            escaped = re.escape(needle.lower())
            if re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", host_domain_text):
                return provider
            if needle.lower() in banner.lower() or needle.lower() in capabilities.lower():
                return provider
    return "Unknown"


def _extract_auth_mechanisms(capabilities):
    caps = (capabilities or "").upper()
    known = (
        "LOGIN", "PLAIN", "XOAUTH2", "OAUTHBEARER", "CRAM-MD5",
        "NTLM", "GSSAPI", "DIGEST-MD5"
    )
    return sorted({m for m in known if f"AUTH={m}" in caps})


def _classify_imap_result(provider, banner, capabilities, error_type=None):
    """Classify reachability without attempting authentication."""
    if error_type:
        return error_type
    b = (banner or "").strip().lower()
    c = (capabilities or "").lower()
    if not b.startswith("* ok"):
        return "no_imap_banner"
    if "logindisabled" in c:
        return "login_disabled"
    auth = _extract_auth_mechanisms(capabilities)
    if auth and not any(x in auth for x in ("LOGIN", "PLAIN")) and any(
        x in auth for x in ("XOAUTH2", "OAUTHBEARER")
    ):
        return "auth_restricted"
    if provider != "Unknown":
        return "hosted_provider"
    if auth:
        return "imap_reachable_auth_advertised"
    return "imap_reachable"


def _read_until_tag(sock_obj, tag, timeout):
    chunks = []
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            chunk = sock_obj.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            joined = b"".join(chunks).decode("utf-8", errors="ignore")
            if tag.lower() in joined.lower():
                break
        except socket.timeout:
            break
    return b"".join(chunks).decode("utf-8", errors="ignore")


def _probe_once(host, port, domain):
    """Probe one explicit IMAP endpoint. Never sends credentials."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    t_val = CFG["timeout_seconds"]

    try:
        with socket.create_connection((host, port), timeout=t_val) as sock:
            sock.settimeout(t_val)
            tls_used = False
            banner = ""
            capabilities = ""
            tls_version = ""
            cipher = ""

            if port == 993:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    tls_used = True
                    tls_version = ssock.version() or ""
                    cipher_info = ssock.cipher()
                    cipher = cipher_info[0] if cipher_info else ""
                    banner = ssock.recv(2048).decode("utf-8", errors="ignore")
                    if not banner.strip().lower().startswith("* ok"):
                        return {
                            "alive": False, "banner": banner, "capabilities": "",
                            "error_type": "no_imap_banner", "tls_used": True,
                            "tls_version": tls_version, "cipher": cipher
                        }
                    ssock.sendall(b"A001 CAPABILITY\r\n")
                    capabilities = _read_until_tag(ssock, "A001", t_val)
                    return {
                        "alive": True, "banner": banner, "capabilities": capabilities,
                        "error_type": None, "tls_used": True,
                        "tls_version": tls_version, "cipher": cipher
                    }

            banner = sock.recv(2048).decode("utf-8", errors="ignore")
            if not banner.strip().lower().startswith("* ok"):
                return {
                    "alive": False, "banner": banner, "capabilities": "",
                    "error_type": "no_imap_banner", "tls_used": False,
                    "tls_version": "", "cipher": ""
                }

            sock.sendall(b"A001 CAPABILITY\r\n")
            capabilities = _read_until_tag(sock, "A001", t_val)

            if port == 143 and "starttls" in capabilities.lower():
                sock.sendall(b"A002 STARTTLS\r\n")
                stls = _read_until_tag(sock, "A002", t_val)
                if "a002 ok" in stls.lower():
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        tls_used = True
                        tls_version = ssock.version() or ""
                        cipher_info = ssock.cipher()
                        cipher = cipher_info[0] if cipher_info else ""
                        ssock.sendall(b"A003 CAPABILITY\r\n")
                        capabilities = _read_until_tag(ssock, "A003", t_val)

            return {
                "alive": True, "banner": banner, "capabilities": capabilities,
                "error_type": None, "tls_used": tls_used,
                "tls_version": tls_version, "cipher": cipher
            }

    except socket.gaierror:
        return {"alive": False, "banner": "", "capabilities": "",
                "error_type": "dns_error", "tls_used": False,
                "tls_version": "", "cipher": ""}
    except socket.timeout:
        return {"alive": False, "banner": "", "capabilities": "",
                "error_type": "timeout", "tls_used": False,
                "tls_version": "", "cipher": ""}
    except ConnectionRefusedError:
        return {"alive": False, "banner": "", "capabilities": "",
                "error_type": "connection_refused", "tls_used": False,
                "tls_version": "", "cipher": ""}
    except ssl.SSLError as ex:
        dprint(f"TLS probe exception {host}:{port} -> {ex}")
        return {"alive": False, "banner": "", "capabilities": "",
                "error_type": "tls_error", "tls_used": True,
                "tls_version": "", "cipher": ""}
    except (ConnectionError, OSError) as ex:
        dprint(f"Network probe exception {host}:{port} -> {ex}")
        return {"alive": False, "banner": "", "capabilities": "",
                "error_type": "connection_error", "tls_used": False,
                "tls_version": "", "cipher": ""}


def _candidate_endpoints(domain):
    domain = domain.strip().lower().rstrip(".")
    candidates, seen = [], set()
    def add(host):
        host = host.strip().lower().rstrip(".")
        if not host:
            return
        for port in TARGET_PORTS:
            key = (host, port)
            if key not in seen:
                seen.add(key)
                candidates.append((host, port))
    for prefix in HOST_PREFIXES:
        add(f"{prefix}{domain}")
    add(domain)
    return candidates


def _valid_hostname(host):
    host = host.strip().rstrip(".")
    if not host or len(host) > 253 or " " in host:
        return False
    return re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", host) is not None


def test_single_domain(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return {
            "line": line, "direct_working": False, "domain": None,
            "provider": None, "host": None, "port": None,
            "status": "skipped", "auth_mechanisms": [],
            "tls_used": False, "tls_version": "", "cipher": "",
            "banner": "", "capabilities": ""
        }

    parts = [p.strip() for p in stripped.split("|")]
    domain = (parts[0] if parts and parts[0] else stripped).lower()

    if len(parts) > 1 and parts[1]:
        host = parts[1].strip().lower().rstrip(".")
        if not _valid_hostname(host):
            return {
                "line": line, "direct_working": False, "domain": domain,
                "provider": "Unknown", "host": host, "port": "", "status": "invalid_host",
                "auth_mechanisms": [], "tls_used": False, "tls_version": "", "cipher": "",
                "banner": "", "capabilities": ""
            }
        if len(parts) > 2 and parts[2]:
            try:
                port = int(parts[2])
            except (ValueError, TypeError):
                return {
                    "line": line, "direct_working": False, "domain": domain,
                    "provider": "Unknown", "host": host, "port": parts[2], "status": "invalid_port",
                    "auth_mechanisms": [], "tls_used": False, "tls_version": "", "cipher": "",
                    "banner": "", "capabilities": ""
                }
        else:
            port = 993
        if not 1 <= port <= 65535:
            return {
                "line": line, "direct_working": False, "domain": domain,
                "provider": "Unknown", "host": host, "port": port, "status": "invalid_port",
                "auth_mechanisms": [], "tls_used": False, "tls_version": "", "cipher": "",
                "banner": "", "capabilities": ""
            }
        endpoints = [(host, port)]
    else:
        endpoints = _candidate_endpoints(domain) if CFG.get(
            "auto_discover_hosts", True
        ) else [(domain, 993)]

    best = None
    attempts = CFG["retry_count"] + 1

    for host, port in endpoints:
        if not 1 <= port <= 65535:
            continue
        provider = _provider_hint(domain, host)
        last = None

        for attempt in range(1, attempts + 1):
            dprint(f"Ping probe {attempt}/{attempts} -> {host}:{port} ({domain})")
            result = _probe_once(host, port, domain)
            last = result
            if result["alive"]:
                provider = _provider_hint(
                    domain, host, result["banner"], result["capabilities"]
                )
                status = _classify_imap_result(
                    provider, result["banner"], result["capabilities"]
                )
                auth = _extract_auth_mechanisms(result["capabilities"])
                direct = status in {
                    "imap_reachable_auth_advertised", "imap_reachable"
                }
                row = {
                    "line": line, "direct_working": direct, "domain": domain,
                    "provider": provider, "host": host, "port": port,
                    "status": status, "auth_mechanisms": auth,
                    "tls_used": result["tls_used"],
                    "tls_version": result["tls_version"],
                    "cipher": result["cipher"],
                    "banner": result["banner"].strip(),
                    "capabilities": result["capabilities"].strip()
                }
                if best is None or (not best["direct_working"] and direct):
                    best = row
                if direct:
                    return row
                break
            if attempt < attempts:
                time.sleep(0.15)

        if best is None and last:
            best = {
                "line": line, "direct_working": False, "domain": domain,
                "provider": provider, "host": host, "port": port,
                "status": last["error_type"] or "connection_error",
                "auth_mechanisms": [], "tls_used": last["tls_used"],
                "tls_version": last["tls_version"], "cipher": last["cipher"],
                "banner": last["banner"].strip(),
                "capabilities": last["capabilities"].strip()
            }

    return best or {
        "line": line, "direct_working": False, "domain": domain,
        "provider": "Unknown", "host": "", "port": "",
        "status": "no_candidates", "auth_mechanisms": [],
        "tls_used": False, "tls_version": "", "cipher": "",
        "banner": "", "capabilities": ""
    }


def _write_dashboard(path, total, counts, started, finished):
    dashboard = {
        "generated_at": time.time(),
        "duration_seconds": round(finished - started, 2),
        "total_entries": total,
        "classifications": counts,
        "direct_working": counts.get("imap_reachable_auth_advertised", 0)
                           + counts.get("imap_reachable", 0),
        "hosted_provider": counts.get("hosted_provider", 0),
        "auth_restricted": counts.get("auth_restricted", 0)
                           + counts.get("login_disabled", 0),
        "network_failures": sum(
            counts.get(k, 0) for k in (
                "dns_error", "timeout", "connection_refused",
                "connection_error", "tls_error"
            )
        )
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2)


def _load_ping_report_state(report_file):
    """Rebuild counters from an existing report when resuming a run."""
    counts = {}
    working_count = 0
    completed_rows = 0
    if not os.path.isfile(report_file):
        return counts, working_count, completed_rows
    try:
        with open(report_file, "r", newline="", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                status = (row.get("status") or "worker_error").strip() or "worker_error"
                counts[status] = counts.get(status, 0) + 1
                if (row.get("direct_working") or "").strip().lower() == "yes":
                    working_count += 1
                completed_rows += 1
    except (OSError, csv.Error):
        return {}, 0, 0
    return counts, working_count, completed_rows


def run_ping(domains_file=None, output_working=None, output_dead=None,
             sample_size=None, dry_run=False):
    in_file = domains_file or CFG["ping_input_file"]

    if os.name == "nt":
        os.system("")
    _clear_screen()
    _print_banner(PING_BANNER, "iMap Ping")

    if not os.path.exists(in_file):
        print(f"\033[31m[ERROR] \033[34m'{in_file}' \033[0mnot found.\033[0m")
        _pause()
        return

    with open(in_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\r\n") for line in f
                 if line.strip() and not line.strip().startswith("#")]

    total_lines = len(lines)
    if total_lines == 0:
        print(f"\033[33m[INFO] \033[34m'{in_file}' \033[0mis empty.\033[0m")
        _pause()
        return

    if sample_size is not None:
        lines = lines[:sample_size]
        total_lines = len(lines)
        print(f"\033[33m[SAMPLE MODE]\033[0m Limiting this run to {total_lines} entries.")

    if dry_run:
        print("\033[33m[DRY RUN]\033[0m No network connections or output files will be created.")
        print(f"Would probe {total_lines:,} entries from: {in_file}")
        print(f"Would write a new run folder under: {Path(CFG['results_dir']) / 'ping'}")
        return

    run_dir, completed_indexes = (None, set())
    if sample_size is None and CFG.get("resume_enabled", True):
        run_dir, completed_indexes = _find_resumable_ping_run(in_file, total_lines)
    if run_dir is None:
        run_dir = _create_run_directory("ping")

    def output_paths(directory):
        return (
            output_working or str(directory / "working.txt"),
            output_dead or str(directory / "dead.txt"),
            str(directory / "hosted_provider.txt"),
            str(directory / "auth_restricted.txt"),
            str(directory / "ping_report.csv"),
            str(directory / "ping_checkpoint.json"),
            str(directory / "imap_dashboard.json"),
        )

    (out_work, out_dead, out_hosted, out_restricted, report_file,
     checkpoint_file, dashboard_file) = output_paths(run_dir)

    if completed_indexes:
        print(
            f"\033[33m[RESUME]\033[0m {len(completed_indexes)}/{total_lines} "
            f"entries are already complete."
        )
        choice = input("Resume from checkpoint? [Y/n]: ").strip().lower()
        if choice not in {"", "y", "yes"}:
            run_dir = _create_run_directory("ping")
            (out_work, out_dead, out_hosted, out_restricted, report_file,
             checkpoint_file, dashboard_file) = output_paths(run_dir)
            completed_indexes.clear()

    active_items = [(idx, line) for idx, line in enumerate(lines)
                    if idx not in completed_indexes]
    if not active_items:
        print("\033[32m[DONE]\033[0m Everything is already complete.")
        try:
            os.remove(checkpoint_file)
        except OSError:
            pass
        _pause()
        return

    if not completed_indexes:
        for filename in (
            out_work, out_dead, out_hosted, out_restricted, report_file
        ):
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            Path(filename).write_text("", encoding="utf-8")
        with open(report_file, "w", newline="", encoding="utf-8") as rf:
            csv.writer(rf).writerow([
                "domain", "host", "port", "provider", "status",
                "direct_working", "auth_mechanisms", "tls_used",
                "tls_version", "cipher", "banner", "capabilities", "input",
                "tls_versions", "tls_grade", "weak_cipher", "starttls",
                "cert_subject", "cert_issuer", "cert_not_before", "cert_not_after",
                "cert_expired", "cert_self_signed", "cert_wildcard", "cert_wildcard_coverage",
                "ip_addresses", "asn", "hosting_provider", "country", "city",
                "protocols", "protocol_hosts"
            ])

    max_workers = CFG["ping_workers"]
    print(
        f"\033[33m[INFO]\033[0m Probing {len(active_items):,} entries with "
        f"{max_workers} workers.\n"
        f"\033[33m[INFO]\033[0m Conventional IMAP discovery only; "
        f"no credentials or login attempts are performed.\n"
    )
    _print_run_header("PING", total_lines, max_workers, run_dir)
    _start_live_line()

    started = time.time()
    completed = len(completed_indexes)
    counts, working_count, report_rows = _load_ping_report_state(report_file) if completed_indexes else ({}, 0, 0)

    working_buffer, hosted_buffer, restricted_buffer = [], [], []
    dead_buffer, report_buffer = set(), []
    futures = {}
    cursor = [0]
    checkpoint_dirty = [0]
    in_flight_limit = max_workers * max(1, CFG.get("max_in_flight_multiplier", 2))
    last_render = [0.0]

    def flush():
        if working_buffer:
            with open(out_work, "a", encoding="utf-8") as f:
                f.writelines(x + "\n" for x in working_buffer)
            working_buffer.clear()
        if hosted_buffer:
            with open(out_hosted, "a", encoding="utf-8") as f:
                f.writelines(x + "\n" for x in hosted_buffer)
            hosted_buffer.clear()
        if restricted_buffer:
            with open(out_restricted, "a", encoding="utf-8") as f:
                f.writelines(x + "\n" for x in restricted_buffer)
            restricted_buffer.clear()
        if dead_buffer:
            with open(out_dead, "a", encoding="utf-8") as f:
                f.writelines(x + "\n" for x in sorted(dead_buffer))
            dead_buffer.clear()
        if report_buffer:
            with open(report_file, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(report_buffer)
            report_buffer.clear()

    def save_checkpoint():
        if not CFG.get("resume_enabled", True):
            return
        tmp = checkpoint_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "version": 3,
                "input_file": os.path.abspath(in_file),
                "total": total_lines,
                "completed_indexes": sorted(completed_indexes),
                "completed": len(completed_indexes),
                "updated": time.time()
            }, f)
        os.replace(tmp, checkpoint_file)

    def refill(executor):
        while cursor[0] < len(active_items) and len(futures) < in_flight_limit:
            idx, line = active_items[cursor[0]]
            futures[executor.submit(test_single_domain, line)] = idx
            cursor[0] += 1

    with ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="imap-ping"
    ) as executor:
        try:
            refill(executor)
            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    idx = futures.pop(future)
                    completed_indexes.add(idx)
                    completed += 1
                    checkpoint_dirty[0] += 1
                    try:
                        result = future.result()
                    except Exception as ex:
                        dprint(f"Ping worker exception -> {ex}")
                        result = {
                            "line": lines[idx], "direct_working": False,
                            "domain": "", "provider": "Unknown",
                            "host": "", "port": "", "status": "worker_error",
                            "auth_mechanisms": [], "tls_used": False,
                            "tls_version": "", "cipher": "",
                            "banner": "", "capabilities": ""
                        }

                    status = result["status"]
                    counts[status] = counts.get(status, 0) + 1
                    line = result["line"]
                    domain = result["domain"] or ""
                    provider = result["provider"] or "Unknown"
                    host = result["host"] or ""
                    port = result["port"] or ""

                    if result["direct_working"]:
                        working_count += 1
                        working_buffer.append(line)
                    elif status == "hosted_provider":
                        hosted_buffer.append(
                            f"{domain} | {host} | {port} | {provider}"
                        )
                    elif status in {"auth_restricted", "login_disabled"}:
                        restricted_buffer.append(
                            f"{domain} | {host} | {port} | {provider} | {status}"
                        )
                    elif domain:
                        dead_buffer.add(domain.lower())

                    report_buffer.append([
                        domain, host, port, provider, status,
                        "yes" if result["direct_working"] else "no",
                        ",".join(result["auth_mechanisms"]),
                        "yes" if result["tls_used"] else "no",
                        result["tls_version"], result["cipher"],
                        result["banner"], result["capabilities"], line,
                        ",".join(result.get("tls_versions", [])),
                        result.get("tls_grade", ""),
                        result.get("weak_cipher", ""),
                        result.get("starttls", ""),
                        result.get("cert_subject", ""),
                        result.get("cert_issuer", ""),
                        result.get("cert_not_before", ""),
                        result.get("cert_not_after", ""),
                        "yes" if result.get("cert_expired") else "no",
                        "yes" if result.get("cert_self_signed") else "no",
                        "yes" if result.get("cert_wildcard") else "no",
                        result.get("cert_wildcard_coverage", ""),
                        ",".join(result.get("ip_addresses", [])),
                        result.get("asn", ""),
                        result.get("hosting_provider", ""),
                        result.get("country", ""),
                        result.get("city", ""),
                        ";".join(f"{k}={v}" for k, v in result.get("protocols", {}).items()),
                        ";".join(f"{k}={v}" for k, v in result.get("protocol_hosts", {}).items())
                    ])

                    if checkpoint_dirty[0] >= 25:
                        flush()
                        save_checkpoint()
                        checkpoint_dirty[0] = 0

                    if (
                        len(working_buffer) >= 200
                        or len(hosted_buffer) >= 200
                        or len(restricted_buffer) >= 200
                        or len(dead_buffer) >= 200
                        or len(report_buffer) >= 200
                    ):
                        flush()

                    refill(executor)

                    now = time.time()
                    if (now - last_render[0] >= PROGRESS_REFRESH_SECONDS
                            or completed == total_lines):
                        elapsed = max(now - started, 0.001)
                        rate = completed / elapsed
                        eta = ((total_lines - completed) / rate) if rate else 0
                        h, rem = divmod(int(eta), 3600)
                        m, sec = divmod(rem, 60)
                        bar = _progress_bar(completed, total_lines)

                        print(
                            f"\r\033[36m[{bar}]\033[0m "
                            f"\033[33m{completed / total_lines * 100:5.1f}%\033[0m "
                            f"({completed:,}/{total_lines:,}) | "
                            f"\033[32mDirect {working_count:,}\033[0m | "
                            f"\033[35mHosted {counts.get('hosted_provider', 0):,}\033[0m | "
                            f"\033[31mRestricted {counts.get('auth_restricted', 0) + counts.get('login_disabled', 0):,}\033[0m | "
                            f"ETA {h:02d}:{m:02d}:{sec:02d}\033[K",
                            end="", flush=True
                        )
                        last_render[0] = now
        except KeyboardInterrupt:
            _finish_live_line()
            for future in futures:
                future.cancel()
            flush()
            save_checkpoint()
            print(
                f"\033[33m[PAUSED]\033[0m Checkpoint saved to "
                f"\033[34m{checkpoint_file}\033[0m."
            )
            _pause()
            return

    flush()
    finished = time.time()
    _write_dashboard(dashboard_file, total_lines, counts, started, finished)
    _write_run_summary(
        run_dir, "ping", started, finished,
        {"input_entries": total_lines, "direct_working": working_count}, counts
    )

    try:
        os.remove(checkpoint_file)
    except OSError:
        pass

    _finish_live_line()
    _print_completion_panel("Ping", run_dir, finished - started, "Direct IMAP", working_count)
    print(f"\033[36m[DIRECT]\033[0m {out_work}")
    print(f"\033[36m[HOSTED]\033[0m {out_hosted}")
    print(f"\033[36m[RESTRICTED]\033[0m {out_restricted}")
    print(f"\033[36m[OTHER/DEAD]\033[0m {out_dead}")
    print(f"\033[36m[CSV REPORT]\033[0m {report_file}")
    print(f"\033[36m[DASHBOARD]\033[0m {dashboard_file}")
    print(f"\033[36m[SUMMARY]\033[0m {run_dir / 'run_summary.json'}")
    html_report = None
    if CFG.get("html_report_enabled", True):
        try:
            html_report = _generate_html_report(report_file, run_dir / "imap_report.html", dashboard_file)
            print(f"\033[36m[HTML REPORT]\033[0m {html_report}")
        except Exception as ex:
            dprint(f"HTML report generation failed: {ex}")
            print(f"\033[33m[WARN]\033[0m HTML report could not be generated: {ex}")
    if CFG.get("webhook_enabled") and CFG.get("webhook_on_completion"):
        _send_run_webhook(
            "Ping", run_dir,
            [("Targets", f"{total_lines:,}"),
             ("Direct IMAP", f"{working_count:,}"),
             ("Hosted", f"{counts.get('hosted_provider', 0):,}"),
             ("Restricted", f"{counts.get('auth_restricted', 0) + counts.get('login_disabled', 0):,}"),
             ("HTML report", str(html_report or "not generated"))]
        )

    top = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    if top:
        print("\n\033[36m[CLASSIFICATION SUMMARY]\033[0m")
        for name, count in top:
            print(f"  {name:30} {count:,}")

    _pause()




# ==================== DEEP ANALYSIS / REPORTING ====================

def _enrichment_defaults():
    return {
        "tls_versions": [], "tls_grade": "Not assessed", "weak_cipher": "",
        "starttls": "unknown", "cert_subject": "", "cert_issuer": "",
        "cert_not_before": "", "cert_not_after": "", "cert_expired": False,
        "cert_self_signed": False, "cert_wildcard": False, "cert_wildcard_coverage": "",
        "ip_addresses": [], "asn": "", "hosting_provider": "", "country": "",
        "city": "", "protocols": {}, "protocol_hosts": {}
    }

def _certificate_from_socket(ssock, host):
    if not CFG.get("certificate_analysis", True):
        return {}
    try:
        der = ssock.getpeercert(binary_form=True)
        if not der:
            return {}
        pem = ssl.DER_cert_to_PEM_cert(der)
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False, encoding="ascii") as f:
            f.write(pem)
            temp_name = f.name
        try:
            cert = ssl._ssl._test_decode_cert(temp_name)
        finally:
            try:
                os.unlink(temp_name)
            except OSError:
                pass

        def flatten(name):
            return ", ".join(f"{k}={v}" for group in cert.get(name, ()) for k, v in group)

        sans = [v for k, v in cert.get("subjectAltName", ()) if str(k).upper() == "DNS"]
        subject = flatten("subject")
        issuer = flatten("issuer")
        from email.utils import parsedate_to_datetime

        def iso(value):
            try:
                return parsedate_to_datetime(value).isoformat() if value else ""
            except Exception:
                return value or ""

        not_after = cert.get("notAfter", "")
        try:
            expired = bool(not_after and parsedate_to_datetime(not_after).timestamp() < time.time())
        except Exception:
            expired = False

        wildcard_coverage = ""
        hostname = host.lower().rstrip(".")
        for pattern in (x for x in sans if x.startswith("*.")):
            suffix = pattern[2:].lower().rstrip(".")
            if hostname.endswith("." + suffix) and hostname.count(".") == suffix.count(".") + 1:
                wildcard_coverage = pattern
                break

        return {
            "cert_subject": subject,
            "cert_issuer": issuer,
            "cert_not_before": iso(cert.get("notBefore")),
            "cert_not_after": iso(not_after),
            "cert_expired": expired,
            "cert_self_signed": bool(subject and subject == issuer),
            "cert_wildcard": any(x.startswith("*.") for x in sans),
            "cert_wildcard_coverage": wildcard_coverage,
        }
    except Exception as ex:
        dprint(f"Certificate analysis failed for {host}: {ex}")
        return {}

def _certificate_from_probe(host, port):
    if not CFG.get("certificate_analysis", True) or port not in (993, 143):
        return {}
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=CFG["timeout_seconds"]) as sock:
            sock.settimeout(CFG["timeout_seconds"])
            if port == 143:
                sock.recv(2048)
                sock.sendall(b"A001 CAPABILITY\r\n")
                caps = _read_until_tag(sock, "A001", CFG["timeout_seconds"])
                if "starttls" not in caps.lower():
                    return {}
                sock.sendall(b"A002 STARTTLS\r\n")
                if "a002 ok" not in _read_until_tag(sock, "A002", CFG["timeout_seconds"]).lower():
                    return {}
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                return _certificate_from_socket(ssock, host)
    except (OSError, ssl.SSLError):
        return {}

def _probe_tls_versions(host, port):
    if not CFG.get("tls_analysis", True) or port not in (993, 143):
        return []
    versions = []
    for label, attr in (("TLSv1", "TLSv1"), ("TLSv1.1", "TLSv1_1"),
                        ("TLSv1.2", "TLSv1_2"), ("TLSv1.3", "TLSv1_3")):
        if not hasattr(ssl.TLSVersion, attr):
            continue
        try:
            ver = getattr(ssl.TLSVersion, attr)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.minimum_version = ver
            ctx.maximum_version = ver
            with socket.create_connection((host, port), timeout=CFG["timeout_seconds"]) as sock:
                sock.settimeout(CFG["timeout_seconds"])
                if port == 143:
                    sock.recv(2048)
                    sock.sendall(b"A001 CAPABILITY\r\n")
                    caps = _read_until_tag(sock, "A001", CFG["timeout_seconds"])
                    if "starttls" not in caps.lower():
                        continue
                    sock.sendall(b"A002 STARTTLS\r\n")
                    if "a002 ok" not in _read_until_tag(sock, "A002", CFG["timeout_seconds"]).lower():
                        continue
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    if ssock.version() == label:
                        versions.append(label)
        except (OSError, ssl.SSLError, ValueError):
            continue
    return versions

def _security_grade(versions, cipher, starttls):
    cipher_u = (cipher or "").upper()
    if any(x in cipher_u for x in ("RC4", "3DES", "DES-", "NULL", "EXPORT", "MD5", "ANON")):
        return "Weak"
    if any(x in set(versions) for x in ("TLSv1", "TLSv1.1")):
        return "Legacy"
    if starttls == "missing":
        return "Review"
    return "Strong" if versions else "Not assessed"

def _resolve_ips(host):
    try:
        return sorted({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
    except (socket.gaierror, OSError):
        return []

def _geo_lookup(ip):
    if not CFG.get("geoip_enabled", False):
        return {}
    cache_path = Path(CFG.get("geoip_cache_file", "results/geoip_cache.json"))
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    if ip in cache:
        return cache[ip]
    try:
        url = CFG["geoip_endpoint"].format(ip=urllib.parse.quote(ip, safe=""))
        req = urllib.request.Request(url, headers={"User-Agent": f"iMapTool/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=float(CFG.get("geoip_timeout_seconds", 3.0))) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        item = {
            "asn": str(data.get("asn") or ""),
            "hosting_provider": str(data.get("org") or data.get("organization") or ""),
            "country": str(data.get("country_name") or data.get("country") or ""),
            "city": str(data.get("city") or ""),
        }
        cache[ip] = item
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        os.replace(tmp, cache_path)
        return item
    except Exception as ex:
        dprint(f"GeoIP lookup failed for {ip}: {ex}")
        return {}

def _read_until_smtp(sock, timeout):
    chunks = []
    end = time.time() + timeout
    while time.time() < end:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk.decode("utf-8", errors="ignore"))
            if re.search(r"(?m)^250 ", "".join(chunks)):
                break
        except socket.timeout:
            break
    return "".join(chunks)

def _mail_protocol_probe(host, port, protocol):
    result = {"alive": False, "status": "unreachable", "tls": False,
              "tls_version": "", "cipher": "", "banner": ""}
    try:
        with socket.create_connection((host, port), timeout=CFG["timeout_seconds"]) as sock:
            sock.settimeout(CFG["timeout_seconds"])
            if (protocol == "pop3" and port == 995) or (protocol == "smtp" and port == 465):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    result["tls"] = True
                    result["tls_version"] = ssock.version() or ""
                    cipher = ssock.cipher()
                    result["cipher"] = cipher[0] if cipher else ""
                    result["banner"] = ssock.recv(2048).decode("utf-8", errors="ignore")
            else:
                result["banner"] = sock.recv(2048).decode("utf-8", errors="ignore")
            if protocol == "pop3":
                result["alive"] = result["banner"].lstrip().upper().startswith("+OK")
            else:
                result["alive"] = bool(re.match(r"^220[\s-]", result["banner"].strip()))
                if result["alive"] and port == 587:
                    sock.sendall(b"EHLO imaptool.local\r\n")
                    result["banner"] += "\n" + _read_until_smtp(sock, CFG["timeout_seconds"])
            result["status"] = "reachable" if result["alive"] else "unexpected_banner"
    except socket.gaierror:
        result["status"] = "dns_error"
    except socket.timeout:
        result["status"] = "timeout"
    except ConnectionRefusedError:
        result["status"] = "connection_refused"
    except ssl.SSLError:
        result["status"] = "tls_error"
    except (ConnectionError, OSError):
        result["status"] = "connection_error"
    return result

def _enrich_result(domain, host, port, result):
    extra = _enrichment_defaults()
    caps = result.get("capabilities", "") or ""
    extra["starttls"] = "supported" if "starttls" in caps.lower() else (
        "missing" if port == 143 else "not_applicable"
    )
    if result.get("tls_used"):
        if result.get("tls_version"):
            extra["tls_versions"] = [result["tls_version"]]
        extra.update(_certificate_from_probe(host, port))
    if CFG.get("tls_analysis", True) and port in (993, 143):
        extra["tls_versions"] = sorted(set(extra["tls_versions"]) | set(_probe_tls_versions(host, port)))
    extra["weak_cipher"] = "yes" if any(
        x in (result.get("cipher", "") or "").upper()
        for x in ("RC4", "3DES", "DES-", "NULL", "EXPORT", "MD5", "ANON")
    ) else ""
    extra["tls_grade"] = _security_grade(
        extra["tls_versions"], result.get("cipher", ""), extra["starttls"]
    )
    extra["ip_addresses"] = _resolve_ips(host)
    if extra["ip_addresses"] and CFG.get("geoip_enabled", False):
        extra.update(_geo_lookup(extra["ip_addresses"][0]))

    mapping = CFG.get("protocol_mapping", {})
    if mapping.get("pop3") or mapping.get("smtp"):
        for proto, ports in (("pop3", (110, 995)), ("smtp", (25, 465, 587))):
            if not mapping.get(proto):
                continue
            for p in ports:
                probe = _mail_protocol_probe(host, p, proto)
                if probe["alive"]:
                    extra["protocols"][f"{proto}:{p}"] = probe["status"]
                    extra["protocol_hosts"][f"{proto}:{p}"] = host
    return extra

def test_single_domain(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return {
            "line": line, "direct_working": False, "domain": None,
            "provider": None, "host": None, "port": None, "status": "skipped",
            "auth_mechanisms": [], "tls_used": False, "tls_version": "",
            "cipher": "", "banner": "", "capabilities": ""
        }

    parts = [p.strip() for p in stripped.split("|")]
    domain = (parts[0] if parts and parts[0] else stripped).lower()

    if len(parts) > 1 and parts[1]:
        host = parts[1].lower().rstrip(".")
        if not _valid_hostname(host):
            return {
                "line": line, "direct_working": False, "domain": domain,
                "provider": "Unknown", "host": host, "port": "",
                "status": "invalid_host", "auth_mechanisms": [], "tls_used": False,
                "tls_version": "", "cipher": "", "banner": "", "capabilities": ""
            }
        if len(parts) > 2 and parts[2]:
            try:
                port = int(parts[2])
            except (ValueError, TypeError):
                return {
                    "line": line, "direct_working": False, "domain": domain,
                    "provider": "Unknown", "host": host, "port": parts[2],
                    "status": "invalid_port", "auth_mechanisms": [], "tls_used": False,
                    "tls_version": "", "cipher": "", "banner": "", "capabilities": ""
                }
        else:
            port = 993
        if not 1 <= port <= 65535:
            return {
                "line": line, "direct_working": False, "domain": domain,
                "provider": "Unknown", "host": host, "port": port,
                "status": "invalid_port", "auth_mechanisms": [], "tls_used": False,
                "tls_version": "", "cipher": "", "banner": "", "capabilities": ""
            }
        endpoints = [(host, port)]
    else:
        endpoints = _candidate_endpoints(domain) if CFG.get("auto_discover_hosts", True) else [(domain, 993)]

    best = None
    attempts = CFG["retry_count"] + 1
    for host, port in endpoints:
        provider = _provider_hint(domain, host)
        last = None
        for attempt in range(attempts):
            last = _probe_once(host, port, domain)
            if last["alive"]:
                provider = _provider_hint(domain, host, last["banner"], last["capabilities"])
                status = _classify_imap_result(provider, last["banner"], last["capabilities"])
                auth = _extract_auth_mechanisms(last["capabilities"])
                direct = status in {"imap_reachable_auth_advertised", "imap_reachable"}
                row = {
                    "line": line, "direct_working": direct, "domain": domain,
                    "provider": provider, "host": host, "port": port, "status": status,
                    "auth_mechanisms": auth, "tls_used": last["tls_used"],
                    "tls_version": last["tls_version"], "cipher": last["cipher"],
                    "banner": last["banner"].strip(), "capabilities": last["capabilities"].strip()
                }
                try:
                    row.update(_enrich_result(domain, host, port, last))
                except Exception as ex:
                    dprint(f"Enrichment failed for {host}:{port}: {ex}")
                if best is None or (not best.get("direct_working") and direct):
                    best = row
                if direct:
                    return row
                break
            if attempt < attempts - 1:
                time.sleep(0.15)
        if best is None and last:
            best = {
                "line": line, "direct_working": False, "domain": domain,
                "provider": provider, "host": host, "port": port,
                "status": last.get("error_type") or "connection_error",
                "auth_mechanisms": [], "tls_used": last.get("tls_used", False),
                "tls_version": last.get("tls_version", ""), "cipher": last.get("cipher", ""),
                "banner": last.get("banner", "").strip(),
                "capabilities": last.get("capabilities", "").strip()
            }

    return best or {
        "line": line, "direct_working": False, "domain": domain, "provider": "Unknown",
        "host": "", "port": "", "status": "no_candidates", "auth_mechanisms": [],
        "tls_used": False, "tls_version": "", "cipher": "", "banner": "", "capabilities": ""
    }

def _discord_webhook(message, title=None, fields=None):
    if not CFG.get("webhook_enabled") or not CFG.get("webhook_url") or not CFG.get("webhook_on_completion", True):
        return False
    payload = {"content": message[:1900]}
    if title or fields:
        payload["embeds"] = [{
            "title": (title or "iMapTool")[:256],
            "fields": [
                {"name": str(n)[:256], "value": str(v)[:1024], "inline": True}
                for n, v in (fields or [])[:25]
            ]
        }]
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            CFG["webhook_url"], data=body,
            headers={"Content-Type": "application/json", "User-Agent": f"iMapTool/{APP_VERSION}"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            return 200 <= getattr(response, "status", 204) < 300
    except Exception as ex:
        dprint(f"Webhook delivery failed: {ex}")
        return False

def _generate_html_report(csv_path, html_path=None, dashboard_path=None):
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))
    html_path = Path(html_path or CFG.get("html_report_file", "results/imap_report.html"))
    with csv_path.open("r", newline="", encoding="utf-8", errors="replace") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>iMapTool Offline Report</title>
<style>
:root{{--bg:#09111f;--panel:#101a2b;--line:#263650;--text:#e9f1fb;--muted:#91a4bd;--accent:#69d7ff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px system-ui,-apple-system,Segoe UI,sans-serif}}
.wrap{{max-width:1500px;margin:auto;padding:28px}} .hero,.card,.chart,.table{{background:var(--panel);border:1px solid var(--line);border-radius:14px}}
.hero{{padding:20px}} h1{{margin:0;font-size:24px}} .muted{{color:var(--muted)}}
.cards,.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:14px 0}}
.card,.chart{{padding:14px}} .value{{font-size:24px;font-weight:700}} .controls{{display:flex;gap:9px;flex-wrap:wrap;margin:14px 0}}
input,select,button{{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:9px;padding:9px}}
button{{cursor:pointer}} .table{{overflow:auto}} table{{width:100%;border-collapse:collapse;min-width:1200px}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
th{{position:sticky;top:0;background:#15243a;cursor:pointer}} tr:hover td{{background:#17243a}}
.bar{{display:flex;gap:8px;align-items:center;margin:7px 0}} .bar label{{width:130px;overflow:hidden;text-overflow:ellipsis}}
.track{{height:9px;flex:1;background:#22314b;border-radius:9px}} .fill{{height:100%;background:var(--accent);border-radius:9px}}
.pager{{display:flex;justify-content:space-between;padding:12px}}
</style></head><body><div class="wrap">
<div class="hero"><h1>╭─── iMapTool Offline Report ────────────────────────────╮</h1>
<div class="muted">│ Unified IMAP Operational Suite · standalone local report │</div></div>
<div id="cards" class="cards"></div>
<div class="charts"><div class="chart"><b>TLS Version Distribution</b><div id="tls"></div></div>
<div class="chart"><b>Authentication Mechanisms</b><div id="auth"></div></div>
<div class="chart"><b>Host Distribution</b><div id="host"></div></div></div>
<div class="controls"><input id="q" placeholder="Search all fields…" style="min-width:320px">
<select id="status"><option value="">All statuses</option></select>
<select id="provider"><option value="">All providers</option></select>
<select id="grade"><option value="">All TLS grades</option></select></div>
<div class="table"><table><thead id="head"></thead><tbody id="body"></tbody></table>
<div class="pager"><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button></div></div>
</div>
<script>
const rows={payload}; let filtered=rows.slice(), page=0, pageSize=100, sortKey="", asc=true;
const cols=Object.keys(rows[0]||{{}});
function esc(v){{return String(v??"").replace(/[&<>"']/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]))}}
function dist(key){{const m={{}}; rows.forEach(r=>String(r[key]||"").split(/[,;]/).map(x=>x.trim()).filter(Boolean).forEach(x=>m[x]=(m[x]||0)+1)); return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,12)}}
function draw(id,data){{const e=document.getElementById(id),max=data[0]?.[1]||1;e.innerHTML=data.length?data.map(([k,v])=>`<div class="bar"><label title="${{esc(k)}}">${{esc(k)}}</label><div class="track"><div class="fill" style="width:${{v/max*100}}%"></div></div><b>${{v}}</b></div>`).join(""):"<span class='muted'>No data</span>"}}
function charts(){{draw("tls",dist("tls_versions"));draw("auth",dist("auth_mechanisms"));draw("host",dist("host"))}}
function setup(){{[["status","status"],["provider","provider"],["grade","tls_grade"]].forEach(([id,key])=>[...new Set(rows.map(r=>r[key]).filter(Boolean))].sort().forEach(v=>document.getElementById(id).insertAdjacentHTML("beforeend",`<option>${{esc(v)}}</option>`)))}}
function apply(){{const q=document.getElementById("q").value.toLowerCase(),s=document.getElementById("status").value,p=document.getElementById("provider").value,g=document.getElementById("grade").value;filtered=rows.filter(r=>(!q||Object.values(r).some(v=>String(v).toLowerCase().includes(q)))&&(!s||r.status===s)&&(!p||r.provider===p)&&(!g||r.tls_grade===g));page=0;render()}}
function sortBy(k){{if(sortKey===k)asc=!asc;else{{sortKey=k;asc=true}}filtered.sort((a,b)=>String(a[k]||"").localeCompare(String(b[k]||""),undefined,{{numeric:true}})*(asc?1:-1));render()}}
function render(){{const pages=Math.max(1,Math.ceil(filtered.length/pageSize));page=Math.max(0,Math.min(page,pages-1));const data=filtered.slice(page*pageSize,page*pageSize+pageSize);document.getElementById("head").innerHTML="<tr>"+cols.map(c=>`<th onclick="sortBy('${{c}}')">${{esc(c)}}</th>`).join("")+"</tr>";document.getElementById("body").innerHTML=data.map(r=>"<tr>"+cols.map(c=>`<td>${{esc(r[c])}}</td>`).join("")+"</tr>").join("");document.getElementById("page").textContent=`Page ${{page+1}} / ${{pages}} · ${{filtered.length.toLocaleString()}} rows`;document.getElementById("prev").disabled=page===0;document.getElementById("next").disabled=page>=pages-1}}
function cards(){{const direct=rows.filter(r=>r.direct_working==="yes").length,legacy=rows.filter(r=>r.tls_grade==="Legacy").length;document.getElementById("cards").innerHTML=[["Total",rows.length],["Direct IMAP",direct],["TLS rows",rows.filter(r=>r.tls_used==="yes").length],["Legacy TLS",legacy]].map(x=>`<div class="card"><div class="muted">${{x[0]}}</div><div class="value">${{Number(x[1]).toLocaleString()}}</div></div>`).join("")}}
document.getElementById("q").oninput=apply;["status","provider","grade"].forEach(id=>document.getElementById(id).onchange=apply);document.getElementById("prev").onclick=()=>{{page--;render()}};document.getElementById("next").onclick=()=>{{page++;render()}};cards();setup();charts();render();
</script></body></html>"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return html_path

def _send_run_webhook(tool, run_dir, fields):
    _discord_webhook(
        f"iMapTool {APP_VERSION} · {tool} completed",
        title=f"iMapTool · {tool}",
        fields=fields + [("Run directory", str(run_dir))]
    )

def run_self_test():
    """Run fast offline checks for configuration, parsing and UI helpers."""
    _clear_screen()
    _print_banner(MAIN_BANNER, "Self Test")
    tests = []
    tests.append(("Configuration validation", True))
    tests.append(("Progress bar bounds", len(_progress_bar(0, 10)) == 28 and len(_progress_bar(10, 10)) == 28))
    tests.append(("Hostname validation", _valid_hostname("imap.example.com") and not _valid_hostname("bad host")))
    tests.append(("Provider fingerprint", _provider_hint("example.com", "imap.gmail.com") == "Google"))
    tests.append(("Provider false-positive guard", _provider_hint("mygoogle.com", "imap.mygoogle.com") == "Unknown"))
    tests.append(("Auth parsing", set(_extract_auth_mechanisms("* CAPABILITY AUTH=LOGIN AUTH=PLAIN")) == {"LOGIN", "PLAIN"}))
    tests.append(("IMAP classification", _classify_imap_result("Unknown", "* OK Ready", "* CAPABILITY IMAP4rev1 AUTH=LOGIN") == "imap_reachable_auth_advertised"))
    tests.append(("Invalid port handling", test_single_domain("example.com | imap.example.com | 70000")["status"] == "invalid_port"))
    passed = sum(ok for _, ok in tests)
    for name, ok in tests:
        print(f"  {'[PASS]' if ok else '[FAIL]'} {name}")
    print(f"\n\033[36mSelf test: {passed}/{len(tests)} checks passed.\033[0m")
    _pause()


def _save_config():
    path = Path("config.json")
    tmp = path.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(CFG, f, indent=4)
            f.write("\n")
        os.replace(tmp, path)
        return True, ""
    except OSError as ex:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False, str(ex)


def _apply_runtime_config():
    global HOST_PREFIXES, TARGET_PORTS, EXCLUDED_DOMAINS
    global USE_UNICODE, USE_COLOR, PROGRESS_REFRESH_SECONDS, DEBUG
    HOST_PREFIXES = list(CFG.get("prefixes", HOST_PREFIXES))
    TARGET_PORTS = list(CFG.get("ports", TARGET_PORTS))
    EXCLUDED_DOMAINS = set(CFG.get("excluded_domains", list(EXCLUDED_DOMAINS)))
    USE_UNICODE = bool(CFG.get("use_unicode", True))
    USE_COLOR = bool(CFG.get("use_color", True))
    PROGRESS_REFRESH_SECONDS = float(CFG.get("progress_refresh_seconds", 0.25))
    DEBUG = bool(CFG.get("debug", False))
    _refresh_output_mode()


def _set_setting(key, value):
    old = CFG.get(key)
    CFG[key] = value
    try:
        _validate_config(CFG)
    except ValueError as ex:
        CFG[key] = old
        print(f"\033[31m[ERROR]\033[0m {ex}")
        _pause()
        return False
    ok, error = _save_config()
    _apply_runtime_config()
    if not ok:
        print(f"\033[33m[WARN]\033[0m Setting changed for this session but could not be saved: {error}")
    else:
        print("\033[32m[DONE]\033[0m Setting saved.")
    return True


def _ask_int(label, current, minimum, maximum):
    raw = input(f"\033[36m{label}\033[0m [{current}] > ").strip()
    if not raw:
        return current
    try:
        value = int(raw)
    except ValueError:
        print("\033[31m[ERROR]\033[0m Enter a whole number.")
        _pause()
        return current
    if not minimum <= value <= maximum:
        print(f"\033[31m[ERROR]\033[0m Enter a value from {minimum} to {maximum}.")
        _pause()
        return current
    return value


def _ask_float(label, current, minimum, maximum):
    raw = input(f"\033[36m{label}\033[0m [{current}] > ").strip()
    if not raw:
        return current
    try:
        value = float(raw)
    except ValueError:
        print("\033[31m[ERROR]\033[0m Enter a number.")
        _pause()
        return current
    if not minimum <= value <= maximum:
        print(f"\033[31m[ERROR]\033[0m Enter a value from {minimum} to {maximum}.")
        _pause()
        return current
    return value


def _ask_bool(label, current):
    state = "ON" if current else "OFF"
    raw = input(f"\033[36m{label}\033[0m [{state}] (y/n) > ").strip().lower()
    if not raw:
        return current
    if raw in {"y", "yes", "on", "1"}:
        return True
    if raw in {"n", "no", "off", "0"}:
        return False
    print("\033[31m[ERROR]\033[0m Enter y or n.")
    _pause()
    return current


def choose_theme(return_to="main"):
    while True:
        _clear_screen()
        _print_banner(MAIN_BANNER, "Display Themes")
        _section("THEME SELECTION")
        print()
        themes = [
            ("1", "Classic", "Original magenta / cyan"),
            ("2", "Midnight", "Cool blue / cyan, low visual noise"),
            ("3", "Soft", "Neutral, gentle contrast"),
            ("4", "Graphite", "Monochrome, restrained accents"),
            ("5", "Ocean", "Deep blue / cyan technical look"),
            ("6", "Aurora", "Fresh green / cyan with softer highlights"),
        ]
        for key, name, desc in themes:
            marker = "Current" if CFG["theme"] == name.lower() else ""
            _menu_row(key, f"{name} {marker}".strip(), desc)
        _menu_row("0", "Back", "Return to the previous menu.")
        print(f"\n\033[36mCurrent theme:\033[0m {CFG['theme'].title()}")
        choice = input("\033[36mSelect theme [1-6] > \033[0m").strip()
        selected = {"1": "classic", "2": "midnight", "3": "soft", "4": "graphite", "5": "ocean", "6": "aurora"}.get(choice)
        if choice == "0":
            return
        if not selected:
            print("\033[31m[ERROR]\033[0m Invalid theme selection.")
            time.sleep(0.7)
            continue
        CFG["theme"] = selected
        _apply_runtime_config()
        ok, error = _save_config()
        if ok:
            print(f"\n\033[32m[DONE]\033[0m Theme changed to \033[36m{selected.title()}\033[0m.")
        else:
            print(f"\n\033[33m[WARN]\033[0m Theme changed for this session but could not be saved: {error}")
        _pause()
        return


def _settings_display():
    _clear_screen(); _print_banner(MAIN_BANNER, "Display Settings")
    _section("DISPLAY")
    print(f"  Theme:                 {CFG['theme'].title()}")
    print(f"  Colour output:         {'On' if CFG['use_color'] else 'Off'}")
    print(f"  Unicode UI:            {'On' if CFG['use_unicode'] else 'Off'}\n")
    _menu_row("1", "Change theme")
    _menu_row("2", "Colour output")
    _menu_row("3", "Unicode UI")
    _menu_row("0", "Back")
    choice = input("\n\033[36mSelect option > \033[0m").strip()
    if choice == "1": choose_theme(return_to="settings")
    elif choice == "2": _set_setting("use_color", _ask_bool("Colour output", CFG["use_color"]))
    elif choice == "3": _set_setting("use_unicode", _ask_bool("Unicode UI", CFG["use_unicode"]))


def _settings_performance():
    _clear_screen(); _print_banner(MAIN_BANNER, "Performance Settings")
    _section("PERFORMANCE")
    print("  Changes apply to the next run.\n")
    _menu_row("1", "Ping workers", str(CFG["ping_workers"]))
    _menu_row("2", "Scraper workers", str(CFG["scraper_workers"]))
    _menu_row("3", "Request timeout", f"{CFG['timeout_seconds']}s")
    _menu_row("4", "Ping retry count", str(CFG["retry_count"]))
    _menu_row("5", "Progress refresh", f"{CFG['progress_refresh_seconds']}s")
    _menu_row("6", "In-flight multiplier", str(CFG["max_in_flight_multiplier"]))
    _menu_row("0", "Back")
    choice = input("\n\033[36mSelect option > \033[0m").strip()
    if choice == "1": _set_setting("ping_workers", _ask_int("Ping workers", CFG["ping_workers"], 1, 200))
    elif choice == "2": _set_setting("scraper_workers", _ask_int("Scraper workers", CFG["scraper_workers"], 1, 200))
    elif choice == "3": _set_setting("timeout_seconds", _ask_float("Request timeout (seconds)", CFG["timeout_seconds"], 0.1, 120.0))
    elif choice == "4": _set_setting("retry_count", _ask_int("Ping retries", CFG["retry_count"], 0, 5))
    elif choice == "5": _set_setting("progress_refresh_seconds", _ask_float("Progress refresh (seconds)", CFG["progress_refresh_seconds"], 0.05, 5.0))
    elif choice == "6": _set_setting("max_in_flight_multiplier", _ask_int("In-flight multiplier", CFG["max_in_flight_multiplier"], 1, 4))


def _settings_behaviour():
    _clear_screen(); _print_banner(MAIN_BANNER, "Behaviour Settings")
    _section("RUN BEHAVIOUR")
    print()
    _menu_row("1", "Resume interrupted Ping runs", "On" if CFG["resume_enabled"] else "Off")
    _menu_row("2", "Automatic IMAP host discovery", "On" if CFG.get("auto_discover_hosts", True) else "Off")
    _menu_row("3", "Purge in-place backups", "On" if CFG.get("purge_backup", True) else "Off")
    _menu_row("0", "Back")
    choice = input("\n\033[36mSelect option > \033[0m").strip()
    if choice == "1": _set_setting("resume_enabled", _ask_bool("Resume interrupted Ping runs", CFG["resume_enabled"]))
    elif choice == "2": _set_setting("auto_discover_hosts", _ask_bool("Automatic IMAP host discovery", CFG.get("auto_discover_hosts", True)))
    elif choice == "3": _set_setting("purge_backup", _ask_bool("Purge in-place backups", CFG.get("purge_backup", True)))


def _settings_files():
    _clear_screen(); _print_banner(MAIN_BANNER, "File Settings")
    _section("PATHS")
    print("  These paths are used for future runs.\n")
    items=[("1","Ping input file","ping_input_file"),("2","Scraper input file","scraper_input_file"),("3","Scraper output file","scraper_output_file"),("4","Results directory","results_dir")]
    for key,label,cfg_key in items: _menu_row(key,label,str(CFG[cfg_key]))
    _menu_row("0","Back")
    choice=input("\n\033[36mSelect option > \033[0m").strip()
    selected={x[0]:x[2] for x in items}.get(choice)
    if selected:
        value=input(f"\033[36mNew value\033[0m [{CFG[selected]}] > ").strip()
        if value: _set_setting(selected,value)


def show_run_history():
    _clear_screen()
    _print_banner(MAIN_BANNER, "Run History")
    _section("RECENT RUNS")
    root = Path(CFG["results_dir"])
    runs = []
    if root.exists():
        for tool_dir in root.iterdir():
            if not tool_dir.is_dir():
                continue
            for run_dir in tool_dir.iterdir():
                if run_dir.is_dir():
                    runs.append(run_dir)
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        print("  No completed runs found.")
        _pause()
        return
    for idx, run_dir in enumerate(runs[:20], 1):
        detail = run_dir.parent.name
        summary_path = run_dir / "run_summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                totals = summary.get("totals", {})
                total = totals.get("input_entries", totals.get("total_entries", "?"))
                detail = f"{detail} · {total} entries · {float(summary.get('duration_seconds', 0)):.1f}s"
            except (OSError, ValueError, TypeError):
                pass
        _menu_row(str(idx), run_dir.name, detail)
    _menu_row("0", "Back", "Return to the main menu.")
    _pause()


def show_webhook_settings():
    while True:
        _clear_screen()
        _print_banner(MAIN_BANNER, "Webhook")
        _section("DISCORD / WEBHOOK")
        _menu_row("1", "Enable / disable", "Turn completion notifications on or off.")
        _menu_row("2", "Set webhook URL", "Save a Discord-compatible incoming webhook URL.")
        _menu_row("3", "Test webhook", "Send a test notification to the configured channel.")
        _menu_row("4", "Completion notifications", "Control automatic Ping/Purge completion posts.")
        _menu_row("5", "Clear webhook URL", "Remove the saved endpoint from config.json.")
        _menu_row("0", "Back", "Return to Settings.")
        choice = input("\n\033[36mSelect option > \033[0m").strip()
        if choice == "1":
            _set_setting("webhook_enabled", _ask_bool("Webhook enabled", CFG.get("webhook_enabled", False)))
        elif choice == "2":
            raw = input("\033[36mWebhook URL\033[0m > ").strip()
            if raw.startswith("https://"):
                _set_setting("webhook_url", raw)
            else:
                print("\033[31m[ERROR]\033[0m Webhook URL must use HTTPS.")
                _pause()
        elif choice == "3":
            if not CFG.get("webhook_url"):
                print("\033[31m[ERROR]\033[0m Configure a webhook URL first.")
            else:
                ok = _discord_webhook("iMapTool webhook test", title="iMapTool · Webhook Test", fields=[("Status", "Connected")])
                print("\033[32m[DONE]\033[0m Test delivered." if ok else "\033[31m[ERROR]\033[0m Test delivery failed.")
            _pause()
        elif choice == "4":
            _set_setting("webhook_on_completion", _ask_bool("Completion notifications", CFG.get("webhook_on_completion", True)))
        elif choice == "5":
            _set_setting("webhook_url", "")
        elif choice == "0":
            return


def show_analysis_settings():
    while True:
        _clear_screen()
        _print_banner(MAIN_BANNER, "Deep Analysis")
        _section("ANALYSIS FEATURES")
        _menu_row("1", "Certificate analysis", "Inspect expiry, issuer, wildcard and self-signed flags.")
        _menu_row("2", "TLS security analysis", "Check TLS versions and weak cipher indicators.")
        _menu_row("3", "POP3 mapping", "Probe POP3 banner services on 110 and 995.")
        _menu_row("4", "SMTP mapping", "Probe SMTP/Submission banners on 25, 465 and 587.")
        _menu_row("5", "GeoIP / ASN mapping", "Optionally enrich resolved IPs using the configured endpoint.")
        _menu_row("6", "Offline HTML reports", "Generate standalone searchable reports after Ping.")
        _menu_row("0", "Back", "Return to Settings.")
        choice = input("\n\033[36mSelect option > \033[0m").strip()
        if choice == "1": _set_setting("certificate_analysis", _ask_bool("Certificate analysis", CFG.get("certificate_analysis", True)))
        elif choice == "2": _set_setting("tls_analysis", _ask_bool("TLS security analysis", CFG.get("tls_analysis", True)))
        elif choice == "3":
            protocols = copy.deepcopy(CFG.get("protocol_mapping", {"imap": True, "pop3": False, "smtp": False}))
            protocols["pop3"] = _ask_bool("POP3 mapping", protocols.get("pop3", False))
            _set_setting("protocol_mapping", protocols)
        elif choice == "4":
            protocols = copy.deepcopy(CFG.get("protocol_mapping", {"imap": True, "pop3": False, "smtp": False}))
            protocols["smtp"] = _ask_bool("SMTP mapping", protocols.get("smtp", False))
            _set_setting("protocol_mapping", protocols)
        elif choice == "5": _set_setting("geoip_enabled", _ask_bool("GeoIP / ASN mapping", CFG.get("geoip_enabled", False)))
        elif choice == "6": _set_setting("html_report_enabled", _ask_bool("Offline HTML reports", CFG.get("html_report_enabled", True)))
        elif choice == "0": return

def show_settings():
    while True:
        _clear_screen()
        _print_banner(MAIN_BANNER, "Settings")
        _section("APPLICATION SETTINGS")
        _menu_row("1", "Display & Theme", f"Current: {CFG['theme'].title()}")
        _menu_row("2", "Performance", f"Ping {CFG['ping_workers']} / Scraper {CFG['scraper_workers']}")
        _menu_row("3", "Run Behaviour", "Resume, discovery and backups")
        _menu_row("4", "File Paths", f"Results: {CFG['results_dir']}")
        _menu_row("5", "Deep Analysis", "TLS, certificates, POP3, SMTP, GeoIP and HTML")
        _menu_row("6", "Webhook", "Discord-compatible completion notifications")
        _menu_row("7", "Restore Defaults", "Reset all application settings")
        _menu_row("0", "Back", "Return to the main menu.")
        choice = input("\n\033[36mSelect setting group > \033[0m").strip()
        if choice == "1": _settings_display()
        elif choice == "2": _settings_performance()
        elif choice == "3": _settings_behaviour()
        elif choice == "4": _settings_files()
        elif choice == "5": show_analysis_settings()
        elif choice == "6": show_webhook_settings()
        elif choice == "7":
            confirm = input("\033[33mRestore all settings to defaults? [y/N] > \033[0m").strip().lower()
            if confirm in {"y", "yes"}:
                CFG.clear(); CFG.update(copy.deepcopy(DEFAULT_CONFIG)); _validate_config(CFG); _apply_runtime_config()
                ok, error = _save_config()
                print("\033[32m[DONE]\033[0m Defaults restored." if ok else f"\033[33m[WARN]\033[0m Defaults applied for this session: {error}")
                _pause()
        elif choice == "0": return

def show_dashboard():
    path = _latest_ping_dashboard()
    if path is None:
        print("\033[33m[INFO]\033[0m No dashboard exists yet. Run iMap Ping first.")
        _pause()
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as ex:
        print(f"\033[31m[ERROR]\033[0m Could not read dashboard: {ex}")
        _pause()
        return

    _clear_screen()
    _print_banner(MAIN_BANNER, "iMapTool")
    print("\033[36mIMAP DISCOVERY DASHBOARD\033[0m\n")
    print(f"Latest run:         {path.parent.name}")
    print(f"Total entries:      {data.get('total_entries', 0):,}")
    print(f"Direct IMAP:        {data.get('direct_working', 0):,}")
    print(f"Hosted providers:   {data.get('hosted_provider', 0):,}")
    print(f"Auth restricted:    {data.get('auth_restricted', 0):,}")
    print(f"Network failures:   {data.get('network_failures', 0):,}")
    print(f"Duration:           {data.get('duration_seconds', 0):.1f}s\n")
    print("\033[36mAll classifications:\033[0m")
    for name, count in sorted(
        data.get("classifications", {}).items(),
        key=lambda x: (-x[1], x[0])
    ):
        print(f"  {name:30} {count:,}")
    _pause()

# ==================== MAIN MENU ROUTER ====================
def main_menu():
    while True:
        _clear_screen()
        _print_banner(MAIN_BANNER, "iMap Tool")
        print(f"\033[36mVersion\033[0m  {APP_VERSION:<8}  \033[36mTheme\033[0m  {CFG['theme'].title()}\n")
        if DEBUG:
            print("\033[33m[!] DEBUG MODE ACTIVE\033[0m\n")
        _section("OPERATIONS")
        _menu_row("1", "iMap Scraper", "Discover IMAP hosts")
        _menu_row("2", "iMap Purge", "Clean and normalize lists")
        _menu_row("3", "iMap Ping", "Inspect IMAP services")
        print()
        _section("RESULTS & TOOLS")
        _menu_row("4", "Ping Dashboard", "View latest results")
        _menu_row("5", "Display Themes", "Change application appearance")
        _menu_row("6", "Run History", "Review previous runs")
        _menu_row("8", "Self Test", "Check local components")
        print()
        _section("SETTINGS")
        _menu_row("7", "Application Settings", "Configure the suite")
        print()
        _menu_row("0", "Exit", "Close iMap Tool")
        choice=input("\n\033[36mSelect option > \033[0m").strip()
        if choice=="1": run_scraper()
        elif choice=="2": run_purge()
        elif choice=="3": run_ping()
        elif choice=="4": show_dashboard()
        elif choice=="5": choose_theme(return_to="main")
        elif choice=="6": show_run_history()
        elif choice=="7": show_settings()
        elif choice=="8": run_self_test()
        elif choice=="0":
            _clear_screen(); _print_banner(MAIN_BANNER,"iMap Tool"); print("\033[36miMap Tool closed.\033[0m"); break
        else:
            print("\033[31m[ERROR]\033[0m Invalid option."); time.sleep(0.6)


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(
            description="iMapTool 2.5.0 — authorized mail-service discovery and reporting."
        )
        sub = parser.add_subparsers(dest="command")

        p = sub.add_parser("ping", help="Inspect IMAP services")
        p.add_argument("--input", default=CFG["ping_input_file"])
        p.add_argument("--out-working", default=None)
        p.add_argument("--out-dead", default=None)
        p.add_argument("--sample-size", type=int)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--protocols", default=None, help="Comma-separated protocols: imap,pop3,smtp")
        p.add_argument("--geoip", action="store_true", help="Enable optional IP/ASN/GeoIP enrichment")
        p.add_argument("--no-certificate-analysis", action="store_true")
        p.add_argument("--no-tls-analysis", action="store_true")
        p.add_argument("--no-html", action="store_true", help="Skip automatic HTML report generation")

        p = sub.add_parser("scraper", help="Discover conventional IMAP hosts")
        p.add_argument("--input", default=CFG["scraper_input_file"])
        p.add_argument("--output", default=None)
        p.add_argument("--sample-size", type=int)

        p = sub.add_parser("purge", help="Clean a domain list non-interactively")
        p.add_argument("--input", required=True)
        p.add_argument("--output", required=True)
        p.add_argument("--mode", choices=["1", "2", "3", "4", "5"], default="5")

        p = sub.add_parser("report", help="Generate a standalone offline HTML report")
        p.add_argument("--input", required=True)
        p.add_argument("--output", default=None)
        p.add_argument("--dashboard", default=None)

        sub.add_parser("dashboard", help="Display the latest Ping dashboard")
        sub.add_parser("history", help="Display recent run history")
        sub.add_parser("self-test", help="Run offline self tests")

        p = sub.add_parser("theme", help="Set application theme")
        p.add_argument("name", choices=["classic", "midnight", "soft", "graphite", "ocean", "aurora"])
        p = sub.add_parser("settings", help="Print or change application settings")
        p.add_argument("action", nargs="?", choices=["show", "set"], default="show")
        p.add_argument("key", nargs="?")
        p.add_argument("value", nargs="?")
        sub.add_parser("webhook-test", help="Send a Discord webhook test message")

        args = parser.parse_args()
        CLI_MODE = bool(args.command)

        if not args.command:
            main_menu()
        elif args.command == "ping":
            if args.sample_size is not None and args.sample_size < 1:
                parser.error("--sample-size must be at least 1")
            if args.protocols is not None:
                selected = {x.strip().lower() for x in args.protocols.split(",") if x.strip()}
                unknown = selected - {"imap", "pop3", "smtp"}
                if unknown:
                    parser.error("unknown protocol(s): " + ", ".join(sorted(unknown)))
                CFG["protocol_mapping"] = {
                    "imap": "imap" in selected,
                    "pop3": "pop3" in selected,
                    "smtp": "smtp" in selected,
                }
            if args.geoip:
                CFG["geoip_enabled"] = True
            if args.no_certificate_analysis:
                CFG["certificate_analysis"] = False
            if args.no_tls_analysis:
                CFG["tls_analysis"] = False
            if args.no_html:
                CFG["html_report_enabled"] = False
            run_ping(
                domains_file=args.input,
                output_working=args.out_working,
                output_dead=args.out_dead,
                sample_size=args.sample_size,
                dry_run=args.dry_run,
            )
        elif args.command == "scraper":
            if args.sample_size is not None and args.sample_size < 1:
                parser.error("--sample-size must be at least 1")
            run_scraper(
                input_file=args.input,
                output_file=args.output,
                sample_size=args.sample_size,
            )
        elif args.command == "purge":
            run_purge(
                input_file=args.input,
                output_file=args.output,
                mode=args.mode,
                interactive=False,
            )
        elif args.command == "report":
            path = _generate_html_report(args.input, args.output, args.dashboard)
            print(f"\033[32m[DONE]\033[0m Offline report: {path}")
        elif args.command == "dashboard":
            show_dashboard()
        elif args.command == "history":
            show_run_history()
        elif args.command == "self-test":
            run_self_test()
        elif args.command == "theme":
            CFG["theme"] = args.name
            _validate_config(CFG)
            _apply_runtime_config()
            ok, error = _save_config()
            print(
                f"\033[32m[DONE]\033[0m Theme set to {args.name.title()}"
                if ok else f"\033[31m[ERROR]\033[0m {error}"
            )
        elif args.command == "settings":
            if args.action == "set":
                if not args.key or args.value is None:
                    parser.error("settings set requires KEY VALUE")
                if args.key not in CFG:
                    parser.error(f"unknown setting: {args.key}")
                try:
                    value = json.loads(args.value)
                except json.JSONDecodeError:
                    value = args.value
                old_value = CFG.get(args.key)
                CFG[args.key] = value
                try:
                    _validate_config(CFG)
                except ValueError as ex:
                    CFG[args.key] = old_value
                    parser.error(str(ex))
                _apply_runtime_config()
                ok, error = _save_config()
                if not ok:
                    parser.error(error)
                print(f"\\033[32m[DONE]\\033[0m Setting saved: {args.key}")
            else:
                for key in sorted(CFG):
                    value = "<configured>" if key == "webhook_url" and CFG[key] else CFG[key]
                    print(f"{key}={json.dumps(value, ensure_ascii=False)}")
        elif args.command == "webhook-test":
            if not CFG.get("webhook_enabled") or not CFG.get("webhook_url"):
                parser.error("webhook is not enabled or no webhook_url is configured")
            if not _discord_webhook(
                "iMapTool webhook test",
                title="iMapTool · Webhook Test",
                fields=[("Status", "Connected")]
            ):
                parser.error("webhook delivery failed")
            print("\\033[32m[DONE]\\033[0m Webhook test delivered.")
    except KeyboardInterrupt:
        print("\n\033[31mOperation cancelled by user.\033[0m")
