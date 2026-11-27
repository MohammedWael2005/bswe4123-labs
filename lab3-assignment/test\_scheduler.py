import time
import httpx

SCHEDULER\_URL = "http://localhost:8001"

def test\_get\_config():
print("\\n--- 1\. Testing GET /config ---")
try:
  response = httpx.get(f"{SCHEDULER\_URL}/config")
  print(f"Status Code: {response.status\_code}")
  print(f"Response: {response.json()}")
  except Exception as e:
    print(f"Error connecting to Exam Scheduler: {e}")

def test\_schedule\_exam\_success():
print("\\n--- 2\. Testing Successful Exam Scheduling (POST /exams) ---")
payload = {
  "id": "EXAM-101",
  "course\_code": "BSWE4123",
  "day": "Monday",
  "start\_hour": 10,
  "end\_hour": 12,
  "students\_count": 30
  }
try:
start\_time = time.perf\_counter()
response = httpx.post(f"{SCHEDULER\_URL}/exams", json=payload, timeout=10.0)
elapsed = (time.perf\_counter() - start\_time) \* 1000
print(f"Status Code: {response.status\_code}")
print(f"Response Time: {elapsed:.2f} ms")
print(f"Response: {response.json()}")
except Exception as e:
print(f"Error: {e}")

def test\_schedule\_exam\_no\_capacity():
print("\\n--- 3\. Testing Capacity Conflict / No Suitable Room (409) ---")
payload = {
  "id": "EXAM-102",
  "course\_code": "BSWE4999",
  "day": "Monday",
  "start\_hour": 10,
  "end\_hour": 12,
  "students\_count": 500 # Capacity larger than any available room
  }
try:
  response = httpx.post(f"{SCHEDULER\_URL}/exams", json=payload, timeout=10.0)
print(f"Status Code: {response.status\_code}")
print(f"Response: {response.json()}")
except Exception as e:
print(f"Error: {e}")

def test\_retry\_and\_resilience():
print("\\n--- 4\. Testing Service Resilience &amp; Retry Performance ---")
payload = {
  "id": "EXAM-103",
  "course\_code": "BSWE4123",
  "day": "Tuesday",
  "start\_hour": 14,
  "end\_hour": 16,
  "students\_count": 20
  }
start\_time = time.perf\_counter()
try:
  response = httpx.post(f"{SCHEDULER\_URL}/exams", json=payload, timeout=10.0)
elapsed = (time.perf\_counter() - start\_time) \* 1000
print(f"Status Code: {response.status\_code}")
print(f"Total Execution Time: {elapsed:.2f} ms")
print(f"Response: {response.json()}")
except Exception as e:
elapsed = (time.perf\_counter() - start\_time) \* 1000
print(f"Request Failed after {elapsed:.2f} ms: {e}")

if \_\_name\_\_ == "\_\_main\_\_":
print("==================================================")
print(" Starting Automated Tests for Exam Scheduler (Lab 3)")
print("==================================================")
test\_get\_config()
test\_schedule\_exam\_success()
test\_schedule\_exam\_no\_capacity()
test\_retry\_and\_resilience()
print("\\n==================================================")
print(" Tests Completed.")
    print("==================================================")
