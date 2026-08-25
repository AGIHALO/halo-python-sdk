# HALO Python SDK

The official Python client for HALO Project Authentication, Identity OAuth
Clients, Agent Access, long-term Memory, and server-driven x402 payments.

> **👼 proper noun [HALO (Hyper-Available Lifeline Oracle)]**:
> A protocol where a dormant agent receives a temporary intelligence boost ("HALO") to survive a resource crunch (402 Error).

## Installation

```bash
pip install halo-sdk
# or install from source
pip install .
```

Python 3.9 or newer is required.

## What's included in 0.4.0

- Supabase-style `create_client(url, publishable_key).auth` session management
- Project user signup, password sessions, rotating refresh tokens, recovery,
  JWKS, and upstream provider login
- Identity OAuth Client authorization-code, PKCE, refresh-token, and user-info flows
- Server-only Agent Access Link, installation, approval, execution, and revoke flows
- Direct Memory capture, retrieve, deletion, and function execution
- Server-driven x402 signing that uses the `payTo`, network, asset, amount, and
  timeout returned by `https://api.agihalo.com`

## Model Gateway

HALO exposes an OpenAI-compatible production endpoint. Use the OpenAI package
for model calls and this package for HALO Authentication, Memory, and x402
helpers.

```bash
pip install openai
```

```python
import os
from openai import OpenAI

halo = OpenAI(
    api_key=os.environ["HALO_API_KEY"],
    base_url="https://api.agihalo.com/openai/v1",
)

response = halo.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": "Reply with one word: ready"}],
)
print(response.choices[0].message.content)
```

## x402 Auto-Payment

Wrap a `google-genai` model client with `halo_system`. When the HALO API
returns 402, the wrapper signs the server-provided payment requirement and
retries the original model, contents, config, and request headers with the
payment proof.

```python
import os
from google import genai
from halo import halo_system

api_key = os.environ["HALO_API_KEY"]
client = genai.Client(
    api_key=api_key,
    http_options={"base_url": "https://api.agihalo.com"},
)

halo_model = halo_system(
    client.models,
    private_key=os.environ["HALO_WALLET_PRIVATE_KEY"],
    api_key=api_key,
)

response = halo_model.generate_content(
    model="gemini-3.5-flash",
    contents="Hello, HALO!",
)
print(response.text)
```

The SDK does not contain a platform receive-wallet constant. It signs the
`payTo` value delivered by the trusted HALO 402 response, so a server-side
wallet rotation does not require a Python package update.

## Project Authentication

Create the client once with the Project publishable key. Its `auth` member keeps
the active session, rotates refresh tokens, and automatically sends both
`apikey` and the current bearer access token.

```python
from halo import create_client

halo = create_client(
    "https://api.agihalo.com",
    "pk-project",
)

session = halo.auth.sign_in_with_password({
    "email": "user@example.com",
    "password": "Secret123!",
})
user = halo.auth.get_user()
```

Python sessions remain in memory by default. A custom mapping or storage
adapter can persist them when the client lifecycle requires it:

```python
storage = {}
halo = create_client(
    "https://api.agihalo.com",
    "pk-project",
    {
        "auth": {
            "persist_session": True,
            "storage": storage,
        }
    },
)
```

The publishable key is public application identity, not a secret. Access and
refresh tokens are bearer credentials. In a web application, keep them in a
Secure, HttpOnly, SameSite-protected application cookie behind a BFF.

The lower-level `HaloAuthClient` remains available for explicit token and PKCE
handling.

Services registered as HALO Identity OAuth Clients use `HaloOAuthClient`:

```python
from halo import HaloOAuthClient, generate_oauth_state

oauth = HaloOAuthClient(
    client_id="halo_client_...",
    client_secret="server-only-secret",
)
state = generate_oauth_state()
authorize_url = oauth.build_authorize_url(
    redirect_uri="https://service.example.com/callback",
    scopes=["profile", "email"],
    state=state,
)
tokens = oauth.exchange_code(
    code=code,
    redirect_uri="https://service.example.com/callback",
)
profile = oauth.get_user_info(tokens["access_token"])
```

## Agent Access

Use `HaloAgentAccessClient` only in the partner's trusted backend. Its API key
must never be placed in a browser. Project Authentication stays independent;
the Link request may identify a user with a verified Project access token or the
partner's own `externalUserId`.

```python
import os
from halo import HaloAgentAccessClient

access = HaloAgentAccessClient(
    api_key=os.environ["HALO_API_KEY"],
    project_key="customer-project-a",
)

link = access.create_link(
    client_agent_id="service-uuid",
    end_user={"type": "external", "externalUserId": "partner-user-123"},
    required_capabilities=[{
        "capability": "calendar.event.read",
        "resourceSelectors": [{"type": "calendar", "ids": ["primary"]}],
    }],
    optional_capabilities=[],
    return_url="https://app.example.com/halo/complete",
    state="partner-csrf-state",
)

# Send link["connectUrl"] to the browser. After HALO returns, query from the
# trusted backend and take installationId only from this response.
completed = access.get_link_session(link["session"]["id"])
installation_id = completed["session"]["installationId"]
```

Create/write capabilities first create an input-bound approval, wait for the My
Agent owner to approve it in `/my-agent/access`, and then execute with
`approval_id`.

```python
approval = access.create_approval(
    installation_id=installation_id,
    function_id="google.calendar.event.create",
    input={"calendarId": "primary", "summary": "Partner demo"},
    idempotency_key="calendar-create-operation-uuid",
)

result = access.execute(
    installation_id=installation_id,
    function_id="google.calendar.event.create",
    input={"calendarId": "primary", "summary": "Partner demo"},
    idempotency_key="calendar-create-operation-uuid",
    approval_id=approval["approval"]["id"],
)
```

Partners do not register a Connected App OAuth Client with HALO. HALO owns and
operates Connected App OAuth, token custody, incremental consent, allowlisted
capability adapters, and audit. Raw Connected App tokens are never returned.

## Long-Term Memory

For new integrations, use `HaloMemoryClient` directly. The memory client does not read API keys or project keys from environment variables; pass them explicitly from your server configuration.

The memory project must already exist in Halo. `project_key` is the memory project key, not the Halo API key. `end_user_key` is your customer-side end-user id and is required.

```python
from halo import HaloMemoryClient

memory = HaloMemoryClient(
    api_key="sk-...",
    project_key="customer-project-a",
)

# Add this declaration to your own LLM request tools/functions.
memory_function = memory.function_declaration()
```

When your model returns a `halo_retrieve_end_user_memory` function call, execute it with Halo:

```python
halo_result = memory.execute_retrieve_function(
    end_user_key="end-user-123",
    session_data={
        "messages": [
            {
                "role": "user",
                "content": "What should I follow up on today?",
            }
        ],
        "currentTask": "answering user question",
    },
    limit=5,
)

# Feed this back to your LLM as the tool/function response.
tool_response = halo_result["functionResponse"]
```

After your LLM produces the final assistant answer, capture the exchange:

```python
memory.capture(
    end_user_key="end-user-123",
    session_data={
        "messages": [
            {
                "role": "user",
                "content": "What should I follow up on today?",
            }
        ],
    },
    response={
        "role": "assistant",
        "content": "You asked me to follow up on your weekly report draft.",
    },
)
```

You can also inspect memory directly without model function calling:

```python
memory.retrieve(
    end_user_key="end-user-123",
    topics=["report_preferences"],
    limit=5,
)

memory.delete_topic(
    end_user_key="end-user-123",
    topic_key="report_preferences",
    include_raw=False,
)
```

Legacy router/proxy integrations can still use `halo_memory_headers` on proxied model requests:

```python
from halo import halo_memory_headers

headers = halo_memory_headers(
    project_key="customer-project-a",
    end_user_key="end-user-123",
    mode="capture",
)

# Pass `headers` through your provider client's per-request headers option.
```

`session_key` is optional legacy metadata and is not used as Halo's retrieval index. `retrieve=True` is the legacy router mode. It asks Halo to inject compact memory context and the function declaration into the proxied model request. New integrations should prefer user-side function declaration plus direct function API execution.

### OEM Service connections (Preview)

Confirm that the connector rollout is enabled for your project before exposing
this flow.

```python
memory.register_oauth_provider(
    provider_key="google",
    client_id="google-oauth-client-id",
    client_secret="google-oauth-client-secret",
    redirect_uri=(
        "https://connect.your-oem.com/"
        "api/v1/memory/oauth/callback/google"
    ),
)

result = memory.start_oauth(
    scope_id="memory-scope-uuid",
    connector_id="google.calendar",
    completion_mode="mobile_deep_link",
    return_uri="your-oem-app://oauth/complete",
)
```

HALO keeps provider tokens server-side. The OEM receives connection state and
capability IDs, not upstream access or refresh tokens.

See the complete guides at [docs.agihalo.com](https://docs.agihalo.com/).

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
- `HALO_API_KEY`: Your HALO client key. Create one at [app.agihalo.com](https://app.agihalo.com/).
- `HALO_PROXY_URL`: Halo Proxy URL (default: `https://api.agihalo.com`).

## Architecture

1.  **Halo System (Auto Mode)**:
    *   Wraps the model instance with a Proxy.
    *   Intercepts `402 Payment Required` errors.
    *   Uses the payment recipient and settlement parameters returned by the HALO API instead of a wallet embedded in the SDK.
    *   Retries the original model request with `Payment-Signature`; it does not replace the requested model.
    *   **Fast Track**: If `private_key` is provided directly, it skips the Judge and immediately signs/pays (latency optimized).
    *   **Rescue Track**: If configured without a direct key (e.g., using a signer callback), it consults the Judge first.

2.  **Halo Payment Tools (Manual Mode)**:
    *   `consult_judge(context, amount)`: Uses `x-halo-rescue` header to access the Judge model for free.
    *   `sign_payment(requirement)`: Generates an EIP-712 signature for USDC TransferWithAuthorization.
