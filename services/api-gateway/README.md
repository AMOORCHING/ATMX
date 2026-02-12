# API Gateway

Optional thin routing layer that sits in front of `market-engine` and `settlement-oracle`.

## Responsibilities

- Request routing to downstream services
- Authentication / API key validation
- Rate limiting
- CORS handling
- Request/response logging

## Status

**Not yet implemented.** Both `market-engine` and `settlement-oracle` expose their own HTTP APIs directly. Introduce this gateway when:

1. You need unified auth across services
2. You want a single public endpoint with path-based routing
3. Rate limiting or request aggregation becomes necessary

## Candidate stack

- **Nginx / Envoy** for pure reverse-proxy use cases
- **Go net/http** for custom logic (auth, aggregation)
- **Kong / Traefik** for managed API gateway features
