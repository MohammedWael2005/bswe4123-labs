import argparse
import asyncio
import time
from fastapi import FastAPI
import uvicorn

app = FastAPI(title="BSWE4123 lab service")

start_time = time.monotonic()
service_name = "service"
health_delay = 0.0


@app.get("/")
def root():
    return {"service": service_name, "message": "Hello from the lab service"}


@app.get("/hello/{name}")
def hello(name: str):
    return {"service": service_name, "message": f"Hello, {name}!"}


@app.get("/health")
async def health():
    if health_delay > 0:
        await asyncio.sleep(health_delay)

    uptime = round(time.monotonic() - start_time, 1)
    return {
        "status": "ok",
        "uptime_seconds": uptime,
    }


def main():
    global service_name, health_delay

    parser = argparse.ArgumentParser(description="Lab service with a /health endpoint")
    parser.add_argument("--port", type=int, default=8001, help="port to listen on")
    parser.add_argument("--name", default=None, help="service name (default: service-<port>)")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds /health waits before answering (to simulate a slow service)",
    )
    args = parser.parse_args()

    service_name = args.name or f"service-{args.port}"
    health_delay = args.delay

    print(f"Starting {service_name} on port {args.port} (health delay {args.delay}s)")
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
