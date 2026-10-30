**Motivation**

Gloas changes `DepositRequests` to a progressive list without a limit. Execution requests from the EL are still decoded with the Electra type, which caps deposits at `MAX_DEPOSIT_REQUESTS_PER_PAYLOAD`, so a Gloas payload with more deposit requests than that fails to decode.

**Description**

- Decode deposit requests with `ssz.gloas.DepositRequests` from Gloas on. The wire bytes are the same; only the list limit differs
- Add a test that decodes `MAX_DEPOSIT_REQUESTS_PER_PAYLOAD + 1` deposit requests for Gloas and still rejects them pre-Gloas

**AI Assistance Disclosure**

Written with AI assistance (Claude), including the implementation, tests and description.
