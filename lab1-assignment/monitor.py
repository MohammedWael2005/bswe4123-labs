import argparse
import asyncio
import time
from datetime import datetime
import httpx

DEFAULT_PORTS = [8001, 8002, 8003]
DEFAULT_INTERVAL = 2.0
DEFAULT_TIMEOUT = 1.5
DEFAULT_SLOW_MS = 500
DEFAULT_FAIL_THRESHOLD = 3


class Service:
    def __init__(self, port):
        self.port = port
        self.url = f"http://127.0.0.1:{port}/health"
        self.state = "UNKNOWN"
        self.misses = 0

    def update(self, result, slow_ms, threshold):
        old_state = self.state

        if result["ok"]:
            self.misses = 0
            self.state = "SLOW" if result["ms"] > slow_ms else "UP"
        else:
            self.misses += 1
            if self.misses >= threshold:
                self.state = "DOWN"

        return old_state, self.state


async def check_service(client, service):
    start = time.perf_counter()
    try:
        res = await client.get(service.url)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if res.status_code != 200:
            return {"ok": False, "reason": f"HTTP {res.status_code}"}

        data = res.json()
        if data.get("status") != "ok":
            return {"ok": False, "reason": "bad status"}

        return {"ok": True, "ms": elapsed_ms, "uptime": data.get("uptime_seconds")}

    except httpx.TimeoutException:
        return {"ok": False, "reason": "timeout"}
    except httpx.ConnectError:
        return {"ok": False, "reason": "refused"}
    except (httpx.HTTPError, ValueError) as e:
        return {"ok": False, "reason": type(e).__name__}


def format_status(service, result, threshold):
    if result["ok"]:
        uptime = result.get("uptime")
        uptime_str = f"up {uptime:.0f}s" if uptime is not None else ""
        text = f"{service.state:<5} {result['ms']:4.0f} ms {uptime_str}"
    elif service.state == "DOWN":
        text = f"DOWN  ({result['reason']})"
    else:
        text = f"{service.state}?  miss {service.misses}/{threshold} ({result['reason']})"

    return f"{service.port} {text:<27}"


async def run(args):
    services = [Service(p) for p in args.ports]

    print(
        f"Monitoring {len(services)} services every {args.interval:g}s | "
        f"timeout {args.timeout:g}s | SLOW > {args.slow_ms} ms | "
        f"DOWN after {args.fail_threshold} failed check(s) in a row"
    )

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        start_time = time.monotonic()
        round_num = 0

        while args.duration is None or (time.monotonic() - start_time) < args.duration:
            round_num += 1
            now = datetime.now()

            tasks = [check_service(client, s) for s in services]
            results = await asyncio.gather(*tasks)

            parts = []
            changes = []
            for service, res in zip(services, results):
                old_state, new_state = service.update(res, args.slow_ms, args.fail_threshold)
                parts.append(format_status(service, res, args.fail_threshold))

                if old_state != "UNKNOWN" and old_state != new_state:
                    changes.append(f"{service.port} {old_state}->{new_state}")

            output = f"{now:%H:%M:%S} #{round_num:02d} | " + " | ".join(parts)
            if changes:
                output += "  << " + ", ".join(changes)
            print(output, flush=True)

            next_tick = start_time + round_num * args.interval
            sleep_time = max(0.0, next_tick - time.monotonic())
            await asyncio.sleep(sleep_time)


def main():
    parser = argparse.ArgumentParser(description="Health monitor for the lab services")
    parser.add_argument("--ports", type=int, nargs="+", default=DEFAULT_PORTS)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help="seconds between rounds")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="request timeout in seconds")
    parser.add_argument("--slow-ms", type=int, default=DEFAULT_SLOW_MS, help="SLOW above this many ms")
    parser.add_argument(
        "--fail-threshold",
        type=int,
        default=DEFAULT_FAIL_THRESHOLD,
        help="failed checks in a row before a service is DOWN (1 = no tolerance)",
    )
    parser.add_argument("--duration", type=float, default=None, help="stop after N seconds")
    args = parser.parse_args()

    if args.timeout >= args.interval:
        parser.error("--timeout must be shorter than --interval, or rounds would overlap")
    if args.timeout * 1000 <= args.slow_ms:
        parser.error("--timeout must be longer than --slow-ms, or SLOW services look DOWN")

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Monitor stopped.")


if __name__ == "__main__":
    main()
