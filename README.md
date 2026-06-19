# HALO Python SDK

The official Python client for Halo API, featuring **x402 auto-payment middleware** that seamlessly handles payment requirements for AI models.

> **👼 proper noun [HALO (Hyper-Available Lifeline Oracle)]**: 
> A protocol where a dormant agent receives a temporary intelligence boost ("HALO") to survive a resource crunch (402 Error).

## Installation

```bash
pip install halo-sdk
# or install from source
pip install .
```

## Quick Start: Auto-Payment (Recommended)

The easiest way to use HALO. Just wrap your existing model with `halo_system`. If a 402 error occurs, it automatically signs the payment using your private key and retries.

```python
import os
from google import genai
from halo import halo_system

# 1. Setup Client
client = genai.Client(
    api_key="sk-...", # Get your key at www.apihalo.com
    http_options={"base_url": "https://api.agihalo.com"}
)

# 2. Attach HALO System (The Magic ✨)
# Just pass your private key. 402 errors will be auto-resolved.
halo_model = halo_system(
    client.models, 
    private_key="0xYOUR_PRIVATE_KEY",
    api_key="sk-..." # Get your key at www.apihalo.com
)

# 3. Use as usual
# If credits run out, it automatically pays 1 USDC and returns the result.
response = halo_model.generate_content(
    model="gemini-2.0-flash-exp", 
    contents="Hello, Halo!"
)
print(response.text)
```

## Long-Term Memory

Memory is only enabled through the HALO SDK marker. Use `halo_memory_headers` on the proxied model request that should be captured.

The memory project must already exist in Halo. `project_key` is the memory project key, not the Halo API key. `end_user_key` is your customer-side end-user id and is required.

```python
from halo import halo_memory_headers

headers = halo_memory_headers(
    project_key="customer-project-a",
    end_user_key="end-user-123",
    mode="capture",
)

# Pass `headers` through your provider client's per-request headers option.
```

This captures the user/assistant conversation from the proxied model call. Halo stores raw conversation memory on every captured exchange, while the memory worker summarizes/classifies raw entries in batches.

For new retrieval integrations, declare `halo_retrieve_end_user_memory` in your own LLM client and execute Halo's memory API only when your model returns that function call:

```python
import requests

response = requests.post(
    "https://api.agihalo.com/api/v1/memory/functions/halo_retrieve_end_user_memory",
    headers={
        "Authorization": "Bearer sk-...",
        "Content-Type": "application/json",
    },
    json={
        "projectKey": "customer-project-a",
        "endUserKey": "end-user-123",
        "arguments": {
            "sessionData": {
                "messages": [
                    {
                        "role": "user",
                        "content": "What should I follow up on today?",
                    }
                ]
            },
            "limit": 5,
        },
    },
)
```

`session_key` is optional legacy metadata and is not used as Halo's retrieval index. If your integration does not use Halo's router, send current conversation state in `sessionData` when calling the function API.

`retrieve=True` is the legacy router mode. It asks Halo to inject compact memory context and the function declaration into the proxied model request. New integrations should prefer user-side function declaration plus direct function API execution.

## Advanced: TEE / Autonomous Agent Integration

For agents running in a Trusted Execution Environment (TEE) or those who want manual control over payments. You can use `HaloPaymentTools` as a toolset for your agent.

This enables the **Rescue Protocol**:
1. Agent hits 402.
2. Agent calls `consult_judge` (Free) to ask if it should pay.
3. If Judge says "YES", Agent calls `sign_payment` (Paid) to generate a signature.
4. Agent retries the request with the signature.

```python
from halo import HaloPaymentTools

# 1. Initialize Tools inside TEE
tools = HaloPaymentTools(
    private_key="0xTEE_PRIVATE_KEY",
    api_key="sk-...",
    halo_url="https://api.agihalo.com"
)

# 2. Agent Logic (Simulation)
try:
    # ... make API call ...
    raise Exception("402 Payment Required") # Simulated 402
except Exception as e:
    # 3. Agent decides to consult the Judge (Free Lifeline)
    print("Agent: 'I'm out of credits. Should I pay?'")
    decision = tools.consult_judge(
        context="Calculating important physics data", 
        amount_str="1.00 USDC"
    )
    
    if "YES" in decision:
        print("Agent: 'Judge approved. Signing payment...'")
        
        # 4. Generate Payment Signature
        # (In real scenario, parse 'requirement' from 402 error header)
        signature = tools.sign_payment(requirement_dict)
        
        # 5. Retry with Proof
        # retry_request(headers={"Payment-Signature": signature})
        print("Success!")
```

## Environment Variables

You can configure the SDK using environment variables:

- `HALO_WALLET_PRIVATE_KEY`: Your Ethereum private key (for signing payments).
- `HALO_API_KEY`: Your Halo API Key. **Get it at [www.apihalo.com](https://www.apihalo.com)**
- `HALO_PROXY_URL`: Halo Proxy URL (default: `https://api.agihalo.com`).

## Architecture

1.  **Halo System (Auto Mode)**:
    *   Wraps the model instance with a Proxy.
    *   Intercepts `402 Payment Required` errors.
    *   **Fast Track**: If `private_key` is provided directly, it skips the Judge and immediately signs/pays (latency optimized).
    *   **Rescue Track**: If configured without a direct key (e.g., using a signer callback), it consults the Judge first.

2.  **Halo Payment Tools (Manual Mode)**:
    *   `consult_judge(context, amount)`: Uses `x-halo-rescue` header to access the Judge model for free.
    *   `sign_payment(requirement)`: Generates an EIP-712 signature for USDC TransferWithAuthorization.
