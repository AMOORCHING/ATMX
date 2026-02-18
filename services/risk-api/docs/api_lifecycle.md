# ATMX Risk API — Full Contract Lifecycle

**Base URL:** `https://your-domain.com` (or `http://localhost:8001` locally)

Every `/v1/*` request requires: `Authorization: Bearer atmx_sk_...`

> **See also:** [Case Studies](../../../docs/case_studies.md) — 10 retroactive walkthroughs using real NOAA ASOS data from actual outdoor events.

---

## 0. Issue an API Key (operator only)

```bash
curl -X POST "https://your-domain.com/admin/api_keys?name=acme-staging" \
  -H "Authorization: Bearer YOUR_ADMIN_SECRET"
```

```json
{
  "id": "a1b2c3d4e5f6a7b8",
  "name": "acme-staging",
  "key": "atmx_sk_9f3a1c7e4b2d8f6a0e5c3b7d9f1a4c6e2b8d0f5a3c7e9b",
  "prefix": "atmx_sk_9f3a1c7e...",
  "created_at": "2026-02-17T15:00:00Z",
  "rate_limit": "default",
  "message": "Store this key securely — it will not be shown again."
}
```

Save the `key` value — you won't see it again.

---

## 1. Price Discovery

Get the exceedance probability and LMSR premium for a location + risk window.

```bash
curl "https://your-domain.com/v1/risk_price?\
h3_index=882a100d25fffff&\
risk_type=precip_heavy&\
start_time=2026-03-01T00:00:00Z&\
end_time=2026-03-02T00:00:00Z" \
  -H "Authorization: Bearer atmx_sk_9f3a1c7e..."
```

```json
{
  "h3_index": "882a100d25fffff",
  "risk_type": "precip_heavy",
  "risk_probability": 0.142,
  "confidence_interval": [0.099, 0.185],
  "suggested_premium_usd": 1.73,
  "settlement_rule": {
    "version": "v1.3",
    "oracle_source": "NOAA_ASOS",
    "threshold_mm": 12.7,
    "aggregation": "sum",
    "min_stations": 1,
    "dispute_spread_ratio": 0.2
  },
  "pricing_model": "ensemble_baseline_v1",
  "valid_until": "2026-03-01T00:05:00Z"
}
```

---

## 2. Lock in a Contract

Create a contract at the quoted price. This registers the contract in the
settlement oracle and creates an LMSR market in the engine.

```bash
curl -X POST https://your-domain.com/v1/contracts \
  -H "Authorization: Bearer atmx_sk_9f3a1c7e..." \
  -H "Content-Type: application/json" \
  -d '{
    "h3_index": "882a100d25fffff",
    "risk_type": "precip_heavy",
    "start_time": "2026-03-01T00:00:00Z",
    "end_time": "2026-03-02T00:00:00Z",
    "notional_usd": 100.0
  }'
```

```json
{
  "contract_id": "c7e2a9f1-4b3d-...",
  "h3_index": "882a100d25fffff",
  "risk_type": "precip_heavy",
  "start_time": "2026-03-01T00:00:00Z",
  "end_time": "2026-03-02T00:00:00Z",
  "notional_usd": 100.0,
  "premium_usd": 17.30,
  "settlement_rule": { "..." : "..." },
  "status": "active",
  "created_at": "2026-02-17T15:01:00Z",
  "ticker": "ATMX-882a100d25fffff-PRECIP-13MM-20260302"
}
```

---

## 3. Register a Webhook

Don't poll — register a callback URL to get POSTed when the contract settles.

```bash
curl -X POST https://your-domain.com/v1/webhooks \
  -H "Authorization: Bearer atmx_sk_9f3a1c7e..." \
  -H "Content-Type: application/json" \
  -d '{
    "callback_url": "https://your-platform.com/hooks/atmx",
    "events": ["contract.settled", "contract.disputed"],
    "secret": "whsec_your_webhook_secret"
  }'
```

```json
{
  "id": "f8a3c2e1b7d94a6e",
  "callback_url": "https://your-platform.com/hooks/atmx",
  "events": ["contract.settled", "contract.disputed"],
  "created_at": "2026-02-17T15:02:00Z",
  "active": true
}
```

---

## 4. What Happens at Expiry (automatic)

At contract expiry, the background settlement cron:

1. Detects the contract's `end_time` has passed
2. Triggers settlement against NOAA ASOS observed data
3. POSTs the result to every registered webhook

### Webhook Payload

**Headers:**
```
POST /hooks/atmx HTTP/1.1
Content-Type: application/json
X-ATMX-Event: contract.settled
X-ATMX-Delivery: a1b2c3d4e5f6
X-ATMX-Signature: sha256=7d5a8f2e...
```

**Body:**
```json
{
  "event_id": "a1b2c3d4e5f6",
  "event_type": "contract.settled",
  "timestamp": "2026-03-02T00:15:00Z",
  "contract_id": "c7e2a9f1-4b3d-...",
  "h3_index": "882a100d25fffff",
  "risk_type": "precip_heavy",
  "outcome": "YES",
  "observed_value": 15.2,
  "settled_at": "2026-03-02T00:12:00Z",
  "record_hash": "sha256:9c3f..."
}
```

### Verifying the Signature

```python
import hmac, hashlib

expected = hmac.new(
    b"whsec_your_webhook_secret",
    request_body_bytes,
    hashlib.sha256,
).hexdigest()

assert request.headers["X-ATMX-Signature"] == f"sha256={expected}"
```

---

## 5. Handling the Outcome

| Outcome    | Meaning                                  | Action                   |
|------------|------------------------------------------|--------------------------|
| `YES`      | Threshold exceeded (e.g. >12.7mm rain)   | Trigger payout to user   |
| `NO`       | Threshold not exceeded                    | No payout — retain funds |
| `DISPUTED` | Station data disagrees beyond threshold   | Hold funds pending review|

---

## 6. Polling Fallback

If you prefer polling over webhooks:

```bash
curl https://your-domain.com/v1/contracts/CONTRACT_ID/status \
  -H "Authorization: Bearer atmx_sk_9f3a1c7e..."
```

```json
{
  "contract_id": "c7e2a9f1-4b3d-...",
  "status": "settled_yes",
  "h3_index": "882a100d25fffff",
  "risk_type": "precip_heavy",
  "outcome": "YES",
  "observed_value": 15.2,
  "settled_at": "2026-03-02T00:12:00Z",
  "record_hash": "sha256:9c3f..."
}
```

---

## 7. Verify Settlement Integrity

Independently verify the settlement record's hash chain:

```bash
curl -X POST https://your-domain.com/v1/settlements/CONTRACT_ID/verify \
  -H "Authorization: Bearer atmx_sk_9f3a1c7e..." \
  -H "Content-Type: application/json" \
  -d '{"expected_hash": "sha256:9c3f..."}'
```

---

## 8. Admin: Check Key Usage

See how a key has been used (requires admin secret):

```bash
curl https://your-domain.com/admin/api_keys/KEY_ID/usage \
  -H "Authorization: Bearer YOUR_ADMIN_SECRET"
```

```json
{
  "key_id": "a1b2c3d4e5f6a7b8",
  "name": "acme-staging",
  "active": true,
  "total_requests": 247,
  "error_count": 3,
  "last_request_at": "2026-02-17T16:30:00Z",
  "endpoints": {
    "/v1/risk_price": 120,
    "/v1/contracts": 45,
    "/v1/contracts/{contract_id}/status": 80,
    "/v1/webhooks": 2
  }
}
```

---

## Error Responses

Every error returns a consistent structure:

```json
{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "The API key is invalid, revoked, or missing. Obtain a key via POST /admin/api_keys.",
    "request_id": "a1b2c3d4e5f6"
  }
}
```

| Code | Status | Meaning |
|------|--------|---------|
| `INVALID_API_KEY` | 401 | Bad or missing Bearer token |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests — check `Retry-After` header |
| `BAD_REQUEST` | 400 | Invalid parameters (bad H3 cell, invalid time window, etc.) |
| `VALIDATION_ERROR` | 422 | Request body failed schema validation — `details` array lists each field |
| `NOT_FOUND` | 404 | Contract or webhook doesn't exist |
| `UPSTREAM_ERROR` | 502 | Settlement oracle or market engine unreachable |
| `INTERNAL_ERROR` | 500 | Bug — include `request_id` when reporting |
