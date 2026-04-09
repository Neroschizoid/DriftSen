import requests
import time
import sys

URL = "http://localhost:8000/api/v1/predict"

def test_phase(name, inputs, expected_status=200):
    print(f"--- [TEST] {name} ---")
    try:
        r = requests.post(URL, json=inputs, timeout=2)
        if r.status_code == expected_status:
            if r.status_code == 200:
                print(f"✅ PASS: status {r.status_code} | response: {r.json()}")
            else:
                print(f"✅ PASS: (Expected error) status {r.status_code}")
            return True
        else:
            print(f"❌ FAIL: Expected {expected_status}, got {r.status_code} | response: {r.text[:100]}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ FAIL: Exception -> {e}")
        return False

def run_all_tests():
    print("⏳ WAITING FOR SERVER TO BOOT...")
    for i in range(20):
        try:
            requests.get("http://localhost:8000/docs", timeout=1)
            print("🚀 SERVER IS UP AND RUNNING!\n")
            break
        except requests.exceptions.RequestException:
            time.sleep(2)
            sys.stdout.write(".")
            sys.stdout.flush()
    else:
        print("\n❌ SERVER FAILED TO BOOT WITHIN TIMEOUT.")
        sys.exit(1)

    all_passed = True

    # PHASE 1 & 2: Valid Arrays
    all_passed &= test_phase("PHASE 1 - Normal float input", {"features": [0.1, 0.2, 0.3, 0.4, 0.5]})
    all_passed &= test_phase("PHASE 2 - Validate [1,1,1,1,1]", {"features": [1, 1, 1, 1, 1]})
    all_passed &= test_phase("PHASE 2 - Validate [0,0,0,0,0]", {"features": [0, 0, 0, 0, 0]})
    all_passed &= test_phase("PHASE 2 - Validate [5,2,3,1,0]", {"features": [5, 2, 3, 1, 0]})

    # PHASE 5: Edge Cases (Bad inputs should return 422 Unprocessable Entity for schema violations, or 500/200 if handled customly)
    # The BaseModel dictates strict structure. E.g. strings in float array == 422 Pydantic Validation Error
    print("\n[Edge cases expect 422 Unprocessable if validation fails natively]")
    test_phase("PHASE 5 - Characters array", {"features": ["a", "b"]}, expected_status=422)

    # PHASE 6: Performance Check
    print("\n--- [TEST] PHASE 6 - Performance (20 reqs) ---")
    start = time.time()
    for _ in range(20):
        requests.post(URL, json={"features": [0.1, 0.2, 0.3, 0.4, 0.5]}, timeout=2)
    dur = time.time() - start
    if dur < 5:
        print(f"✅ PASS: 20 reqs in {dur:.3f} seconds (< 5s)")
    else:
        print(f"❌ FAIL: Performance too slow: {dur:.3f} seconds")
        all_passed = False

    print("\n==============================")
    if all_passed:
        print("🎯 ALL PRE-DEPLOYMENT TESTS PASSED SUCCESFULLY!")
    else:
        print("⚠️ SOME TESTS FAILED. PLEASE REVIEW LOGS.")

if __name__ == "__main__":
    run_all_tests()
