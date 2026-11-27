# Lab Assignment 3: The Exam Scheduler Service

**Course:** BSWE 4123 - Distributed Software Systems Laboratory  

---

## 1. Setup & Execution Instructions

### A. Environment Dependencies
Install the required packages using:
```bash
pip install -r requirements.txt
```

### B. Running the Services on Separate Ports

1. **Terminal 1: Start Room Booking Service (Port 8000)**
   ```bash
   DELAY=0.0 uvicorn room_booking_service:app --port 8000
   ```

2. **Terminal 2: Start Exam Scheduler Service (Port 8001)**
   ```bash
   ROOM_SERVICE_URL="http://localhost:8000" TIMEOUT=2.0 MAX_RETRIES=3 uvicorn main:app --port 8001
   ```

3. **Terminal 3: Run Automated Test Suite**
   ```bash
   python test_scheduler.py
   ```

---

## 2. Configuration Parameters (Environment Variables)

The Exam Scheduler Service reads all operational parameters from environment variables and exposes them via `GET /config`:
- `ROOM_SERVICE_URL`: Target address of the Room Booking API (default: `http://localhost:8000`).
- `TIMEOUT`: Request timeout limit in seconds (default: `2.0`).
- `MAX_RETRIES`: Maximum retry attempts for failed HTTP calls (default: `3`).

---

## 3. Step 3: Retry & Resilience Analysis

### A. Execution Log (Stopping & Restarting Room Booking Service)

```text
==================================================
 Starting Automated Tests for Exam Scheduler (Lab 3)
==================================================

--- 1. Testing GET /config ---
Status Code: 200
Response: {'room_service_url': 'http://localhost:8000', 'timeout': 2.0, 'max_retries': 3}

--- 2. Testing Retry Mechanism (Service Restart Test) ---
[Attempt 1/3] Failed to connect to Room Booking Service. Retrying in 0.5s...
[Attempt 2/3] Failed to connect to Room Booking Service. Retrying in 1.0s...
[Service Restored Successfully]
[Attempt 3/3] Connected successfully! Room R101 booked.
Status Code: 201
Total Execution Time: 2314.50 ms
Response: {'message': 'Exam scheduled successfully', 'exam_id': 'EXAM-103', 'booked_room': {'id': 'R101', 'capacity': 30}}
```

### B. Explanation of Retry Safety (Idempotency)
Retrying `PUT /bookings/{booking_id}` requests is safe because the booking creation endpoint is **idempotent**. The client generates a unique `booking_id` for the exam booking request. If a response is lost due to a network glitch or service interruption after the server processes it, re-sending the same `booking_id` with identical details returns `200 OK` without creating duplicate room bookings or causing scheduling conflicts.

---

## 4. Step 4: Delay & Timeout Trade-off Analysis

### A. Test Results Matrix

| Scenario | Room Service `DELAY` | Scheduler `TIMEOUT` | Status Code | Response Time (ms) | Operational Result |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Case 1** | `0.1s` | `2.0s` | `201 Created` | ~115 ms | Fast execution under normal low-latency conditions. |
| **Case 2** | `2.5s` | `2.0s` | `503 Service Unavailable` | ~6050 ms | Fails after retries because server delay exceeds request timeout limit. |
| **Case 3** | `1.5s` | `3.0s` | `201 Created` | ~1510 ms | Succeeds when timeout threshold is configured higher than server delay. |

### B. Trade-off Explanation
- **Short Timeout (e.g., 2.0s with high delay):** Fails fast and prevents blocking scheduler threads when a service is unreachable, but risks dropping legitimate requests during temporary server delays.
- **Long Timeout (e.g., 5.0s):** Increases request success rates during slow network conditions, but holds connections open longer during actual outages and increases user waiting time.
