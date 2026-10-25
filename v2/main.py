"""Job-bot Version 2.0 Central CLI Dispatcher."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from v2.core.database import (
    get_database_stats,
    init_db,
    migrate_career_sources_from_v1,
)


def cmd_migrate(args: argparse.Namespace) -> None:
    """Migrate career sources from v1 jobs.db to v2 jobs_v2.db."""
    print("=" * 60)
    print("[MIGRATE] Running Migration from v1 to v2 Database...")
    print("=" * 60)
    count = migrate_career_sources_from_v1()
    print(f"[OK] Successfully migrated {count} career source(s) into jobs_v2.db.\n")


def cmd_stats(args: argparse.Namespace) -> None:
    """Display metrics from centralized jobs_v2.db."""
    stats = get_database_stats()
    print("\n" + "=" * 60)
    print("[STATS] JOB-BOT VERSION 2.0 DATABASE METRICS")
    print("=" * 60)
    print(f" Career Sources Total  : {stats['career_sources_total']}")
    print(f" Career Sources Active : {stats['career_sources_active']}")
    print(f" Total Jobs in DB      : {stats['jobs_total']}")
    print("-" * 60)
    print(" Jobs by Pipeline:")
    for pipeline, cnt in stats["jobs_by_pipeline"].items():
        print(f"   * {pipeline:<15} : {cnt}")
    print("-" * 60)
    print(" Jobs by Status:")
    for status, cnt in stats["jobs_by_status"].items():
        print(f"   * {status:<15} : {cnt}")
    if stats["jobs_by_discard_reason"]:
        print("-" * 60)
        print(" Discard Reasons:")
        for reason, cnt in stats["jobs_by_discard_reason"].items():
            print(f"   * {reason:<25} : {cnt}")
    print("=" * 60 + "\n")


def cmd_telegram(args: argparse.Namespace) -> None:
    """Handle Telegram flow commands."""
    subcmd = args.telegram_action

    if subcmd == "collect":
        from v2.flows.telegram.collector import run

        run(limit=args.limit)
    elif subcmd == "validate":
        from v2.flows.telegram.validator import run

        run(limit=args.limit)
    elif subcmd == "linkedin":
        from v2.flows.telegram.linkedin import run

        run(limit=args.limit)
    elif subcmd == "open":
        from v2.flows.telegram.reviewer import run

        run(limit=args.limit)
    else:
        print(f"Unknown telegram action: {subcmd}")


def cmd_careers(args: argparse.Namespace) -> None:
    """Handle Career flow commands."""
    subcmd = args.careers_action

    if subcmd == "import":
        from v2.flows.careers.importer import import_sources_from_json

        import_sources_from_json(args.file)
    elif subcmd == "detect-apis":
        from v2.flows.careers.api_detector import run

        run(limit=args.limit)
    elif subcmd == "scan":
        from v2.flows.careers.scanner import run

        run(platform=args.platform)
    elif subcmd == "validate":
        from v2.flows.careers.validator import run

        run(limit=args.limit)
    elif subcmd == "open":
        from v2.flows.careers.reviewer import run

        run(limit=args.limit)
    else:
        print(f"Unknown careers action: {subcmd}")


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Launch embedded web dashboard server."""
    from v2.dashboard.server import run_server

    run_server(port=args.port, open_browser=not args.no_browser)


def main() -> None:
    """CLI Entry point."""
    init_db()

    parser = argparse.ArgumentParser(
        prog="python v2/main.py",
        description="Job-bot Version 2.0 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Migrate
    sub_migrate = subparsers.add_parser(
        "migrate", help="Migrate career sources from v1 jobs.db"
    )
    sub_migrate.set_defaults(func=cmd_migrate)

    # 2. Stats
    sub_stats = subparsers.add_parser(
        "stats", help="Display centralized database metrics"
    )
    sub_stats.set_defaults(func=cmd_stats)

    # 3. Telegram flow
    sub_telegram = subparsers.add_parser(
        "telegram", help="Telegram & LinkedIn pipeline"
    )
    telegram_subs = sub_telegram.add_subparsers(dest="telegram_action", required=True)

    tg_collect = telegram_subs.add_parser(
        "collect", help="Harvest messages from Telegram channel"
    )
    tg_collect.add_argument(
        "--limit", type=int, default=500, help="Max messages to scan"
    )

    tg_val = telegram_subs.add_parser(
        "validate", help="Validate pending Telegram jobs (MeuPadrinho)"
    )
    tg_val.add_argument("--limit", type=int, default=500, help="Max jobs to validate")

    tg_li = telegram_subs.add_parser(
        "linkedin", help="Check LinkedIn application links, active status, and work mode"
    )
    tg_li.add_argument("--limit", type=int, default=100, help="Max jobs to check")

    tg_open = telegram_subs.add_parser(
        "open", help="Open Telegram jobs in Chrome"
    )
    tg_open.add_argument("--limit", type=int, default=None, help="Max jobs to open")

    sub_telegram.set_defaults(func=cmd_telegram)

    # 4. Careers flow
    sub_careers = subparsers.add_parser("careers", help="Company career pages pipeline")
    careers_subs = sub_careers.add_subparsers(dest="careers_action", required=True)

    c_import = careers_subs.add_parser(
        "import", help="Import company sources from JSON file"
    )
    c_import.add_argument("file", help="Path to JSON file")

    c_detect = careers_subs.add_parser(
        "detect-apis", help="Sniff network API endpoints"
    )
    c_detect.add_argument("--limit", type=int, default=500, help="Max sources to check")

    c_scan = careers_subs.add_parser(
        "scan", help="Scan career pages using platform adapters"
    )
    c_scan.add_argument(
        "--platform", choices=["search_all", "inhire", "gupy"], default="search_all"
    )

    c_val = careers_subs.add_parser(
        "validate", help="Validate career jobs via Ollama & page scraper"
    )
    c_val.add_argument("--limit", type=int, default=500, help="Max jobs to validate")

    c_open = careers_subs.add_parser("open", help="Open eligible career jobs in Chrome")
    c_open.add_argument("--limit", type=int, default=None, help="Max jobs to open")

    sub_careers.set_defaults(func=cmd_careers)

    # 5. Dashboard
    sub_dashboard = subparsers.add_parser(
        "dashboard", help="Start local Web UI dashboard"
    )
    sub_dashboard.add_argument(
        "--port", type=int, default=8766, help="Port to listen on"
    )
    sub_dashboard.add_argument(
        "--no-browser", action="store_true", help="Do not auto-open browser"
    )
    sub_dashboard.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
