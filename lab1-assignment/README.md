# Lab 1 – Is the Service Up, Slow or Down?

Health monitor that sends `GET /health` to three copies of a web service every 2 seconds and shows each one as **UP**, **SLOW** or **DOWN**.

| File | Description |
|------|-------------|
| `service.py` | FastAPI service with `/health` endpoint + `--delay` flag to fake slowness |
| `monitor.py` | The health checker – uses httpx, classifies each service, marks DOWN only after several misses |
| `requirements.txt` | Dependencies |

Tested on Windows 11 with Python 3.14, FastAPI 0.115, uvicorn 0.30.6, httpx 0.27.2.

## Running it

```bash
pip install -r requirements.txt
```

Need 4 terminals:

```bash
python service.py --port 8001
python service.py --port 8002
python service.py --port 8003
python monitor.py --duration 60
```

To simulate a slow service, kill the original and run:

```bash
python service.py --port 8003 --delay 0.8
```

Other flags: `--interval` (default 2s), `--timeout` (default 1.5s),
`--slow-ms` (default 500), `--fail-threshold` (default 3), `--duration`
(runs forever if not set), `--ports` (default 8001 8002 8003).
Use `--fail-threshold 1` to get step 2 behavior where one miss = DOWN.

---

## Step 1 – `/health` endpoint

Added a `/health` route to `service.py`. It saves `time.monotonic()` at startup and returns uptime on each call:

```
GET http://127.0.0.1:8001/health
{"status":"ok","uptime_seconds":2.8}
```

I went with `time.monotonic()` instead of `time.time()` because monotonic doesn't get messed up if the system clock changes. The uptime ended up being really useful during testing – when it resets to 0 you know the service got restarted, even if the monitor didn't catch the downtime.

The `--delay` flag adds an `asyncio.sleep()` before responding. Since it's async, the service doesn't freeze – it can still handle other requests while waiting.

## Step 2 – `monitor.py`

Every round the monitor hits `GET /health` on all three services and classifies each one:

| What happened | Classification |
|---|---|
| Got HTTP 200 with `"status": "ok"` within 500ms | **UP** + response time |
| Got HTTP 200 with `"status": "ok"` but took over 500ms | **SLOW** + response time |
| Timeout, connection error, bad HTTP status, or missing `"status": "ok"` | failed check, counts toward **DOWN** (see step 4) |

Some design choices I made:

- I use one `httpx.AsyncClient` with `timeout=1.5` for the whole session. Keeps TCP connections alive between rounds – that's why the very first check (8001 in round 1) takes ~70ms while later checks take ~5ms.
- All three checks run at the same time with `asyncio.gather`. If I checked them one by one, three dead services would take 4.5s total (3 × 1.5s timeout) which is way more than the 2s interval. In parallel it always finishes within the timeout.
- Rounds follow a fixed schedule based on `start + n × interval` so they don't drift no matter how long each check takes.
- The monitor won't start if you give it nonsense settings (timeout >= interval, or timeout <= slow threshold).
- State changes get flagged at the end of the line like `<< 8002 UP->DOWN`. Each service also shows its reported uptime.

---

## Step 3 – one minute experiment (no tolerance)

This run used `--fail-threshold 1` so a single failed check = DOWN.

Services were stopped with a Ctrl+Break signal (uvicorn treats it like Ctrl+C, clean shutdown) and started again with the normal command.

| Time | Action |
|---|---|
| 18:35:24 | Started all 3 services + `python monitor.py --duration 60 --fail-threshold 1` |
| 18:35:36.6 | Stopped **8002** |
| 18:35:48.4 | Restarted 8002 normally |
| 18:35:58.7 | Stopped **8003** |
| 18:36:01.2 | Started slow 8003: `python service.py --port 8003 --delay 0.8` |

Output:

```
Monitoring 3 services every 2s | timeout 1.5s | SLOW > 500 ms | DOWN after 1 failed check(s) in a row
18:35:25 #01 | 8001 UP      66 ms up 2s         | 8002 UP       7 ms up 2s         | 8003 UP       7 ms up 2s
18:35:27 #02 | 8001 UP       8 ms up 4s         | 8002 UP       7 ms up 4s         | 8003 UP       7 ms up 4s
18:35:29 #03 | 8001 UP       7 ms up 6s         | 8002 UP       7 ms up 6s         | 8003 UP       6 ms up 6s
18:35:31 #04 | 8001 UP       6 ms up 8s         | 8002 UP       6 ms up 8s         | 8003 UP       6 ms up 8s
18:35:33 #05 | 8001 UP       5 ms up 10s        | 8002 UP       5 ms up 10s        | 8003 UP       4 ms up 10s
18:35:35 #06 | 8001 UP       6 ms up 12s        | 8002 UP       7 ms up 12s        | 8003 UP       6 ms up 12s
18:35:37 #07 | 8001 UP       7 ms up 14s        | 8002 DOWN  (timeout)             | 8003 UP       5 ms up 14s         << 8002 UP->DOWN
18:35:39 #08 | 8001 UP       7 ms up 16s        | 8002 DOWN  (timeout)             | 8003 UP       5 ms up 16s
18:35:41 #09 | 8001 UP       7 ms up 18s        | 8002 DOWN  (timeout)             | 8003 UP       4 ms up 18s
18:35:43 #10 | 8001 UP       8 ms up 20s        | 8002 DOWN  (timeout)             | 8003 UP       7 ms up 20s
18:35:45 #11 | 8001 UP       6 ms up 22s        | 8002 DOWN  (timeout)             | 8003 UP       4 ms up 22s
18:35:47 #12 | 8001 UP       3 ms up 24s        | 8002 DOWN  (timeout)             | 8003 UP       3 ms up 24s
18:35:49 #13 | 8001 UP       9 ms up 26s        | 8002 SLOW   523 ms up 0s         | 8003 UP       7 ms up 26s         << 8002 DOWN->SLOW
18:35:51 #14 | 8001 UP       4 ms up 28s        | 8002 UP       4 ms up 2s         | 8003 UP       4 ms up 28s         << 8002 SLOW->UP
18:35:53 #15 | 8001 UP       6 ms up 30s        | 8002 UP       6 ms up 4s         | 8003 UP       6 ms up 30s
18:35:55 #16 | 8001 UP       5 ms up 32s        | 8002 UP       5 ms up 6s         | 8003 UP       5 ms up 32s
18:35:57 #17 | 8001 UP       4 ms up 34s        | 8002 UP       4 ms up 8s         | 8003 UP       3 ms up 34s
18:35:59 #18 | 8001 UP      66 ms up 36s        | 8002 UP      57 ms up 10s        | 8003 DOWN  (timeout)              << 8003 UP->DOWN
18:36:01 #19 | 8001 UP      16 ms up 38s        | 8002 UP      16 ms up 12s        | 8003 DOWN  (timeout)
18:36:03 #20 | 8001 UP       8 ms up 40s        | 8002 UP       7 ms up 14s        | 8003 DOWN  (timeout)
18:36:05 #21 | 8001 UP       8 ms up 42s        | 8002 UP       7 ms up 16s        | 8003 SLOW   828 ms up 2s          << 8003 DOWN->SLOW
18:36:07 #22 | 8001 UP       6 ms up 44s        | 8002 UP       5 ms up 18s        | 8003 SLOW   821 ms up 4s
18:36:09 #23 | 8001 UP      12 ms up 46s        | 8002 UP      11 ms up 20s        | 8003 SLOW   819 ms up 6s
18:36:11 #24 | 8001 UP      10 ms up 48s        | 8002 UP      10 ms up 22s        | 8003 SLOW   813 ms up 8s
18:36:13 #25 | 8001 UP       6 ms up 50s        | 8002 UP       6 ms up 24s        | 8003 DOWN  (timeout)              << 8003 SLOW->DOWN
18:36:15 #26 | 8001 UP       6 ms up 52s        | 8002 UP       6 ms up 26s        | 8003 SLOW   810 ms up 12s         << 8003 DOWN->SLOW
18:36:17 #27 | 8001 UP       6 ms up 54s        | 8002 UP       6 ms up 28s        | 8003 SLOW   811 ms up 14s
18:36:19 #28 | 8001 UP       3 ms up 56s        | 8002 UP       2 ms up 30s        | 8003 SLOW   827 ms up 16s
18:36:21 #29 | 8001 UP       6 ms up 58s        | 8002 UP       5 ms up 32s        | 8003 SLOW   818 ms up 18s
18:36:23 #30 | 8001 UP       2 ms up 60s        | 8002 UP       2 ms up 34s        | 8003 SLOW   810 ms up 20s
```

### What happened and why

**Rounds 1-6:** Everything normal. All three responding in 3-8ms. 8001 took 66ms on the first round because it had to open a new TCP connection, after that the connection gets reused.

**Round 7 – 8002 goes DOWN:** 8002 was stopped at 18:35:36.6 and the next check failed, but only after waiting the full 1.5s timeout. Interesting thing – the failure reason is `timeout`, not `refused`. On Windows when you connect to a closed port on localhost, Windows doesn't reject it right away. It retries internally for about 2.3 seconds (measured: 2339ms before WinError 10061). My timeout is 1.5s so httpx hits the timeout first. On Linux this would show `refused` instead, but either way it's a failed check.

**Rounds 7-12:** 8002 stays DOWN for 6 rounds (~12s). 8001 and 8003 not affected at all since checks run in parallel.

**Round 13 – 8002 comes back as SLOW (523ms, up 0s):** It was restarted at 18:35:48.4. The check at :49 caught it mid-startup – the port wasn't fully open yet. Windows retried the TCP connection and it connected as soon as the port opened, so the total request time was 523ms. The service itself wasn't slow, the *connection* was slow because of the startup timing. `up 0s` confirms it's a fresh process.

**Round 14 – 8002 back to UP (4ms).** Fully started now, back to normal speed. Getting one slow check right after restart is expected.

**Round 18 – 8003 goes DOWN.** Stopped at 18:35:58.7 to swap in the slow version. That same round 8001 and 8002 spiked to 57-66ms (probably because the machine was busy), but still way under 500ms.

**Rounds 18-20:** 8003 DOWN for 3 rounds (~6s). That's the 2.5s gap before the slow copy was started (18:36:01.2) plus Python/FastAPI startup (~3s).

**Round 21 – 8003 comes back SLOW (828ms, up 2s).** The slow copy is running now. Each health check takes the 800ms artificial delay plus a few ms overhead, so it's always above 500ms = SLOW.

**Rounds 22-24, 26-30:** 8003 stays SLOW at 810-828ms. Working as expected.

**Round 25 – false alarm.** 8003 briefly showed DOWN then went back to SLOW in round 26. The service never actually crashed – uptime went from 8s (#24) to 12s (#26), same process. What happened is one check took over 1.5s. The slow service normally responds in ~810ms, leaving only ~700ms margin before the timeout. A small hiccup on the machine pushed it over. With the "one miss = DOWN" rule, a perfectly working service got marked DOWN for 2 seconds. This is the problem step 4 fixes.

**8001** was untouched the whole time and stayed UP – it's basically the control variable showing that the changes in 8002/8003 came from stopping and starting them, not from bugs in the monitor.

---

## Step 4 – DOWN only after multiple misses

### What I changed

Added a miss counter per service:

```python
if result["ok"]:
    self.misses = 0
    self.state = "SLOW" if result["ms"] > slow_ms else "UP"
else:
    self.misses += 1
    if self.misses >= fail_threshold:   # default 3
        self.state = "DOWN"
```

The idea:
- One failed check doesn't flip the state. The service keeps its last state but with a `?` and miss count, like `UP?  miss 1/3 (timeout)`. Basically "it didn't respond but let's not panic yet."
- After **3 consecutive failures**, it goes to DOWN.
- **One good response** instantly resets the counter. This is intentionally asymmetric – not responding doesn't prove a service is dead (could be a network hiccup), but getting a real response *does* prove it's alive.

Same scenario again, this time with default `--fail-threshold 3`:

| Time | Action |
|---|---|
| 18:36:50 | Started everything + `python monitor.py --duration 60` |
| 18:37:02.3 | Stopped **8002** |
| 18:37:15.2 | Restarted 8002 normally |
| 18:37:24.4 | Stopped **8003** |
| 18:37:26.9 | Started slow 8003: `python service.py --port 8003 --delay 0.8` |

```
Monitoring 3 services every 2s | timeout 1.5s | SLOW > 500 ms | DOWN after 3 failed check(s) in a row
18:36:51 #01 | 8001 UP      71 ms up 2s         | 8002 UP       6 ms up 2s         | 8003 UP       6 ms up 2s
18:36:53 #02 | 8001 UP       4 ms up 4s         | 8002 UP       4 ms up 4s         | 8003 UP       4 ms up 4s
18:36:55 #03 | 8001 UP       4 ms up 6s         | 8002 UP       5 ms up 6s         | 8003 UP       4 ms up 6s
18:36:57 #04 | 8001 UP       4 ms up 8s         | 8002 UP       3 ms up 8s         | 8003 UP       4 ms up 8s
18:36:59 #05 | 8001 UP       5 ms up 10s        | 8002 UP       4 ms up 10s        | 8003 UP       4 ms up 10s
18:37:01 #06 | 8001 UP       3 ms up 12s        | 8002 UP       2 ms up 12s        | 8003 UP       2 ms up 12s
18:37:03 #07 | 8001 UP       4 ms up 14s        | 8002 UP?  miss 1/3 (timeout)     | 8003 UP       3 ms up 14s
18:37:05 #08 | 8001 UP       3 ms up 16s        | 8002 UP?  miss 2/3 (timeout)     | 8003 UP       2 ms up 16s
18:37:07 #09 | 8001 UP       6 ms up 18s        | 8002 DOWN  (timeout)             | 8003 UP       5 ms up 18s         << 8002 UP->DOWN
18:37:09 #10 | 8001 UP       3 ms up 20s        | 8002 DOWN  (timeout)             | 8003 UP       3 ms up 20s
18:37:11 #11 | 8001 UP       4 ms up 22s        | 8002 DOWN  (timeout)             | 8003 UP       3 ms up 22s
18:37:13 #12 | 8001 UP       8 ms up 24s        | 8002 DOWN  (timeout)             | 8003 UP       7 ms up 24s
18:37:15 #13 | 8001 UP       8 ms up 26s        | 8002 DOWN  (timeout)             | 8003 UP       6 ms up 26s
18:37:17 #14 | 8001 UP       5 ms up 28s        | 8002 UP       6 ms up 0s         | 8003 UP       4 ms up 28s         << 8002 DOWN->UP
18:37:19 #15 | 8001 UP       5 ms up 30s        | 8002 UP       5 ms up 2s         | 8003 UP       5 ms up 30s
18:37:21 #16 | 8001 UP       3 ms up 32s        | 8002 UP       4 ms up 4s         | 8003 UP       3 ms up 32s
18:37:23 #17 | 8001 UP       5 ms up 34s        | 8002 UP       5 ms up 6s         | 8003 UP       5 ms up 34s
18:37:25 #18 | 8001 UP       6 ms up 36s        | 8002 UP       6 ms up 8s         | 8003 UP?  miss 1/3 (timeout)
18:37:28 #19 | 8001 UP     182 ms up 38s        | 8002 UP     157 ms up 11s        | 8003 UP?  miss 2/3 (timeout)
18:37:29 #20 | 8001 UP       6 ms up 40s        | 8002 UP       5 ms up 12s        | 8003 SLOW   818 ms up 2s          << 8003 UP->SLOW
18:37:31 #21 | 8001 UP       3 ms up 42s        | 8002 UP       3 ms up 14s        | 8003 SLOW   808 ms up 4s
18:37:33 #22 | 8001 UP       4 ms up 44s        | 8002 UP       4 ms up 16s        | 8003 SLOW   813 ms up 6s
18:37:35 #23 | 8001 UP       3 ms up 46s        | 8002 UP       3 ms up 18s        | 8003 SLOW   811 ms up 8s
18:37:37 #24 | 8001 UP       4 ms up 48s        | 8002 UP       4 ms up 20s        | 8003 SLOW   808 ms up 10s
18:37:39 #25 | 8001 UP       5 ms up 50s        | 8002 UP       4 ms up 22s        | 8003 SLOW   814 ms up 12s
18:37:41 #26 | 8001 UP       6 ms up 52s        | 8002 UP       5 ms up 24s        | 8003 SLOW   819 ms up 14s
18:37:43 #27 | 8001 UP       5 ms up 54s        | 8002 UP       4 ms up 26s        | 8003 SLOW   813 ms up 16s
18:37:45 #28 | 8001 UP       4 ms up 56s        | 8002 UP       3 ms up 28s        | 8003 SLOW   815 ms up 18s
18:37:47 #29 | 8001 UP       4 ms up 58s        | 8002 UP       3 ms up 30s        | 8003 SLOW   813 ms up 20s
18:37:49 #30 | 8001 UP       5 ms up 60s        | 8002 UP       4 ms up 32s        | 8003 SLOW   817 ms up 22s
```

### Differences from step 3

- **Rounds 7-8:** 8002 shows `UP?` with 1 and 2 misses. The monitor noticed the failures but held off on reporting DOWN.
- **Round 9:** Third miss in a row → 8002 finally marked DOWN. Real outage still gets caught, just ~6.5s after it was stopped instead of ~2s in step 3.
- **Round 14:** 8002 jumps straight to UP on first good response. `up 0s` = fresh restart.
- **Rounds 18-19:** The 8003 swap only caused 2 misses, which is below the threshold, so 8003 was **never shown as DOWN** this time. In step 3 the same swap showed DOWN for 3 rounds. At round 20 it went straight from UP to SLOW (818ms, `up 2s`).
- **Round 19:** 8001 and 8002 took 157-182ms and the round started a second late (:28 instead of :27). The machine was busy launching the new Python process for 8003. Still under 500ms though.
- **No false alarm this time.** The hiccup that caused round 25's false DOWN in step 3 would only show up as `SLOW?  miss 1/3 (timeout)` here.

### Why I picked timeout = 1.5s

It needs to be between the SLOW cutoff and the interval:

- Has to be **over 500ms**, otherwise a slow service can never respond in time and looks identical to a dead one. My slow copy responds in ~810ms so I wanted good margin. 1.5s gives about 700ms of room.
- Has to be **under 2s**, otherwise a round can take longer than the interval, the next round starts late, and the output stops coming every 2s.

| | Short timeout (like 0.6s) | Long timeout (like 5s) |
|---|---|---|
| **Pro** | Detects hangs/network issues faster. Rounds finish quickly. | Slow-but-alive services correctly show as SLOW instead of DOWN. Fewer false alarms. |
| **Con** | Slow services get wrongly classified as DOWN. The 810ms service would fail almost every time. | Each failed check wastes the full timeout. Real outages take longer to detect. Doesn't fit in a 2s round. |

The false alarm at step 3 round 25 showed the downside of a tight margin – the slow service's 810ms response occasionally pushes past 1.5s. A bigger timeout would prevent that but would also slow down detection of real outages. I kept 1.5s and let the fail threshold handle occasional misses.

Side note: timeout mostly matters when a service *hangs* (no response at all). On Linux, connecting to a closed port gets refused instantly. On Windows it retries for ~2.3s before giving up, so the timeout actually gets hit (see step 3 discussion).

### Why I picked N = 3

With interval = 2s, timeout = 1.5s, and N misses needed:

- **Detection time** is roughly (N-1) × 2s + (time until next check) + 1.5s. For N=3 that's about **5.5 to 7.5s**. The step 4 run measured ~6.5s.
- **Shortest catchable outage** is about (N-1) × 2s = 4s. Anything shorter just shows as `UP?  miss 1/3`.

Why not other values:

- **N=1** (step 3): fastest detection (~2s) but every hiccup triggers a false DOWN. Got one in just 60 seconds.
- **N=2:** Would've still caught the 8003 swap as DOWN since it caused exactly 2 misses.
- **N=5:** ~10s+ detection time, way too slow for a status dashboard.
- **N=3:** Filters out random blips (dropped packet, GC pause, quick restart) but still catches real outages in a few seconds.

Quick math to show why it matters: say a healthy service randomly fails 1% of checks. With N=1 that's a false alarm every 100 checks → roughly **every 3.3 minutes**. With N=3 you need 3 consecutive failures: 0.01³ = one in a million → about **once every 23 days**. Real outages aren't random – they fail *every* check, so they still hit 3 misses fast.

| | Small N | Large N |
|---|---|---|
| **Pro** | Fast detection. Short outages visible. | Way fewer false alarms. Blips don't scare anyone. |
| **Con** | False alarms from random hiccups. People stop trusting the dashboard. | Slower detection. Outages under ~(N-1)×2s never show as DOWN. |

The tradeoff with N=3 is that short outages get hidden. But the monitor still prints `miss 1/3` so you can see something happened, and the uptime resetting (like `8003 … up 2s` at round 20) reveals a restart even when the service was never marked DOWN.
