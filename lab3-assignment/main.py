import os
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import httpx
app = FastAPI(
  title="Exam Scheduler Service",
  description="Automated exam room scheduling service for Lab Assignment 3",
  version="1.0.0"
  )
\# ---------------------------------------------------------
\# 1\. Configuration from Environment Variables
\# ---------------------------------------------------------
ROOM\_SERVICE\_URL = os.getenv("ROOM\_SERVICE\_URL", "http://localhost:8000")
TIMEOUT = float(os.getenv("TIMEOUT", "2.0"))
MAX\_RETRIES = int(os.getenv("MAX\_RETRIES", "3"))
\# ---------------------------------------------------------
\# 2\. Pydantic Schemas
\# ---------------------------------------------------------
class ExamRequest(BaseModel):
  id: str = Field(..., examples=["EXAM-101"])
  course\_code: str = Field(..., examples=["BSWE4123"])
  day: str = Field(..., examples=["Monday"])
  start\_hour: int = Field(..., ge=8, le=20, examples=[3])
  end\_hour: int = Field(..., ge=8, le=20, examples=[4])
  students\_count: int = Field(..., ge=1, examples=[5])
  
class ConfigResponse(BaseModel):
  room\_service\_url: str
  timeout: float
  max\_retries: int

\# ---------------------------------------------------------
\# 3\. GET /config Endpoint
\# ---------------------------------------------------------
@app.get("/config", response\_model=ConfigResponse)
def get\_config():
"""Returns the environment variables configuration currently in use."""
return {
  "room\_service\_url": ROOM\_SERVICE\_URL,
"timeout": TIMEOUT,
"max\_retries": MAX\_RETRIES
}

\# ---------------------------------------------------------
\# 4\. Helper Function: HTTP Requests with Exponential Backoff
\# ---------------------------------------------------------
async def call\_with\_retry(client: httpx.AsyncClient, method: str, url: str, \*\*kwargs):
"""
Executes HTTP requests with Exponential Backoff retry mechanism.
Retries on Timeout, ConnectionError, or 5xx server errors.
Never retries on 404 or 409 status codes.
"""
backoff = 0.5 # Initial backoff delay (seconds)

for attempt in range(1, MAX\_RETRIES + 1):
  try:
    response = await client.request(method, url, \*\*kwargs)

\# Never retry client-side status errors (404 Not Found, 409 Conflict)
if response.status\_code in (404, 409):
return response
\# Retry on 5xx server errors if attempts remain
if response.status\_code &gt;= 500:
if attempt == MAX\_RETRIES:
return response
else:
return response
except (httpx.TimeoutException, httpx.ConnectError):
if attempt == MAX\_RETRIES:
raise
        
\# Exponential backoff delay
await asyncio.sleep(backoff)
backoff \*= 2

raise HTTPException(
  status\_code=status.HTTP\_503\_SERVICE\_UNAVAILABLE,
detail="Room Booking Service is unavailable after retries"
)

\# ---------------------------------------------------------
\# 5\. POST /exams Endpoint
\# ---------------------------------------------------------
@app.post("/exams", status\_code=status.HTTP\_201\_CREATED)
async def schedule\_exam(exam: ExamRequest):
  """
  Schedules an exam by fetching rooms from Room Booking Service,
  selecting the smallest free room that fits the students\_count, and booking it.
  """
  if exam.end\_hour &lt;= exam.start\_hour:
  raise HTTPException(
  status\_code=status.HTTP\_422\_UNPROCESSABLE\_ENTITY,
  detail="End hour must be greater than start hour"
  )
  async with httpx.AsyncClient(timeout=TIMEOUT) as client:
    \# Step A: Fetch rooms list from Room Booking Service
  try:
    rooms\_res = await call\_with\_retry(client, "GET", f"{ROOM\_SERVICE\_URL}/rooms")
    if rooms\_res.status\_code != 200:
    raise HTTPException(
    status\_code=status.HTTP\_503\_SERVICE\_UNAVAILABLE,
    detail="Failed to retrieve rooms from Room Booking Service"
    )
    rooms = rooms\_res.json()
    except Exception:
    raise HTTPException(
    status\_code=status.HTTP\_503\_SERVICE\_UNAVAILABLE,
    detail="Room Booking Service cannot be reached"
    )

\# Step B: Filter rooms by capacity and sort to pick the smallest suitable room
suitable\_rooms = [r for r in rooms if r.get("capacity", 0) &gt;= exam.students\_count]
suitable\_rooms.sort(key=lambda r: r.get("capacity", 0))

if not suitable\_rooms:
raise HTTPException(
  status\_code=status.HTTP\_409\_CONFLICT,
detail="No room available with sufficient capacity"
)

\# Step C: Attempt booking the rooms in ascending order of capacity
for room in suitable\_rooms:
booking\_id = f"booking-exam-{exam.id}"
booking\_payload = {
  "id": booking\_id,
"room\_id": room["id"],
  "day": exam.day,
  "start\_hour": exam.start\_hour,
"end\_hour": exam.end\_hour,
"purpose": f"Exam: {exam.course\_code}"
  }
try:
  book\_res = await call\_with\_retry(
  client,
  "PUT",
  f"{ROOM\_SERVICE\_URL}/bookings/{booking\_id}",
  json=booking\_payload
  )

if book\_res.status\_code in (200, 201):
return {
  "message": "Exam scheduled successfully",
  "exam\_id": exam.id,
  "course\_code": exam.course\_code,
"booked\_room": room,
  "booking": book\_res.json() if book\_res.content else booking\_payload
}
elif book\_res.status\_code == 409:
\# Room is occupied at this time, try the next smallest suitable room
continue
except Exception:
raise HTTPException(
  status\_code=status.HTTP\_503\_SERVICE\_UNAVAILABLE,
detail="Room Booking Service lost connection during booking attempt"
)
\# If all suitable rooms had overlapping bookings
raise HTTPException(
  status\_code=status.HTTP\_409\_CONFLICT,
detail="No free room is large enough at the requested time"
        )
