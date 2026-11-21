"""Client script that exercises every success and error case of the API.

Start the service first (on a fresh process, since data is kept in memory):
    uvicorn main:app
Then run:
    python test_bookings.py
"""

import uuid

import httpx

BASE_URL = "http://127.0.0.1:8000"
DAY = "2026-11-24"

client = httpx.Client(base_url=BASE_URL)


def call(label: str, method: str, url: str, expected: int, **kwargs) -> httpx.Response:
    r = client.request(method, url, **kwargs)
    mark = "OK  " if r.status_code == expected else "FAIL"
    print(f"[{mark}] {r.status_code} (expected {expected})  {method} {url}  - {label}")
    return r


def booking(start: int, end: int, room: str = "B205", purpose: str = "Study group") -> dict:
    return {"room_id": room, "day": DAY, "start_hour": start, "end_hour": end, "purpose": purpose}


print("=== Rooms ===")
call("list rooms", "GET", "/rooms", 200)
call("create room C310", "POST", "/rooms", 201,
     json={"id": "C310", "building": "C", "capacity": 40})
call("create room C310 again", "POST", "/rooms", 409,
     json={"id": "C310", "building": "C", "capacity": 40})
call("create room with capacity 0", "POST", "/rooms", 422,
     json={"id": "C311", "building": "C", "capacity": 0})
call("get room B205", "GET", "/rooms/B205", 200)
call("get unknown room Z999", "GET", "/rooms/Z999", 404)

print("\n=== Bookings ===")
id1, id2, id3 = (str(uuid.uuid4()) for _ in range(3))
call("book B205 10-12", "PUT", f"/bookings/{id1}", 201, json=booking(10, 12))
call("book B205 12-13 (touches, no overlap)", "PUT", f"/bookings/{id2}", 201,
     json=booking(12, 13))
call("book B205 11-14 (overlaps)", "PUT", f"/bookings/{str(uuid.uuid4())}", 409,
     json=booking(11, 14))
call("book A101 11-14 (other room, fine)", "PUT", f"/bookings/{id3}", 201,
     json=booking(11, 14, room="A101"))
call("book unknown room Z999", "PUT", f"/bookings/{str(uuid.uuid4())}", 404,
     json=booking(9, 10, room="Z999"))
call("end hour before start hour", "PUT", f"/bookings/{str(uuid.uuid4())}", 422,
     json=booking(14, 12))
call("start hour before 8:00", "PUT", f"/bookings/{str(uuid.uuid4())}", 422,
     json=booking(7, 9))
call("end hour after 20:00", "PUT", f"/bookings/{str(uuid.uuid4())}", 422,
     json=booking(19, 21))
call("empty purpose", "PUT", f"/bookings/{str(uuid.uuid4())}", 422,
     json=booking(15, 16, purpose=""))
call("get booking", "GET", f"/bookings/{id1}", 200)
call("get unknown booking", "GET", "/bookings/does-not-exist", 404)
r = call("list B205 bookings on the day", "GET", "/rooms/B205/bookings", 200,
         params={"day": DAY})
print("       ->", [(b["start_hour"], b["end_hour"]) for b in r.json()])
call("list bookings of unknown room", "GET", "/rooms/Z999/bookings", 404)
call("delete booking", "DELETE", f"/bookings/{id2}", 204)
call("delete it again", "DELETE", f"/bookings/{id2}", 404)

print("\n=== Step 4: safe retry (same PUT sent twice) ===")
retry_id = str(uuid.uuid4())
body = booking(16, 18, purpose="Extra lab session")
first = call("first attempt", "PUT", f"/bookings/{retry_id}", 201, json=body)
second = call("retry, same id + same body", "PUT", f"/bookings/{retry_id}", 200, json=body)
print("       -> same booking returned:", first.json() == second.json())
r = client.get("/rooms/B205/bookings", params={"day": DAY})
count = sum(1 for b in r.json() if b["id"] == retry_id)
print(f"       -> bookings with id {retry_id}: {count}")
call("same id, different body", "PUT", f"/bookings/{retry_id}", 409,
     json=booking(17, 19, purpose="Something else"))
