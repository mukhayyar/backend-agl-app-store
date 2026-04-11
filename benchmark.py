#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║     AGL App Store — Comprehensive Benchmark Suite         ║
║     gRPC vs HTTP · Concurrency · Latency · Throughput     ║
╚═══════════════════════════════════════════════════════════╝

Usage:
  python3 benchmark.py              # full suite
  python3 benchmark.py --quick      # fast (25 reps per test)
  python3 benchmark.py --grpc-only  # gRPC vs HTTP comparison only
  python3 benchmark.py --load       # concurrency stress test only
  python3 benchmark.py --db         # database benchmark only
  python3 benchmark.py --export     # export results to benchmark_results.json
"""

import sys
import os
import time
import json
import math
import asyncio
import argparse
import threading
import statistics
import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional, Tuple, Any
from contextlib import contextmanager

# ── Dependencies ──────────────────────────────────────────────────────────────
try:
    import httpx
    import requests
    import grpc
    from google.protobuf import empty_pb2
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.text import Text
    from rich import box
    from rich.rule import Rule
    from rich.columns import Columns
    import psycopg2
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip3 install httpx requests grpcio rich psycopg2-binary")
    sys.exit(1)

# ── Patch gRPC version check (generated for 1.76, installed 1.78) ─────────────
import grpc._utilities
_orig = grpc._utilities.first_version_is_lower
grpc._utilities.first_version_is_lower = lambda a, b: False

# ── Import generated proto stubs ──────────────────────────────────────────────
BACKEND_DIR = '/root/agl/apps/backend'
sys.path.insert(0, BACKEND_DIR)
try:
    from generated import pens_agl_store_pb2 as pb2
    from generated import pens_agl_store_pb2_grpc as pb2_grpc
    GRPC_AVAILABLE = True
except Exception as e:
    GRPC_AVAILABLE = False
    print(f"[warn] gRPC stubs not available: {e}")

# ── Configuration ─────────────────────────────────────────────────────────────
GRPC_HOST        = "localhost:50051"
HTTP_BACKEND_URL = "http://localhost:8000"   # FastAPI on port 8000
REST_API_URL     = "http://localhost:8002"   # uvicorn REST on port 8002
DB_URL           = "postgresql://pensagl:CHANGE_ME_DB_PASSWORD@localhost/agl_store"

console = Console()
RESULTS: Dict[str, Any] = {}


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class BenchResult:
    name: str
    latencies: List[float] = field(default_factory=list)
    errors: int = 0
    bytes_transferred: int = 0

    @property
    def n(self): return len(self.latencies)

    @property
    def mean(self): return statistics.mean(self.latencies) * 1000 if self.latencies else 0

    @property
    def median(self): return statistics.median(self.latencies) * 1000 if self.latencies else 0

    @property
    def stdev(self): return (statistics.stdev(self.latencies) * 1000 if len(self.latencies) > 1 else 0)

    @property
    def min(self): return min(self.latencies) * 1000 if self.latencies else 0

    @property
    def max(self): return max(self.latencies) * 1000 if self.latencies else 0

    def pct(self, p):
        if not self.latencies: return 0
        s = sorted(self.latencies)
        idx = int(math.ceil(p / 100 * len(s))) - 1
        return s[max(0, idx)] * 1000

    @property
    def rps(self):
        if not self.latencies: return 0
        return self.n / sum(self.latencies)

    @property
    def error_rate(self):
        total = self.n + self.errors
        return (self.errors / total * 100) if total > 0 else 0

    def to_dict(self):
        return {
            "name": self.name, "n": self.n, "errors": self.errors,
            "mean_ms": round(self.mean, 3), "median_ms": round(self.median, 3),
            "p95_ms": round(self.pct(95), 3), "p99_ms": round(self.pct(99), 3),
            "min_ms": round(self.min, 3), "max_ms": round(self.max, 3),
            "stdev_ms": round(self.stdev, 3), "rps": round(self.rps, 1),
            "error_rate_pct": round(self.error_rate, 1),
            "bytes_transferred": self.bytes_transferred,
        }


# ── Timing helpers ────────────────────────────────────────────────────────────
@contextmanager
def timer(result: BenchResult, payload_bytes: int = 0):
    t0 = time.perf_counter()
    try:
        yield
        result.latencies.append(time.perf_counter() - t0)
        result.bytes_transferred += payload_bytes
    except Exception:
        result.errors += 1


def run_bench(fn: Callable, reps: int, warmup: int = 3) -> BenchResult:
    """Run fn reps times after warmup; return BenchResult."""
    result = BenchResult(name="")
    for _ in range(warmup):
        try: fn(result)
        except: pass
    result = BenchResult(name="")
    for _ in range(reps):
        fn(result)
    return result


def run_concurrent_bench(fn: Callable, reps: int, concurrency: int) -> BenchResult:
    """Run fn reps times with given concurrency; return BenchResult."""
    result = BenchResult(name="")
    lock = threading.Lock()

    def worker():
        r = BenchResult(name="")
        fn(r)
        with lock:
            result.latencies.extend(r.latencies)
            result.errors += r.errors
            result.bytes_transferred += r.bytes_transferred

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(worker) for _ in range(reps)]
        concurrent.futures.wait(futs)

    return result


# ── Section header ─────────────────────────────────────────────────────────────
def section(title: str):
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]")


# ── Results table ──────────────────────────────────────────────────────────────
def print_comparison_table(results: List[BenchResult], title: str = ""):
    if title:
        console.print(f"\n[bold]{title}[/bold]")

    tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold white on #1a1a2e",
                border_style="dim", padding=(0, 1))
    tbl.add_column("Test", style="bold", min_width=30)
    tbl.add_column("N", justify="right", style="dim")
    tbl.add_column("Mean", justify="right")
    tbl.add_column("Median", justify="right")
    tbl.add_column("p95", justify="right")
    tbl.add_column("p99", justify="right")
    tbl.add_column("Min", justify="right")
    tbl.add_column("Max", justify="right")
    tbl.add_column("RPS", justify="right", style="bold green")
    tbl.add_column("Err%", justify="right", style="bold red")

    best_mean = min((r.mean for r in results if r.mean > 0), default=0)

    for r in results:
        highlight = r.mean == best_mean and r.mean > 0
        style = "bold green" if highlight else ""
        mean_str = f"[bold green]{r.mean:.1f}ms ✓[/bold green]" if highlight else f"{r.mean:.1f}ms"
        err_str = f"[red]{r.error_rate:.1f}%[/red]" if r.error_rate > 0 else "[green]0%[/green]"
        tbl.add_row(
            f"[{style}]{r.name}[/{style}]" if style else r.name,
            str(r.n), mean_str,
            f"{r.median:.1f}ms", f"{r.pct(95):.1f}ms", f"{r.pct(99):.1f}ms",
            f"{r.min:.1f}ms", f"{r.max:.1f}ms",
            f"{r.rps:.0f}", err_str,
        )
    console.print(tbl)


def bar(value: float, max_val: float, width: int = 20) -> str:
    filled = int((value / max_val) * width) if max_val > 0 else 0
    return "█" * filled + "░" * (width - filled)


def print_latency_histogram(result: BenchResult):
    if not result.latencies: return
    lats_ms = [l * 1000 for l in sorted(result.latencies)]
    mn, mx = min(lats_ms), max(lats_ms)
    buckets = 8
    width = (mx - mn) / buckets if mx > mn else 1
    counts = [0] * buckets
    for v in lats_ms:
        idx = min(int((v - mn) / width), buckets - 1)
        counts[idx] += 1
    max_count = max(counts)
    console.print(f"\n  [dim]Latency distribution for[/dim] [bold]{result.name}[/bold]")
    for i, cnt in enumerate(counts):
        lo = mn + i * width
        hi = lo + width
        b = bar(cnt, max_count, 25)
        console.print(f"  {lo:6.1f}-{hi:6.1f}ms │[cyan]{b}[/cyan]│ {cnt:3d}")


# ═════════════════════════════════════════════════════════════════════════════
# BENCHMARK 1: gRPC vs HTTP (same operations)
# ═════════════════════════════════════════════════════════════════════════════
def bench_grpc_vs_http(reps: int = 100):
    section("1 · gRPC vs HTTP/JSON — Same Operations")

    results = []

    # ── gRPC: Healthcheck ─────────────────────────────────────────────────────
    if GRPC_AVAILABLE:
        channel = grpc.insecure_channel(GRPC_HOST)
        stub = pb2_grpc.FlathubServiceStub(channel)
        empty = empty_pb2.Empty()

        def grpc_health(r):
            with timer(r):
                stub.Healthcheck(empty)
        res = run_bench(grpc_health, reps)
        res.name = "gRPC  Healthcheck"
        results.append(res)

        def grpc_categories(r):
            with timer(r):
                resp = stub.GetCategories(empty)
                r.bytes_transferred += resp.ByteSize()
        res = run_bench(grpc_categories, reps)
        res.name = "gRPC  GetCategories"
        results.append(res)

        def grpc_stats(r):
            with timer(r):
                resp = stub.GetStats(empty)
                r.bytes_transferred += resp.ByteSize()
        res = run_bench(grpc_stats, reps)
        res.name = "gRPC  GetStats"
        results.append(res)

        def grpc_appstream(r):
            req = pb2.ListAppstreamRequest(filter="", sort="")
            with timer(r):
                resp = stub.ListAppstream(req)
                r.bytes_transferred += resp.ByteSize()
        res = run_bench(grpc_appstream, reps)
        res.name = "gRPC  ListAppstream"
        results.append(res)

        def grpc_search(r):
            req = pb2.SearchAppsRequest(locale="en", query=pb2.SearchQuery(query="app", hits_per_page=10, page=1))
            with timer(r):
                resp = stub.SearchApps(req)
                r.bytes_transferred += resp.ByteSize()
        res = run_bench(grpc_search, reps)
        res.name = "gRPC  SearchApps"
        results.append(res)

        channel.close()

    # ── HTTP Backend (port 8000) ───────────────────────────────────────────────
    sess = requests.Session()

    def http_health(r):
        with timer(r):
            resp = sess.get(f"{HTTP_BACKEND_URL}/http/health", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(http_health, reps)
    res.name = "HTTP  /http/health"
    results.append(res)

    def http_categories(r):
        with timer(r):
            resp = sess.get(f"{HTTP_BACKEND_URL}/apps/categories", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(http_categories, reps)
    res.name = "HTTP  /apps/categories"
    results.append(res)

    def http_apps(r):
        with timer(r):
            resp = sess.get(f"{HTTP_BACKEND_URL}/apps?limit=20", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(http_apps, reps)
    res.name = "HTTP  /apps?limit=20"
    results.append(res)

    def http_search(r):
        with timer(r):
            resp = sess.get(f"{HTTP_BACKEND_URL}/apps/search?q=app&per_page=10", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(http_search, reps)
    res.name = "HTTP  /apps/search"
    results.append(res)

    # ── REST API (port 8002) ───────────────────────────────────────────────────
    def rest_health(r):
        with timer(r):
            resp = sess.get(f"{REST_API_URL}/health", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(rest_health, reps)
    res.name = "REST  /health"
    results.append(res)

    def rest_categories(r):
        with timer(r):
            resp = sess.get(f"{REST_API_URL}/categories", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(rest_categories, reps)
    res.name = "REST  /categories"
    results.append(res)

    def rest_apps(r):
        with timer(r):
            resp = sess.get(f"{REST_API_URL}/apps?limit=20", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(rest_apps, reps)
    res.name = "REST  /apps?limit=20"
    results.append(res)

    def rest_stats(r):
        with timer(r):
            resp = sess.get(f"{REST_API_URL}/stats", timeout=5)
            r.bytes_transferred += len(resp.content)
    res = run_bench(rest_stats, reps)
    res.name = "REST  /stats"
    results.append(res)

    sess.close()
    print_comparison_table(results, "gRPC · HTTP Backend (8000) · REST API (8002)")

    # Payload size comparison
    if GRPC_AVAILABLE:
        section_title = "Payload size: gRPC protobuf vs HTTP JSON"
        console.print(f"\n  [bold]{section_title}[/bold]")
        channel2 = grpc.insecure_channel(GRPC_HOST)
        stub2 = pb2_grpc.FlathubServiceStub(channel2)
        empty = empty_pb2.Empty()

        def measure(label, grpc_fn, http_url):
            try:
                grpc_resp = grpc_fn(stub2, empty)
                grpc_bytes = grpc_resp.ByteSize()
            except: grpc_bytes = 0
            try:
                http_resp = requests.get(http_url, timeout=5)
                http_bytes = len(http_resp.content)
            except: http_bytes = 0
            ratio = http_bytes / grpc_bytes if grpc_bytes > 0 else 0
            console.print(
                f"  [cyan]{label:<20}[/cyan]  "
                f"gRPC: [green]{grpc_bytes:>6} B[/green]  "
                f"JSON: [yellow]{http_bytes:>6} B[/yellow]  "
                f"ratio: [bold]{ratio:.1f}x[/bold] {'(JSON larger)' if ratio > 1 else ''}"
            )

        measure("GetCategories", lambda s, e: s.GetCategories(e), f"{HTTP_BACKEND_URL}/apps/categories")
        measure("GetStats",      lambda s, e: s.GetStats(e),      f"{REST_API_URL}/stats")
        channel2.close()

    RESULTS["grpc_vs_http"] = [r.to_dict() for r in results]


# ═════════════════════════════════════════════════════════════════════════════
# BENCHMARK 2: Concurrency / Load Test
# ═════════════════════════════════════════════════════════════════════════════
def bench_concurrency(reps_per_level: int = 50):
    section("2 · Concurrency Scaling — REST API")

    concurrency_levels = [1, 5, 10, 25, 50]
    endpoint = f"{REST_API_URL}/apps?limit=10"

    def http_call(r):
        with timer(r):
            resp = requests.get(endpoint, timeout=10)
            r.bytes_transferred += len(resp.content)

    results_by_level = []
    tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold white on #1a1a2e",
                border_style="dim", padding=(0, 1))
    tbl.add_column("Concurrency", justify="right")
    tbl.add_column("Total Req", justify="right")
    tbl.add_column("Mean", justify="right")
    tbl.add_column("p95", justify="right")
    tbl.add_column("p99", justify="right")
    tbl.add_column("RPS", justify="right", style="bold green")
    tbl.add_column("Err%", justify="right", style="bold red")
    tbl.add_column("Throughput", min_width=22)

    max_rps = 0
    for level in concurrency_levels:
        r = run_concurrent_bench(http_call, reps_per_level, level)
        r.name = f"c={level}"
        max_rps = max(max_rps, r.rps)
        results_by_level.append(r)

    for r in results_by_level:
        lvl = int(r.name.split("=")[1])
        b = bar(r.rps, max_rps, 20)
        err_str = f"[red]{r.error_rate:.1f}%[/red]" if r.error_rate > 0 else "[green]0%[/green]"
        tbl.add_row(
            str(lvl), str(r.n),
            f"{r.mean:.1f}ms", f"{r.pct(95):.1f}ms", f"{r.pct(99):.1f}ms",
            f"{r.rps:.0f}", err_str,
            f"[cyan]{b}[/cyan] {r.rps:.0f} rps"
        )
    console.print(tbl)

    # Also show gRPC concurrency if available
    if GRPC_AVAILABLE:
        console.print("\n  [bold]gRPC Concurrency (Healthcheck)[/bold]")
        channel = grpc.insecure_channel(GRPC_HOST)
        stub = pb2_grpc.FlathubServiceStub(channel)
        empty = empty_pb2.Empty()

        def grpc_call(r):
            with timer(r):
                stub.Healthcheck(empty)

        grpc_tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold",
                         padding=(0, 1))
        grpc_tbl.add_column("Concurrency", justify="right")
        grpc_tbl.add_column("Mean", justify="right")
        grpc_tbl.add_column("p95", justify="right")
        grpc_tbl.add_column("RPS", justify="right", style="bold green")

        for level in [1, 5, 10, 25, 50]:
            r = run_concurrent_bench(grpc_call, reps_per_level, level)
            grpc_tbl.add_row(str(level), f"{r.mean:.1f}ms", f"{r.pct(95):.1f}ms", f"{r.rps:.0f}")
        console.print(grpc_tbl)
        channel.close()

    RESULTS["concurrency"] = [r.to_dict() for r in results_by_level]


# ═════════════════════════════════════════════════════════════════════════════
# BENCHMARK 3: Database Benchmark
# ═════════════════════════════════════════════════════════════════════════════
def bench_database(reps: int = 200):
    section("3 · Database Query Benchmarks (PostgreSQL)")

    try:
        conn = psycopg2.connect(DB_URL)
    except Exception as e:
        console.print(f"  [red]DB connection failed: {e}[/red]")
        return

    results = []

    queries = [
        ("SELECT 1 (baseline)",         "SELECT 1"),
        ("COUNT all apps",               "SELECT COUNT(*) FROM apps"),
        ("COUNT published apps",         "SELECT COUNT(*) FROM apps WHERE published = TRUE"),
        ("SELECT apps LIMIT 10",         "SELECT id, name, developer_name FROM apps ORDER BY updated_at DESC LIMIT 10"),
        ("SELECT apps LIMIT 50",         "SELECT id, name, developer_name, summary, expires_at, is_verified FROM apps ORDER BY updated_at DESC LIMIT 50"),
        ("SELECT categories",            "SELECT name, description FROM categories ORDER BY name"),
        ("JOIN apps+categories (1 app)", "SELECT a.id, a.name, c.name FROM apps a LEFT JOIN app_categories ac ON a.id = ac.app_id LEFT JOIN categories c ON ac.category_id = c.id LIMIT 10"),
        ("SELECT users LIMIT 20",        "SELECT id, display_name, role, is_trusted_publisher FROM users LIMIT 20"),
        ("SELECT submissions pending",   "SELECT id, app_id, name, status, submitted_at FROM app_submissions WHERE status='pending' ORDER BY submitted_at DESC"),
        ("FULL TEXT search apps",        "SELECT id, name FROM apps WHERE name ILIKE '%app%' OR summary ILIKE '%app%' LIMIT 20"),
        ("SELECT by expires_at",         "SELECT id, expires_at FROM apps WHERE expires_at IS NOT NULL AND expires_at < NOW() + INTERVAL '30 days'"),
    ]

    cur = conn.cursor()
    for label, sql in queries:
        def make_fn(q):
            def fn(r):
                with timer(r):
                    cur.execute(q)
                    rows = cur.fetchall()
                    r.bytes_transferred += sum(len(str(row)) for row in rows)
            return fn
        res = run_bench(make_fn(sql), reps)
        res.name = label
        results.append(res)

    cur.close()
    conn.close()

    print_comparison_table(results, "PostgreSQL Query Latency")

    # Print histogram for the slowest query
    slowest = max(results, key=lambda r: r.mean)
    print_latency_histogram(slowest)

    RESULTS["database"] = [r.to_dict() for r in results]


# ═════════════════════════════════════════════════════════════════════════════
# BENCHMARK 4: Async HTTP (httpx) — Pipeline & Keep-Alive
# ═════════════════════════════════════════════════════════════════════════════
def bench_async_http(reps: int = 100):
    section("4 · Async HTTP — Keep-Alive vs New Connection vs Sync")

    async def run_async():
        results = []

        # Keep-alive (single client, reused connection)
        async with httpx.AsyncClient(base_url=REST_API_URL, timeout=10) as client:
            res = BenchResult(name="")
            for _ in range(5): await client.get("/health")  # warmup
            res = BenchResult(name="")
            for _ in range(reps):
                t0 = time.perf_counter()
                try:
                    r = await client.get("/apps?limit=10")
                    res.latencies.append(time.perf_counter() - t0)
                    res.bytes_transferred += len(r.content)
                except: res.errors += 1
            res.name = "httpx async keep-alive /apps"
            results.append(res)

            # Pipelined (concurrent requests in a batch of 10)
            res2 = BenchResult(name="")
            for _ in range(reps // 10):
                t0 = time.perf_counter()
                try:
                    reqs = await asyncio.gather(*[client.get("/apps?limit=10") for _ in range(10)])
                    elapsed = time.perf_counter() - t0
                    for r in reqs: res2.bytes_transferred += len(r.content)
                    res2.latencies.append(elapsed / 10)  # per-request avg
                except: res2.errors += 10
            res2.name = "httpx async pipeline (10x)"
            results.append(res2)

        # New connection per request (no keep-alive)
        res3 = BenchResult(name="")
        for _ in range(reps):
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(base_url=REST_API_URL, timeout=10) as c:
                    r = await c.get("/apps?limit=10")
                    res3.bytes_transferred += len(r.content)
                res3.latencies.append(time.perf_counter() - t0)
            except: res3.errors += 1
        res3.name = "httpx async new-conn /apps"
        results.append(res3)

        return results

    # requests (sync, keep-alive via Session)
    res_sync_ka = BenchResult(name="")
    sess = requests.Session()
    for _ in range(5): sess.get(f"{REST_API_URL}/health")
    for _ in range(reps):
        t0 = time.perf_counter()
        try:
            r = sess.get(f"{REST_API_URL}/apps?limit=10", timeout=5)
            res_sync_ka.latencies.append(time.perf_counter() - t0)
            res_sync_ka.bytes_transferred += len(r.content)
        except: res_sync_ka.errors += 1
    sess.close()
    res_sync_ka.name = "requests sync keep-alive /apps"

    # requests (sync, no Session)
    res_sync_new = BenchResult(name="")
    for _ in range(reps):
        t0 = time.perf_counter()
        try:
            r = requests.get(f"{REST_API_URL}/apps?limit=10", timeout=5)
            res_sync_new.latencies.append(time.perf_counter() - t0)
            res_sync_new.bytes_transferred += len(r.content)
        except: res_sync_new.errors += 1
    res_sync_new.name = "requests sync new-conn /apps"

    async_results = asyncio.run(run_async())
    all_results = async_results + [res_sync_ka, res_sync_new]
    print_comparison_table(all_results, "Connection Strategy Comparison (/apps?limit=10)")
    RESULTS["async_http"] = [r.to_dict() for r in all_results]


# ═════════════════════════════════════════════════════════════════════════════
# BENCHMARK 5: Endpoint Depth (small vs large payloads)
# ═════════════════════════════════════════════════════════════════════════════
def bench_payload_sizes(reps: int = 100):
    section("5 · Payload Size Impact — REST API endpoints")

    sess = requests.Session()
    endpoints = [
        ("/health",                           "Health check"),
        ("/stats",                            "Platform stats"),
        ("/categories",                       "All categories"),
        ("/apps?limit=1",                     "Apps limit=1"),
        ("/apps?limit=10",                    "Apps limit=10"),
        ("/apps?limit=50",                    "Apps limit=50"),
        ("/apps?limit=200",                   "Apps limit=200"),
        ("/apps?search=a&limit=20",           "Apps search='a'"),
        ("/admin/stats",                      "Admin stats (no auth)"),
    ]

    results = []
    payload_info = []

    for path, label in endpoints:
        def make_fn(p):
            def fn(r):
                with timer(r):
                    resp = sess.get(f"{REST_API_URL}{p}", timeout=10)
                    r.bytes_transferred += len(resp.content)
            return fn
        res = run_bench(make_fn(path), reps)
        res.name = label
        results.append(res)

        # Measure payload once
        try:
            resp = sess.get(f"{REST_API_URL}{path}", timeout=5)
            payload_info.append((label, len(resp.content), resp.status_code))
        except:
            payload_info.append((label, 0, 0))

    sess.close()
    print_comparison_table(results, "Endpoint Latency by Payload Size")

    # Payload vs latency table
    console.print("\n  [bold]Payload size → latency correlation[/bold]")
    payload_tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 1))
    payload_tbl.add_column("Endpoint")
    payload_tbl.add_column("Status", justify="right")
    payload_tbl.add_column("Payload", justify="right")
    payload_tbl.add_column("Mean latency", justify="right")
    payload_tbl.add_column("Payload bar", min_width=20)

    max_bytes = max((b for _, b, _ in payload_info), default=1)
    for (label, nbytes, status), res in zip(payload_info, results):
        b = bar(nbytes, max_bytes, 20)
        status_style = "green" if status == 200 else "red"
        payload_tbl.add_row(
            label, f"[{status_style}]{status}[/{status_style}]",
            f"{nbytes:,} B", f"{res.mean:.1f}ms",
            f"[cyan]{b}[/cyan]"
        )
    console.print(payload_tbl)
    RESULTS["payload_sizes"] = [r.to_dict() for r in results]


# ═════════════════════════════════════════════════════════════════════════════
# BENCHMARK 6: gRPC streaming vs unary (latency distribution)
# ═════════════════════════════════════════════════════════════════════════════
def bench_grpc_operations(reps: int = 100):
    if not GRPC_AVAILABLE:
        return
    section("6 · gRPC Operation Comparison")

    channel = grpc.insecure_channel(GRPC_HOST)
    stub = pb2_grpc.FlathubServiceStub(channel)
    empty = empty_pb2.Empty()

    ops = [
        ("Healthcheck",      lambda: stub.Healthcheck(empty)),
        ("GetCategories",    lambda: stub.GetCategories(empty)),
        ("GetStats",         lambda: stub.GetStats(empty)),
        ("ListAppstream",    lambda: stub.ListAppstream(pb2.ListAppstreamRequest(filter="", sort=""))),
        ("GetLoginMethods",  lambda: stub.GetLoginMethods(empty)),
        ("GetPlatforms",     lambda: stub.GetPlatforms(empty)),
        ("GetEolRebase",     lambda: stub.GetEolRebase(empty)),
        ("GetEolMessage",    lambda: stub.GetEolMessage(empty)),
        ("SearchApps(empty)",lambda: stub.SearchApps(pb2.SearchAppsRequest(locale="en", query=pb2.SearchQuery(query="", hits_per_page=5)))),
        ("SearchApps('app')",lambda: stub.SearchApps(pb2.SearchAppsRequest(locale="en", query=pb2.SearchQuery(query="app", hits_per_page=10)))),
        ("GetRecentlyAdded", lambda: stub.GetRecentlyAdded(pb2.GetRecentlyAddedRequest(page=1, per_page=10))),
        ("GetVerified",      lambda: stub.GetVerified(pb2.GetVerifiedRequest(page=1, per_page=10))),
    ]

    results = []
    for label, fn in ops:
        def make_fn(f):
            def bench(r):
                t0 = time.perf_counter()
                try:
                    resp = f()
                    r.latencies.append(time.perf_counter() - t0)
                    r.bytes_transferred += resp.ByteSize()
                except grpc.RpcError as e:
                    # INTERNAL = server-side failure (DB error etc.) — count as error
                    # UNIMPLEMENTED = stub not implemented — skip silently
                    if e.code() != grpc.StatusCode.UNIMPLEMENTED:
                        r.errors += 1
                except Exception:
                    r.errors += 1
            return bench
        res = run_bench(make_fn(fn), reps)
        res.name = f"gRPC {label}"
        results.append(res)

    channel.close()
    print_comparison_table(results, "gRPC Operation Latency")

    # Print error breakdown
    failed = [r for r in results if r.n == 0 and r.errors > 0]
    ok     = [r for r in results if r.n > 0]
    if failed:
        console.print("\n  [dim]gRPC: " + str(len(ok)) + " ok, " + str(len(failed)) + " failed (DB error)[/dim]")
    if ok:
        print_latency_histogram(ok[0])
    RESULTS["grpc_operations"] = [r.to_dict() for r in results]


# ═════════════════════════════════════════════════════════════════════════════
# BENCHMARK 7: End-to-end user flow (simulated real user)
# ═════════════════════════════════════════════════════════════════════════════
def bench_user_flow(reps: int = 50):
    section("7 · Simulated User Flow — End-to-End")

    sess = requests.Session()

    def user_browse_flow(r):
        """Simulates: load homepage → get categories → browse apps → search"""
        t0 = time.perf_counter()
        try:
            # 1. Load stats (homepage call)
            sess.get(f"{REST_API_URL}/stats", timeout=5)
            # 2. Get categories
            sess.get(f"{REST_API_URL}/categories", timeout=5)
            # 3. Browse apps (first page)
            sess.get(f"{REST_API_URL}/apps?limit=20", timeout=5)
            # 4. Search
            sess.get(f"{REST_API_URL}/apps?search=app&limit=10", timeout=5)
            r.latencies.append(time.perf_counter() - t0)
        except: r.errors += 1

    def admin_flow(r):
        """Simulates: admin login check → get stats → list apps → list submissions"""
        t0 = time.perf_counter()
        try:
            sess.get(f"{REST_API_URL}/health", timeout=5)
            sess.get(f"{REST_API_URL}/stats", timeout=5)
            sess.get(f"{REST_API_URL}/apps?limit=50", timeout=5)
            sess.get(f"{REST_API_URL}/categories", timeout=5)
            r.latencies.append(time.perf_counter() - t0)
        except: r.errors += 1

    def single_app_page(r):
        """Simulates: load single app page"""
        t0 = time.perf_counter()
        try:
            apps = sess.get(f"{REST_API_URL}/apps?limit=1", timeout=5).json()
            if apps:
                app_id = apps[0]['id']
                sess.get(f"{REST_API_URL}/apps/{app_id}", timeout=5)
            r.latencies.append(time.perf_counter() - t0)
        except: r.errors += 1

    flows = [
        ("User browse flow (4 reqs)",  user_browse_flow),
        ("Admin overview flow (4 reqs)", admin_flow),
        ("Single app page (2 reqs)",   single_app_page),
    ]

    results = []
    for name, fn in flows:
        res = run_bench(fn, reps)
        res.name = name
        results.append(res)

    sess.close()
    print_comparison_table(results, "Full User Flow Latency (total per flow)")
    RESULTS["user_flows"] = [r.to_dict() for r in results]


# ═════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
def print_summary():
    section("Summary")

    console.print("\n  [bold green]✓ Benchmark complete.[/bold green]\n")

    if "grpc_vs_http" in RESULTS:
        grpc_res = [r for r in RESULTS["grpc_vs_http"] if r["name"].startswith("gRPC") and r["mean_ms"] > 0]
        http_res  = [r for r in RESULTS["grpc_vs_http"] if (r["name"].startswith("HTTP") or r["name"].startswith("REST")) and r["mean_ms"] > 0]
        if grpc_res and http_res:
            grpc_mean = statistics.mean(r["mean_ms"] for r in grpc_res)
            http_mean = statistics.mean(r["mean_ms"] for r in http_res)
            winner    = "gRPC" if grpc_mean < http_mean else "HTTP/REST"
            speedup   = max(grpc_mean, http_mean) / min(grpc_mean, http_mean) if min(grpc_mean, http_mean) > 0 else 0
            console.print(f"  Protocol winner:  [bold cyan]{winner}[/bold cyan]  ({speedup:.1f}x faster avg)")
        elif grpc_res:
            grpc_mean = statistics.mean(r["mean_ms"] for r in grpc_res)
            console.print(f"  gRPC avg latency: [bold cyan]{grpc_mean:.1f}ms[/bold cyan] (HTTP/REST results not available)")
        elif http_res:
            http_mean = statistics.mean(r["mean_ms"] for r in http_res)
            console.print(f"  HTTP/REST avg:    [bold cyan]{http_mean:.1f}ms[/bold cyan] (gRPC DB-dependent calls failed — see bench 6)")

    if "database" in RESULTS:
        db_means = [r["mean_ms"] for r in RESULTS["database"]]
        console.print(f"  DB query range:   [bold]{min(db_means):.2f}ms[/bold] – [bold]{max(db_means):.2f}ms[/bold]")

    if "concurrency" in RESULTS:
        best_rps = max(r["rps"] for r in RESULTS["concurrency"])
        best_c   = [r["name"] for r in RESULTS["concurrency"] if r["rps"] == best_rps][0]
        console.print(f"  Peak throughput:  [bold green]{best_rps:.0f} RPS[/bold green] at {best_c}")

    console.print()


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="AGL App Store Benchmark Suite")
    parser.add_argument("--quick",     action="store_true", help="Fewer repetitions (fast mode)")
    parser.add_argument("--grpc-only", action="store_true", help="gRPC vs HTTP only")
    parser.add_argument("--load",      action="store_true", help="Concurrency/load test only")
    parser.add_argument("--db",        action="store_true", help="Database benchmark only")
    parser.add_argument("--export",    action="store_true", help="Export to benchmark_results.json")
    parser.add_argument("--reps",      type=int, default=0,  help="Override repetitions")
    args = parser.parse_args()

    reps = args.reps if args.reps > 0 else (25 if args.quick else 100)
    db_reps = args.reps if args.reps > 0 else (50 if args.quick else 200)

    console.print(Panel.fit(
        "[bold white]AGL App Store — Benchmark Suite[/bold white]\n"
        f"[dim]gRPC :50051 · HTTP :8000 · REST :8002 · PostgreSQL[/dim]\n"
        f"[dim]Repetitions: {reps}  |  DB reps: {db_reps}  |  gRPC stubs: {'✓' if GRPC_AVAILABLE else '✗'}[/dim]",
        border_style="cyan", box=box.DOUBLE
    ))

    only_one = args.grpc_only or args.load or args.db

    if not only_one or args.grpc_only:
        bench_grpc_vs_http(reps)

    if not only_one or args.load:
        bench_concurrency(min(reps, 50))

    if not only_one or args.db:
        bench_database(db_reps)

    if not only_one:
        bench_async_http(reps)
        bench_payload_sizes(reps)
        bench_grpc_operations(reps)
        bench_user_flow(min(reps, 50))

    print_summary()

    if args.export or not only_one:
        out = "/root/agl/benchmark_results.json"
        with open(out, "w") as f:
            json.dump(RESULTS, f, indent=2)
        console.print(f"  Results exported → [cyan]{out}[/cyan]\n")


if __name__ == "__main__":
    main()
