import os
import time
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

app = FastAPI(
  title="Campus Room Booking Service",
  description="Room Booking API backend for Lab Assignment 2 &amp; 3",
  version="1.0.0"
  )

\# ---------------------------------------------------------
\# 1\. Simulated Delay Middleware (Step 4 Requirement)
\# ---------------------------------------------------------
DELAY = float(os.getenv("DELAY", "0.0"))

@app.middleware("http")
async def add\_simulated\_delay(request, call\_next):
if DELAY &gt; 0:
time.sleep(DELAY)
response = await call\_next(request)
return response

\# ---------------------------------------------------------
\# 2\. Pydantic Models
\# ---------------------------------------------------------
class Room(BaseModel):
  id: str = Field(..., examples=["B205"])
  building: str = Field(min\_length=1, examples=["Building B"])
  capacity: int = Field(gt=0, le=500, examples=)

class BookingIn(BaseModel):
  room\_id: str
  day: str = Field(..., examples=["Monday"])
  start\_hour: int = Field(ge=8, le=20)
  end\_hour: int = Field(ge=8, le=20)
  purpose: str = Field(min\_length=1, max\_length=200)

class Booking(BookingIn):
  id: str

\# ---------------------------------------------------------
\# 3\. In-Memory Database Store
\# ---------------------------------------------------------
rooms: Dict[str, Room] = {
  "R101": Room(id="R101", building="Building A", capacity=30),
  "B205": Room(id="B205", building="Building B", capacity=50),
  "C301": Room(id="C301", building="Building C", capacity=120),
  }

bookings: Dict[str, Booking] = {}

\# ---------------------------------------------------------
\# 4\. Helper Functions &amp; Endpoints
\# ---------------------------------------------------------
def overlaps(a: BookingIn, b: BookingIn) -&gt; bool:
return (
  a.room\_id == b.room\_id
and a.day == b.day
  and a.start\_hour &lt; b.end\_hour
and b.start\_hour &lt; a.end\_hour
)

@app.get("/rooms", response\_model=List[Room])
def list\_rooms():
return list(rooms.values())

@app.get("/rooms/{room\_id}", response\_model=Room)
def get\_room(room\_id: str):
if room\_id not in rooms:
raise HTTPException(status.HTTP\_404\_NOT\_FOUND, f"Room {room\_id} not found")
return rooms[room\_id]

@app.get("/bookings", response\_model=List[Booking])
def list\_bookings():
return list(bookings.values())

@app.put("/bookings/{booking\_id}", response\_model=Booking)
def put\_booking(booking\_id: str, data: BookingIn, response: Response):
"""Idempotent Booking Creation / Update."""
existing = bookings.get(booking\_id)
if existing is not None:
  if BookingIn(\*\*existing.model\_dump(exclude={"id"})) == data:
    response.status\_code = status.HTTP\_200\_OK
    return existing
    raise HTTPException(
    status.HTTP\_409\_CONFLICT,
    f"Booking id {booking\_id} is already used for a different booking",
    )

if data.room\_id not in rooms:
raise HTTPException(status.HTTP\_404\_NOT\_FOUND, f"Room {data.room\_id} not found")

if data.end\_hour &lt;= data.start\_hour:
raise HTTPException(status.HTTP\_422\_UNPROCESSABLE\_ENTITY, "end\_hour must be after start\_hour")

for other in bookings.values():
  if overlaps(data, other):
    raise HTTPException(
      status.HTTP\_409\_CONFLICT,
    f"Room {data.room\_id} is already booked during this time",
    )

booking = Booking(id=booking\_id, \*\*data.model\_dump())
bookings[booking\_id] = booking
response.status\_code = status.HTTP\_201\_CREATED
return booking

@app.get("/bookings/{booking\_id}", response\_model=Booking)
def get\_booking(booking\_id: str):
if booking\_id not in bookings:
raise HTTPException(status.HTTP\_404\_NOT\_FOUND, f"Booking {booking\_id} not found")
return bookings[booking\_id]

@app.delete("/bookings/{booking\_id}", status\_code=status.HTTP\_204\_NO\_CONTENT)
def delete\_booking(booking\_id: str):
if booking\_id not in bookings:
raise HTTPException(status.HTTP\_404\_NOT\_FOUND, f"Booking {booking\_id} not found")
    del bookings[booking_id]
