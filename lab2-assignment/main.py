"""Campus Room Booking Service (BSWE4123 - Lab Assignment 2).

Run with:
    uvicorn main:app --reload
"""

from datetime import date

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

app = FastAPI(title="Campus Room Booking Service")


# ---------------------------------------------------------------- models

class Room(BaseModel):
    id: str = Field(pattern=r"^[A-Z][0-9]{3}$", examples=["B205"])
    building: str = Field(min_length=1)
    capacity: int = Field(gt=0, le=500)


class BookingIn(BaseModel):
    """What the client sends. The booking id comes from the URI (PUT)."""

    room_id: str
    day: date
    start_hour: int = Field(ge=8, le=20)
    end_hour: int = Field(ge=8, le=20)
    purpose: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_hour <= self.start_hour:
            raise ValueError("end_hour must be after start_hour")
        return self


class Booking(BookingIn):
    id: str


# ------------------------------------------------------- in-memory store

rooms: dict[str, Room] = {
    "B205": Room(id="B205", building="B", capacity=30),
    "A101": Room(id="A101", building="A", capacity=12),
}
bookings: dict[str, Booking] = {}


def get_room_or_404(room_id: str) -> Room:
    if room_id not in rooms:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Room {room_id} not found")
    return rooms[room_id]


def get_booking_or_404(booking_id: str) -> Booking:
    if booking_id not in bookings:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Booking {booking_id} not found")
    return bookings[booking_id]


def overlaps(a: BookingIn, b: BookingIn) -> bool:
    # Half-open intervals: 10-12 and 12-13 do NOT overlap.
    return (
        a.room_id == b.room_id
        and a.day == b.day
        and a.start_hour < b.end_hour
        and b.start_hour < a.end_hour
    )


# ----------------------------------------------------------------- rooms

@app.get("/rooms", response_model=list[Room])
def list_rooms():
    return list(rooms.values())


@app.post("/rooms", response_model=Room, status_code=status.HTTP_201_CREATED)
def create_room(room: Room):
    if room.id in rooms:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Room {room.id} already exists")
    rooms[room.id] = room
    return room


@app.get("/rooms/{room_id}", response_model=Room)
def get_room(room_id: str):
    return get_room_or_404(room_id)


@app.get("/rooms/{room_id}/bookings", response_model=list[Booking])
def list_room_bookings(room_id: str, day: date | None = None):
    get_room_or_404(room_id)
    result = [b for b in bookings.values() if b.room_id == room_id]
    if day is not None:
        result = [b for b in result if b.day == day]
    return sorted(result, key=lambda b: (b.day, b.start_hour))


# -------------------------------------------------------------- bookings

@app.put("/bookings/{booking_id}", response_model=Booking)
def put_booking(booking_id: str, data: BookingIn, response: Response):
    """Idempotent create: the client chooses the booking id.

    - new id                    -> booking created, 201
    - same id, same content     -> nothing new is created, 200 (safe retry)
    - same id, different content-> 409 (the id is already taken)
    """
    existing = bookings.get(booking_id)
    if existing is not None:
        if BookingIn(**existing.model_dump(exclude={"id"})) == data:
            response.status_code = status.HTTP_200_OK
            return existing
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Booking id {booking_id} is already used for a different booking",
        )

    get_room_or_404(data.room_id)

    for other in bookings.values():
        if overlaps(data, other):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Room {data.room_id} is already booked {other.start_hour}:00-"
                f"{other.end_hour}:00 on {other.day} (booking {other.id})",
            )

    booking = Booking(id=booking_id, **data.model_dump())
    bookings[booking_id] = booking
    response.status_code = status.HTTP_201_CREATED
    return booking


@app.get("/bookings/{booking_id}", response_model=Booking)
def get_booking(booking_id: str):
    return get_booking_or_404(booking_id)


@app.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_id: str):
    get_booking_or_404(booking_id)
    del bookings[booking_id]
