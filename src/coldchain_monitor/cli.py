"""Command-line interface: ``coldchain generate | forecast | evaluate | serve``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from coldchain_monitor import __version__
from coldchain_monitor.data import read_csv, synthetic_log, write_csv
from coldchain_monitor.evaluation import evaluate, format_table
from coldchain_monitor.service import forecast_summary
from coldchain_monitor.warning import DEFAULT_LIMIT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coldchain",
        description="Forecasting and early warning for milk cold-storage temperature.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a synthetic temperature log to CSV")
    gen.add_argument("output", help="path of the CSV file to create")
    gen.add_argument("--hours", type=float, default=168.0, help="length of the log (default 168)")
    gen.add_argument("--seed", type=int, default=0)
    gen.add_argument("--quantization", type=float, default=0.5, help="sensor step, °C")

    fc = sub.add_parser("forecast", help="forecast the next hours from the end of a log")
    fc.add_argument("input", help="CSV with a temperature_c column on a 5-minute grid")
    fc.add_argument("--hours", type=int, default=3, help="forecast horizon (default 3)")
    fc.add_argument("--limit", type=float, default=DEFAULT_LIMIT, help="excursion limit, °C")

    ev = sub.add_parser("evaluate", help="compare the methods on held-out logs")
    ev.add_argument("--calibration", nargs="+", required=True, metavar="CSV",
                    help="logs used to calibrate the alarm thresholds")
    ev.add_argument("--test", nargs="+", required=True, metavar="CSV",
                    help="held-out logs on which the metrics are reported")
    ev.add_argument("--horizons", nargs="+", type=int, default=[1, 3, 6], metavar="H")
    ev.add_argument("--limit", type=float, default=DEFAULT_LIMIT, help="excursion limit, °C")

    srv = sub.add_parser("serve", help="run the REST service (GET /health, GET|POST /forecast)")
    srv.add_argument("--host", default="127.0.0.1", help="interface to bind (0.0.0.0 in Docker)")
    srv.add_argument("--port", type=int, default=8000)
    return parser


def _cmd_generate(args: argparse.Namespace) -> int:
    log = synthetic_log(hours=args.hours, seed=args.seed, quantization=args.quantization)
    path = write_csv(log, args.output)
    print(f"{len(log)} readings ({log.hours:.0f} h) written to {path}")
    return 0


def _cmd_forecast(args: argparse.Namespace) -> int:
    log = read_csv(args.input)
    r = forecast_summary(log.temperature, args.hours, args.limit)
    print(f"Log {log.name}: {r.readings} readings, latest {r.latest:.2f} °C")
    print(f"Forecast for +{r.hours} h:")
    print(f"  Persistence     {r.persistence:6.2f} °C")
    print(f"  Moving average  {r.moving_average:6.2f} °C")
    print(f"  Linear trend    {r.linear_trend:6.2f} °C")
    print(f"  ARIMA(5,1,0)    {r.arima:6.2f} °C (highest on the way: {r.arima_max:.2f} °C)")
    messages = {
        "excursion": f"EXCURSION, the latest reading is above {r.limit:g} °C",
        "warning": f"WARNING, ARIMA expects more than {r.limit:g} °C within the horizon",
        "ok": f"ok, no excursion above {r.limit:g} °C expected by ARIMA",
    }
    print(f"Status: {messages[r.status]}")
    print(f"Tier 2 trigger: {'active (volatile signal)' if r.tier2_active else 'inactive'}")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    calibration = [read_csv(path) for path in args.calibration]
    test = [read_csv(path) for path in args.test]
    rows = evaluate(calibration, test, args.horizons, args.limit)
    print(format_table(rows))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from coldchain_monitor.server import serve

    serve(args.host, args.port)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "generate": _cmd_generate,
        "forecast": _cmd_forecast,
        "evaluate": _cmd_evaluate,
        "serve": _cmd_serve,
    }
    try:
        return handlers[args.command](args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
