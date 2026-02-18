# Deploying ATMX Risk API

## Option A: VPS with Docker Compose (recommended for full stack)

Works on any VPS — DigitalOcean, Hetzner, Linode, EC2, etc.
Caddy handles TLS automatically via Let's Encrypt.

### 1. Provision a server

- **Minimum:** 2 vCPU, 4 GB RAM (DigitalOcean $24/mo, Hetzner ~$7/mo)
- Ubuntu 22.04+ with Docker and Docker Compose installed

### 2. Clone and configure

```bash
git clone <your-repo-url> /opt/atmx
cd /opt/atmx
```

Create a `.env` file:

```bash
cat > .env << 'EOF'
# REQUIRED — change all of these
POSTGRES_PASSWORD=a-strong-random-password
ADMIN_SECRET=a-strong-random-secret-for-key-management
DOMAIN=api.yourdomain.com

# OPTIONAL
BOOTSTRAP_API_KEY=atmx_sk_a_pregenerated_key_if_you_want_one
REDIS_PASSWORD=another-strong-password
EOF
```

Generate strong secrets:

```bash
# Quick way to generate random secrets
openssl rand -hex 32   # for POSTGRES_PASSWORD
openssl rand -hex 32   # for ADMIN_SECRET
```

### 3. Point DNS

Create an **A record** pointing `api.yourdomain.com` → your server's IP.
Caddy needs this to issue a TLS certificate automatically.

### 4. Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 5. Verify

```bash
# Health check
curl https://api.yourdomain.com/health

# Issue your first API key
curl -X POST "https://api.yourdomain.com/admin/api_keys?name=my-platform" \
  -H "Authorization: Bearer YOUR_ADMIN_SECRET"

# Test a pricing call with the key you just got
curl "https://api.yourdomain.com/v1/risk_price?\
h3_index=882a100d25fffff&\
risk_type=precip_heavy&\
start_time=2026-03-01T00:00:00Z&\
end_time=2026-03-02T00:00:00Z" \
  -H "Authorization: Bearer atmx_sk_..."
```

### 6. Interactive docs

Open `https://api.yourdomain.com/docs` in your browser.
Click **Authorize**, paste your API key, and try any endpoint interactively.

---

## Option B: Railway

Railway can run multi-service Docker Compose stacks. Since ATMX has 4+ services
(db, redis, settlement-oracle, market-engine, risk-api), Railway's team plan
or a project with multiple services works best.

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and init
railway login
railway init

# Deploy each service
railway up
```

You'll need to configure each service's environment variables in the Railway
dashboard to point at internal service URLs.

**Note:** Railway automatically provides HTTPS on `*.up.railway.app` domains.

---

## Option C: Fly.io

Fly works well for individual services. For the full stack, deploy each service
as a separate Fly app and use internal networking (`*.flycast`).

```bash
# From services/risk-api/
fly launch --name atmx-risk-api
fly secrets set ADMIN_SECRET=your-secret
fly secrets set MARKET_ENGINE_URL=http://atmx-market-engine.flycast:8080
fly secrets set SETTLEMENT_ORACLE_URL=http://atmx-settlement-oracle.flycast:8000
fly deploy
```

---

## Post-deploy checklist

- [ ] Health check returns `{"status": "ok"}` on `/health`
- [ ] Swagger docs load at `/docs`
- [ ] Can issue an API key via `POST /admin/api_keys`
- [ ] Can get a risk price via `GET /v1/risk_price` with the key
- [ ] Can create a contract via `POST /v1/contracts`
- [ ] Can register a webhook via `POST /v1/webhooks`
- [ ] Settlement cron is running (check logs: `docker compose logs risk-api`)
- [ ] Change `ADMIN_SECRET` from the default value
