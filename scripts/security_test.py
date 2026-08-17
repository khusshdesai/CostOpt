import json
import time
import requests
import threading
import argparse

# Target server URL
TARGET_URL = "http://127.0.0.1:8000"

def run_sql_injection_checks():
    """Attempts to inject SQL characters into query parameters and endpoints."""
    print("\n--- 1. Running SQL Injection Vulnerability Scans ---")
    
    sqli_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE telemetry; --",
        "UNION SELECT NULL, NULL, NULL, NULL, NULL, NULL--",
        "test' AND 1=0 UNION SELECT 1,2,3,4,5,6--"
    ]
    
    endpoints = [
        "/api/overview",
        "/api/charts/savings",
        "/api/anomalies"
    ]
    
    success_count = 0
    for ep in endpoints:
        for payload in sqli_payloads:
            url = f"{TARGET_URL}{ep}"
            params = {"env": payload, "z_score": payload}
            try:
                # We expect either a 422 Unprocessable Entity (from FastAPI validator) 
                # or a normal response where the payload is treated as a literal string (no DB crash/leak)
                res = requests.get(url, params=params, timeout=5)
                
                # Check for SQLite errors or server 500 crashes
                if res.status_code == 500:
                    print(f"[!] Server Error (500) on {ep} with payload: {payload}")
                    print(f"    Possible SQLi trigger or unhandled database exception.")
                    success_count += 1
                elif "sqlite" in res.text.lower() or "syntax error" in res.text.lower():
                    print(f"[!] SQL Error leaking in response from {ep} for payload: {payload}")
                    success_count += 1
                else:
                    # Server handled it safely
                    pass
            except Exception as e:
                print(f"[x] Connection failed checking {url}: {e}")
                
    if success_count == 0:
        print("[+] SQL Injection checks passed: No active SQL injection vulnerabilities found.")
    else:
        print(f"[!] Warning: Found {success_count} potential SQLi issues.")

def run_cors_misconfig_check():
    """Checks for overly permissive CORS headers."""
    print("\n--- 2. Checking CORS Header Misconfigurations ---")
    url = f"{TARGET_URL}/api/overview"
    headers = {"Origin": "http://evil-attacker.com"}
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        allow_origin = res.headers.get("Access-Control-Allow-Origin")
        allow_cred = res.headers.get("Access-Control-Allow-Credentials")
        
        print(f"    Access-Control-Allow-Origin: {allow_origin}")
        print(f"    Access-Control-Allow-Credentials: {allow_cred}")
        
        if allow_origin == "*" or allow_origin == "http://evil-attacker.com":
            if allow_cred == "true":
                print("[!] Vulnerability Found: Permissive CORS with Allow-Credentials enabled!")
                print("    This allows malicious websites to perform cross-origin reads on behalf of the developer.")
            else:
                print("[w] Permissive CORS enabled (*), but credentials are not allowed. Safe for local, but check in production.")
        else:
            print("[+] CORS is configured securely.")
    except Exception as e:
        print(f"[x] CORS check failed: {e}")

def run_rate_limiting_checks(concurrency=20, total=200):
    """Sends rapid requests to check for database locking and resource exhaustion."""
    print(f"\n--- 3. Running Rate Limiting & DB Lock Checks ({total} requests) ---")
    
    failed_requests = 0
    completed_requests = 0
    lock = threading.Lock()
    
    def send_request():
        nonlocal failed_requests, completed_requests
        url = f"{TARGET_URL}/api/overview"
        try:
            res = requests.get(url, timeout=5)
            with lock:
                completed_requests += 1
                if res.status_code != 200:
                    failed_requests += 1
        except Exception:
            with lock:
                failed_requests += 1

    threads = []
    # Send bursts of threads
    for _ in range(total):
        t = threading.Thread(target=send_request)
        threads.append(t)
        
    start_time = time.time()
    for t in threads:
        t.start()
        # Cap concurrency
        while threading.active_count() > concurrency + 1:
            time.sleep(0.01)
            
    for t in threads:
        t.join()
        
    elapsed = time.time() - start_time
    print(f"    Completed {completed_requests} requests in {elapsed:.2f} seconds.")
    print(f"    Failed/Blocked Requests: {failed_requests}")
    
    if failed_requests > 0:
        print("[!] Vulnerability: System is susceptible to Denial of Service or Database Locking.")
    else:
        print("[+] System handled concurrency successfully under local load.")

def main():
    parser = argparse.ArgumentParser(description="LLM CostOpt Security Attacker & Audit Script")
    parser.add_argument("--concurrency", type=int, default=15, help="Concurrency level for stress checks")
    parser.add_argument("--total-requests", type=int, default=100, help="Total requests for stress check")
    args = parser.parse_args()
    
    print("==================================================")
    print("LLM CostOpt Security Attacker Script Starting...")
    print(f"Target: {TARGET_URL}")
    print("==================================================")
    
    run_sql_injection_checks()
    run_cors_misconfig_check()
    run_rate_limiting_checks(args.concurrency, args.total_requests)

if __name__ == "__main__":
    main()
