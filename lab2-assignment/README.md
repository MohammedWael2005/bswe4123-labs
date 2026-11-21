# Lab Assignment 2 – Campus Room Booking Service

A FastAPI REST service for booking university rooms. Two bookings of the same room on the
same day may never overlap (10–12 and 12–13 are allowed, since a booking ends exactly when
the next starts).

## Files

| File | Purpose |
|------|---------|
| `main.py` | The FastAPI service (Pydantic models, in-memory storage) |
| `test_bookings.py` | httpx client that runs every success and error case |
| `requirements.txt` | Dependencies |

## How to run

```bash
pip install -r requirements.txt
uvicorn main:app            # terminal 1
python test_bookings.py     # terminal 2
```

Data is stored in memory, so restart the server before re-running the client script.
Interactive docs: http://127.0.0.1:8000/docs

Two rooms are pre-loaded: `B205` (building B, capacity 30) and `A101` (building A, capacity 12).

## Step 1 – API design

**Room body:** `{"id": "C310", "building": "C", "capacity": 40}`
(`id` = one capital letter + three digits, `capacity` 1–500)

**Booking body:** `{"room_id": "B205", "day": "2026-11-24", "start_hour": 10, "end_hour": 12, "purpose": "Study group"}`
(`start_hour`/`end_hour` between 8 and 20, `end_hour` > `start_hour`, `purpose` not empty)

| # | Operation | Method | URI | Request body | Success | Errors |
|---|-----------|--------|-----|--------------|---------|--------|
| 1 | List all rooms | GET | `/rooms` | – | 200 OK | – |
| 2 | Add a room | POST | `/rooms` | Room | 201 Created | 409 room id already exists, 422 invalid data |
| 3 | Get one room | GET | `/rooms/{room_id}` | – | 200 OK | 404 unknown room |
| 4 | List a room's bookings (optional `?day=YYYY-MM-DD`) | GET | `/rooms/{room_id}/bookings` | – | 200 OK | 404 unknown room, 422 invalid `day` |
| 5 | Create a booking (id chosen by client, safe to retry) | PUT | `/bookings/{booking_id}` | Booking | 201 Created (new) / 200 OK (identical retry) | 404 unknown room, 409 overlaps an existing booking, 409 id already used for a different booking, 422 invalid data |
| 6 | Get one booking | GET | `/bookings/{booking_id}` | – | 200 OK | 404 unknown booking |
| 7 | Cancel a booking | DELETE | `/bookings/{booking_id}` | – | 204 No Content | 404 unknown booking |

## Step 2 – Implementation notes

- Validation is done by Pydantic, so FastAPI answers **422** automatically. The rule
  "end hour must be after start hour" is a `model_validator` on `BookingIn`; hours outside
  8–20 are rejected with `Field(ge=8, le=20)`.
- Unknown rooms and bookings raise `HTTPException(404)`.
- Overlap check: two bookings of the same room on the same day overlap when
  `a.start < b.end and b.start < a.end`. Treating the hours as half-open intervals is what makes
  10–12 and 12–13 legal. An overlap returns **409 Conflict**.

## Step 3 – Client script output

Output of `python test_bookings.py` against a freshly started server:

```
=== Rooms ===
[OK  ] 200 (expected 200)  GET /rooms  - list rooms
[OK  ] 201 (expected 201)  POST /rooms  - create room C310
[OK  ] 409 (expected 409)  POST /rooms  - create room C310 again
[OK  ] 422 (expected 422)  POST /rooms  - create room with capacity 0
[OK  ] 200 (expected 200)  GET /rooms/B205  - get room B205
[OK  ] 404 (expected 404)  GET /rooms/Z999  - get unknown room Z999

=== Bookings ===
[OK  ] 201 (expected 201)  PUT /bookings/a1ab52d6-3235-4baa-b75f-717452f94841  - book B205 10-12
[OK  ] 201 (expected 201)  PUT /bookings/1da8fd67-fa6d-4481-98da-6f7c4cb0e654  - book B205 12-13 (touches, no overlap)
[OK  ] 409 (expected 409)  PUT /bookings/ccd2704e-81a5-40e7-8c5c-82b99cc0b7d9  - book B205 11-14 (overlaps)
[OK  ] 201 (expected 201)  PUT /bookings/95d4df09-1a9e-4716-9101-20b115aabc8a  - book A101 11-14 (other room, fine)
[OK  ] 404 (expected 404)  PUT /bookings/9ef11c8d-a113-4f51-b919-a47d363aae7c  - book unknown room Z999
[OK  ] 422 (expected 422)  PUT /bookings/d172df27-d994-47eb-9135-3898ad16f8d0  - end hour before start hour
[OK  ] 422 (expected 422)  PUT /bookings/83f6b05d-3d87-4e0b-a690-0ba60e3452b0  - start hour before 8:00
[OK  ] 422 (expected 422)  PUT /bookings/10e7ea30-b51b-418e-bd1f-2754411a7c12  - end hour after 20:00
[OK  ] 422 (expected 422)  PUT /bookings/c1f730d3-d76a-478f-90d2-3660274cbb15  - empty purpose
[OK  ] 200 (expected 200)  GET /bookings/a1ab52d6-3235-4baa-b75f-717452f94841  - get booking
[OK  ] 404 (expected 404)  GET /bookings/does-not-exist  - get unknown booking
[OK  ] 200 (expected 200)  GET /rooms/B205/bookings  - list B205 bookings on the day
       -> [(10, 12), (12, 13)]
[OK  ] 404 (expected 404)  GET /rooms/Z999/bookings  - list bookings of unknown room
[OK  ] 204 (expected 204)  DELETE /bookings/1da8fd67-fa6d-4481-98da-6f7c4cb0e654  - delete booking
[OK  ] 404 (expected 404)  DELETE /bookings/1da8fd67-fa6d-4481-98da-6f7c4cb0e654  - delete it again

=== Step 4: safe retry (same PUT sent twice) ===
[OK  ] 201 (expected 201)  PUT /bookings/20d41d31-1f0e-4f0f-8fba-33ecb50e5333  - first attempt
[OK  ] 200 (expected 200)  PUT /bookings/20d41d31-1f0e-4f0f-8fba-33ecb50e5333  - retry, same id + same body
       -> same booking returned: True
       -> bookings with id 20d41d31-1f0e-4f0f-8fba-33ecb50e5333: 1
[OK  ] 409 (expected 409)  PUT /bookings/20d41d31-1f0e-4f0f-8fba-33ecb50e5333  - same id, different body
```

## Step 4 – Making booking creation safe to retry

**Problem.** With `POST /bookings` the server picks the id. If the app sends the request, the
server creates the booking, and the reply is lost (bad Wi-Fi, timeout), the app cannot tell
whether it worked. If it sends the POST again, the server sees a brand-new request and creates
a second booking. POST is not idempotent.

**Design: `PUT /bookings/{booking_id}` with an id chosen by the client.**

1. Before the first attempt, the app generates a UUID for the booking (for example
   `20d41d31-...`) and keeps it until it gets a reply.
2. It sends `PUT /bookings/<that uuid>` with the booking body. Every retry uses the **same** id.
3. The server handles the id like this:
   - **id not seen before** → check the room and overlaps, store the booking, reply **201 Created**.
   - **id exists and the body is identical** → this is a retry. Nothing new is stored; the
     server returns the existing booking with **200 OK**.
   - **id exists but the body is different** → reply **409 Conflict**, so a reused id cannot
     silently overwrite someone's booking.

Because the booking id is the key in the store, there can only ever be one booking with that id,
however many times the request arrives. That makes the operation idempotent, which is exactly
what HTTP defines PUT to be: sending the same PUT once or ten times leaves the server in the same
state.

The retry does not hit the overlap check by mistake either: the server first sees the id already
exists with the same data and returns it, instead of comparing the booking with itself and
answering 409.

**Proof.** In the Step 4 section of the output above, the same PUT is sent twice. The first
reply is `201`, the second is `200` with the same booking, and only one booking with that id
exists afterwards. Sending different data under the same id is rejected with `409`.
