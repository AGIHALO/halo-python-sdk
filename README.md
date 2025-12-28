# Halo Python SDK

The official Python client for Halo API, featuring **x402 auto-payment middleware** that can be attached to any existing AI client.

> **👼 proper noun [HALO (Hyper-Available Lifeline Oracle)]**: 
> A protocol where a dormant agent receives a temporary intelligence boost ("HALO") to survive a resource crunch (402 Error).

## Installation

```bash
pip install .
```

## Usage

You can use your existing client initialization code. Just "attach" the Halo payment handler to enable auto-payment.

### With Google Gemini SDK

```python
import google.generativeai as genai
from halo import attach_payment

# 1. Configure your client normally (point to Halo URL)
genai.configure(
    api_key="sk-halo-...", # Your Halo API Key
    transport='rest',
    client_options={'api_endpoint': 'https://api.halo.com/v1'}
)
model = genai.GenerativeModel('gemini-2.0-flash')

# 2. Attach Auto-Payment Handler (The Magic ✨)
attach_payment(
    model, 
    private_key="your-wallet-private-key", # Option A: Easiest
    api_key="sk-halo-...",                 # Required for retrying requests
    trusted_receivers=["0xHaloServerWalletAddress..."] 
)

# 3. Use as usual
# If 402 happens, it will transparently pay and retry!
response = model.generate_content("Hello world")
print(response.text)
```

## Advanced: Secure Signer Callback (Recommended for Prod)

Instead of passing your Private Key to the SDK, you can provide a `signer` callback. This allows you to use a KMS, HSM, or other secure key management systems.

```python
def my_secure_signer(tx_dict):
    """
    Sign the transaction using your secure method.
    Returns: Signed raw transaction hex string.
    """
    # Example: sign with KMS, Hardware Wallet, etc.
    print(f"Signing transaction: {tx_dict}")
    return custom_kms_sign(tx_dict)

attach_payment(
    model,
    signer=my_secure_signer,       # Pass function, NOT key
    wallet_address="0xMyAddress",  # Required for nonce lookup
    api_key="sk-halo-..."
)
```

## Advanced: HALO Protocol (Judge-Act Pattern)

When your agent runs out of credits (Brain Deadlock), the SDK automatically activates the **HALO Protocol**.
It consults a **free, system-provided Judge Model** (`gemini-2.0-flash-exp`) to decide whether to authorize the payment.
The system issues a temporary **Rescue Token** during the 402 error, which authorizes this free model call securely.

```python
from halo import attach_payment, HALOSigner

# 1. Prepare Main Model
big_brain = genai.GenerativeModel('gemini-2.0-flash-exp')

# 2. Create HALO Signer (Zero-Config)
# The system automatically provides the free judge model.
halo_signer = HALOSigner(
    private_key="your-key",
    strategy="Approve only if related to physics" # Give the judge a strategy
)

# 3. Attach
attach_payment(
    big_brain,
    signer=halo_signer,
    wallet_address="0xYourWallet",
    api_key="sk-halo-..."
)
```

## How It Works

1. `attach_payment` wraps your model instance with a Proxy.
2. It intercepts method calls (like `generate_content`).
3. If an error occurs, it checks if it's a `402 Payment Required`.
4. It extracts the payment action (USDC transfer details).
5. It executes the payment using your Key, Signer Callback, or **HALO Signer**.
6. It retries the original request with the payment proof.

# halo-python-sdk
