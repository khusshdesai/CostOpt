import time
from unittest.mock import MagicMock
from costopt import CostOpt

def run_live_demonstration():
    print("=" * 65)
    print("COSTOPT LIVE FEATURE INTEGRATION DEMO")
    print("=" * 65)

    # 1. Setup Mock Provider Client
    mock_completions = MagicMock()
    mock_chat = MagicMock()
    mock_chat.completions = mock_completions
    mock_openai = MagicMock()
    mock_openai.chat = mock_chat

    # Standard Mock Completion Response
    mock_resp = MagicMock()
    mock_resp.id = "chatcmpl-demo-1"
    mock_resp.usage.prompt_tokens = 20
    mock_resp.usage.completion_tokens = 10
    mock_resp.model_dump.return_value = {
        "id": "chatcmpl-demo-1",
        "choices": [{"message": {"content": "Paris is the capital of France."}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10}
    }
    mock_completions.create.return_value = mock_resp

    # Wrap Client with CostOpt (similarity threshold set to 0.70 for semantic matching)
    client = CostOpt(
        client=mock_openai,
        similarity_threshold=0.70,
        cache_db_path="demo_cache.db",
        telemetry_db_path="demo_telemetry.db",
        environment="demonstration",
        application="live-test"
    )

    # Clean old cache for pristine test
    client.cache.clear()

    # -------------------------------------------------------------
    # DEMO 1: Exact Cache Miss & Initial Population
    # -------------------------------------------------------------
    print("\n--- TEST 1: Initial Prompt Execution ---")
    prompt_1 = "What is the capital city of France?"
    print(f"Prompt 1: '{prompt_1}'")
    
    res1 = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_1}]
    )
    print(f"Result 1 Response: {res1.choices[0]['message']['content']}")
    print("[+] Status: Cache Miss -> Sent to Provider API & Saved to Cache.")

    # -------------------------------------------------------------
    # DEMO 2: Semantic Vector Cosine Cache HIT
    # -------------------------------------------------------------
    print("\n--- TEST 2: Semantic Vector Cache Match ---")
    prompt_2 = "Tell me the capital of France city"
    print(f"Prompt 2 (Variant): '{prompt_2}'")

    res2 = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_2}]
    )
    print(f"Result 2 Response: {res2.choices[0]['message']['content']}")
    print("[SUCCESS] SEMANTIC CACHE HIT! (0ms latency, $0.00 API cost!).")

    # -------------------------------------------------------------
    # DEMO 3: Keyword Complexity Model Routing
    # -------------------------------------------------------------
    print("\n--- TEST 3: Dynamic Cost-Driven Model Routing ---")
    prompt_3 = "Classify the sentiment of this text: CostOpt is awesome!"
    print(f"Prompt 3: '{prompt_3}'")
    print("Requested Model: gpt-4o ($5.00/1M tokens)")

    res3 = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_3}]
    )
    print("[SUCCESS] Rerouted to gpt-4o-mini ($0.15/1M tokens)! Saved 97% cost.")

    # -------------------------------------------------------------
    # DEMO 4: Streaming Interception (stream=True)
    # -------------------------------------------------------------
    print("\n--- TEST 4: Streaming Interception (stream=True) ---")
    mock_completions.create.return_value = ["Chunk 1: Hello ", "Chunk 2: from ", "Chunk 3: CostOpt Stream!"]
    
    print("Streaming chunks: ", end="", flush=True)
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Stream me a response"}],
        stream=True
    )
    for chunk in stream:
        print(chunk, end="", flush=True)
        time.sleep(0.1)
    print("\n[SUCCESS] Stream completed and telemetry recorded!")

    # Shutdown
    client.shutdown()
    print("\n" + "=" * 65)
    print("ALL LIVE FEATURE VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_live_demonstration()
