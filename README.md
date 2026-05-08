# Trust-Aware Federated Data Economy Platform

A master’s coursework prototype for COMP6265 Data Economy.

This is not a normal CRUD app. It is a **technical data-economy component** that combines:

- federated/distributed querying over CSV, SQLite and API sources;
- metadata catalogue and schema mapping;
- ODRL-inspired policy and governance enforcement;
- source trust and PageRank-style reputation;
- cost-aware query optimisation inspired by relational optimisers;
- trust-aware conflict detection and resolution;
- query pricing with an arbitrage guard;
- audit logging as a policy duty;
- a React UI to make the algorithm visible.

## Why this project is stronger than a simple query engine

A simple query engine only fetches data. This prototype also answers questions that matter in a data economy:

1. **Can this user access this data for this purpose?**
2. **Which source should be used if the same data appears in many places?**
3. **What happens if sources disagree?**
4. **How much does the query cost internally?**
5. **How much should the user-facing query answer be priced?**
6. **Can the system explain the decision using provenance and audit logs?**

## Architecture

```text
React UI
  ↓
FastAPI Gateway
  ↓
SQL-like Parser
  ↓
Policy Engine
  ↓
Federated Cost Optimiser
  ↓
CSV / SQLite / Mock External API Connectors
  ↓
Conflict Resolver + Trust Engine
  ↓
Query Pricing Engine
  ↓
Audit Log
```

## Core algorithm

### 1. Virtual catalogue and schema mapping

Users query virtual datasets such as:

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION
```

The physical source schemas are different:

| Virtual column | CSV | SQLite | API |
|---|---|---|---|
| pair | pair_code | currency_pair | symbol |
| rate | value | official_rate | spot_rate |

The schema mapping layer hides this heterogeneity.

### 2. Governance / policy engine

The policy engine checks role, purpose, requested columns and sensitivity.

Example:

```sql
SELECT customer_email FROM orders WHERE order_id = 'O-1002'
```

For `researcher` / `research`, this is denied because `customer_email` is PII.

### 3. Source trust and PageRank reputation

Each source has:

- base trust;
- authority level;
- freshness;
- conflict risk;
- provider reputation from an endorsement graph.

The trust formula is:

```text
computed_trust = 0.42*base_trust
               + 0.28*authority_level
               + 0.18*provider_PageRank
               + 0.12*freshness_score
```

PageRank complexity:

```text
O(I * (V + E))
```

where `I` is iterations, `V` is providers and `E` is endorsement edges.

### 4. Cost-aware federated optimiser

The optimiser enumerates candidate plans:

- single source plan;
- verified multi-source plan;
- simple two-way join plan;
- join verified plan.

It estimates:

```text
estimated_execution_cost = access_cost
                          + rows_scanned * row_scan_cost
                          + api_calls * api_call_cost
                          + projection_penalty
```

Balanced score:

```text
score = cost + 0.004*latency + 0.25*api_calls
      + 0.9*conflict_risk - 1.5*trust - 0.4*freshness
```

Lower score is better.

Strategies:

- `balanced`
- `cheapest`
- `trust_first`
- `privacy_first`

### 5. Trust-aware conflict resolution

Verified mode queries all compatible sources and compares values by entity key.

Example:

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION
```

Possible source values:

| Source | Value | Trust |
|---|---:|---:|
| CSV | 105.20 | low |
| SQLite official DB | 108.40 | very high |
| API | 108.43 | high |

The resolver returns the highest trust/authority answer and shows alternatives.

### 6. Query pricing

The system separates:

- **internal execution cost**: used by the optimiser;
- **user-facing query price**: used for monetisation.

Pricing includes:

- base fee;
- selected column price;
- source premium;
- verification fee;
- conflict resolution fee;
- sensitive-column fee.

It includes a simple **arbitrage guard**: if a published view determines the requested columns, the column price is capped by that view price.

## Demo queries

### 1. Financial conflict / trust-aware resolution

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION
```

Recommended role/purpose:

```text
role = researcher
purpose = research
strategy = trust_first
```

### 2. Fruit price conflict

```sql
SELECT name, price_gbp FROM fruits WHERE name = 'apple' WITH VERIFICATION
```

Shows CSV/DB/API disagreement and chooses the trusted source.

### 3. Governance denial

```sql
SELECT customer_email FROM orders WHERE order_id = 'O-1002'
```

Run as:

```text
role = researcher
purpose = research
```

It should be denied.

Then run as:

```text
role = admin
purpose = internal_audit
```

It should be allowed.

### 4. Join plan

```sql
SELECT name, price_gbp, supplier_name FROM fruits JOIN suppliers ON supplier_id = supplier_id WHERE name = 'apple'
```

This demonstrates join candidate enumeration and left-deep style plan selection.

## Run locally with Docker

From the project root:

```bash
docker-compose up --build
```

or, on newer Docker:

```bash
docker compose up --build
```

Open:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000/docs>
- Mock API: <http://localhost:8001/docs>

## Run without Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Mock API in another terminal:

```bash
cd mock_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Frontend:

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## AWS deployment recommendation

For coursework demo, use **one EC2 instance with Docker Compose**.

Security group inbound rules:

- `22` for SSH;
- `5173` for frontend;
- `8000` for backend API;
- `8001` optional, only if you want to expose the mock provider API.

On Ubuntu EC2:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin unzip
sudo usermod -aG docker $USER
newgrp docker
unzip data_economy_final.zip
cd data_economy_final
docker compose up -d --build
```

Then open:

```text
http://<EC2_PUBLIC_IP>:5173
```

## Coursework report angle

Recommended title:

**Trust-Aware Federated Query Platform for Multi-Source Data Sharing**

Main contribution:

> We implemented a policy-aware federated data access component that integrates heterogeneous sources, estimates query execution cost, chooses plans using trust/cost trade-offs, resolves conflicting values through source reputation, prices query answers, and records auditable governance decisions.

## AI tools disclosure placeholder

Add this to your final report and edit honestly:

> We used ChatGPT as an AI-assisted development aid for design discussion, boilerplate generation, debugging and refactoring suggestions. The team reviewed, tested and modified the generated code. The main affected areas were project scaffolding, frontend layout, backend module structure and explanatory documentation. Final design decisions and validation were performed by the team.


## V4 frontend fix
The query console keeps the query result visible after execution. Earlier versions refreshed all platform metadata immediately after a query, which temporarily unmounted the React page and cleared the local result state. Use the manual Refresh button to reload audit/catalogue metadata after reviewing the result.

## Windows host to Linux VM via SSH tunnel
Forward both frontend and backend ports:

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 logesh@<vm-ip>
```

Open http://localhost:5173 in Windows and check http://localhost:8000/api/health.

#check rishi branch
