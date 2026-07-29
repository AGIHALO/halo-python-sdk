import base64
import json
import unittest

from halo import HaloPaymentTools
from halo.client import HaloAutoHandler


class HaloPaymentClientTest(unittest.TestCase):
    def test_payment_recipient_is_taken_from_server_requirement(self):
        tools = HaloPaymentTools(
            private_key="0x" + ("01" * 32),
            api_key="sk-test",
            halo_url="https://api.agihalo.com",
        )
        first_recipient = "0x2b8f0ba618170512a64C2E422c6e9C5B3Ed293E2"
        requirement = {
            "scheme": "exact",
            "network": "eip155:8453",
            "payTo": first_recipient,
            "maxTimeoutSeconds": 60,
            "price": {
                "amount": "1000000",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "extra": {"name": "USD Coin", "version": "2"},
            },
        }

        encoded = tools.sign_payment(requirement)
        payload = json.loads(base64.b64decode(encoded).decode("utf-8"))

        self.assertEqual(payload["accepted"], requirement)
        self.assertEqual(
            payload["payload"]["authorization"]["to"],
            first_recipient,
        )
        self.assertEqual(
            payload["payload"]["authorization"]["value"],
            "1000000",
        )

        next_recipient = "0x1111111111111111111111111111111111111111"
        requirement["payTo"] = next_recipient
        next_payload = json.loads(
            base64.b64decode(
                tools.sign_payment(requirement)
            ).decode("utf-8")
        )
        self.assertEqual(
            next_payload["payload"]["authorization"]["to"],
            next_recipient,
        )

    def test_auto_payment_retry_preserves_original_request(self):
        handler = object.__new__(HaloAutoHandler)
        captured = {}

        def generate_content(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return {"ok": True}

        result = handler._retry(
            generate_content,
            "signed-payment",
            (),
            {
                "model": "gemini-3.5-flash",
                "contents": "Keep the original request",
                "config": {
                    "temperature": 0.2,
                    "http_options": {
                        "headers": {"X-Request-ID": "request-1"}
                    },
                },
            },
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            captured["kwargs"]["model"],
            "gemini-3.5-flash",
        )
        self.assertEqual(
            captured["kwargs"]["contents"],
            "Keep the original request",
        )
        self.assertEqual(
            captured["kwargs"]["config"]["temperature"],
            0.2,
        )
        self.assertEqual(
            captured["kwargs"]["config"]["http_options"]["headers"],
            {
                "X-Request-ID": "request-1",
                "Payment-Signature": "signed-payment",
            },
        )

    def test_payment_required_header_accepts_http_header_casing(self):
        handler = object.__new__(HaloAutoHandler)
        expected = {
            "resource": {"description": "HALO model request"},
            "accepts": [{"scheme": "exact"}],
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(expected).encode("utf-8")
        ).decode("ascii")

        response = type(
            "Response",
            (),
            {"headers": {"Payment-Required": encoded}},
        )()
        error = type("PaymentRequired", (), {"response": response})()

        self.assertEqual(handler._extract_req(error), expected)

    def test_payment_network_and_timeout_are_required(self):
        tools = HaloPaymentTools(
            private_key="0x" + ("01" * 32),
            api_key="sk-test",
        )
        requirement = {
            "scheme": "exact",
            "network": "not-an-eip155-network",
            "payTo": "0x1111111111111111111111111111111111111111",
            "maxTimeoutSeconds": 60,
            "amount": "1000000",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        }

        with self.assertRaisesRegex(ValueError, "eip155"):
            tools.sign_payment(requirement)


if __name__ == "__main__":
    unittest.main()
