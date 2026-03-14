# Weil Dropshipping on Weilchain

An end-to-end dropshipping reference that stitches together the Cerebrum Rust StepAgent, a LangGraph-powered Python backend, and a WeilWallet-integrated React frontend. Human reviewers, WeilAudit logging, MCP tool hints, and WUSD payment flows stay coordinated via Weilchain deployments so every decision is traceable.

## Architecture at a glance

- **Rust applet** (`applets/dropshipping-step-agent`): the Cerebrum StepAgent orchestrates the CartReview → RiskCheck → HumanApproval → PayWithWUSD → PlaceSupplierOrder → FulfillmentUpdate flow, collects richer execution context metadata (flow ID, customer wallet, audit trace, tool hints), and emits MCP-friendly prompts that the backend can resume after payment or human signals.
- **Python backend** (`python/`): FastAPI + LangGraph graph that plans via Ollama/OpenAI, predicts tool usage, runs the StepAgent, waits for human approval, and exposes REST hooks. WeilAudit logging records `plan_start`, `tool_selected`, `step_agent_run_result`, `human_waiting`, `payment_confirmed`, and more so every transition is auditable.
- **React frontend** (`frontend/`): a Vite shell that connects to WeilWallet, requests order creation, fetches payment intents, emits WeilAudit-friendly flow IDs, and lets reviewers trigger approval, retries, and retries while showing status/hints returned by `/orders/{flow_id}`.

## Getting started (inside WSL)

1. **Rust/Cerebrum preparation**
   - `rustup toolchain install nightly`
   - `rustup target add wasm32-unknown-unknown`
   - `cd applets/dropshipping-step-agent && cargo build --target wasm32-unknown-unknown`
   - Deploy the resulting WASM to Weilchain via the official deployment scripts or Weilchain CLI; register the MCP helper addresses and grant the applet permissions to call them. See the deployment checklist below for the recommended guardrails.
2. **Python backend**
   - `cd python`
   - `python3 -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - Configure env vars: `WEIL_RPC`, `WEIL_AUDIT_BASE`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `MERCHANT_WALLET`, `WSPD_STEP_AGENT_ADDRESS`, and any `weilliptic_sdk` credentials you need.
   - `uvicorn api:app --reload`
   - The backend logs every meaningful event to WeilAudit and exposes `/orders`, `/orders/{flow_id}`, `/orders/{flow_id}/payment-intent`, `/orders/{flow_id}/payment-confirmed`, and `/orders/{flow_id}/human-approval`.
3. **React frontend**
   - `cd frontend`
   - `npm install && npm run dev`
   - The UI uses `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`) and the WeilWallet SDK that lives on `window.WeilWallet`; switch between stub and production wallet by wrapping the connection logic around the real SDK in `frontend/src/App.tsx`.
   - Connect WeilWallet, create an order, pay with WUSD, and watch the status panel, audit URL, and human prompt update in sync with the backend.

## WeilAudit + MCP coordination

- Every planner run logs `plan_start` + `plan_result`; tool hints are recorded via `tool_selected` before invoking the StepAgent, and `step_agent_run_start`/`step_agent_run_result` cover the execution. Human approval and payment events (`human_waiting`, `human_decision`, `payment_confirmed`) follow similar structured payloads.
- Use the Python SDK to resume the StepAgent after approvals/payments (`step_agent.resume`), attach context values like `approval` via `step_agent.attach_context`, and log MCP tool metadata through WeilAudit.
- The backend exposes `audit_url` values in responses so the frontend can surface WeilAudit dashboards; replace the placeholder base with your real audit domain via `WEIL_AUDIT_BASE`.

## Deployment checklist

1. Build and deploy the Rust Cerebrum StepAgent (`cargo build --target wasm32-unknown-unknown`); publish the WASM bytecode to Weilchain, register the MCP helper addresses (catalog, risk, payment, supplier, fulfillment), and ensure the contract is authorized to call each helper step.
2. Configure the Python backend with your Weilchain RPC endpoint, deployed StepAgent contract address, WeilAudit namespace (`dropshipping`), MCP client credentials, and the merchant wallet that will receive WUSD payments.
3. Run the backend (`uvicorn api:app --reload`); validate that `/orders` returns a flow ID, `/orders/{flow_id}` reflects status/tool hints/audit URL, and `/orders/{flow_id}/payment-intent` returns the merchant wallet + amount that WeilWallet should transfer.
4. Serve the frontend (`npm run dev`) and wire WeilWallet – connect, request `/orders` creation, confirm `flow_id` + audit links, and trigger `/orders/{flow_id}/payment-confirmed` after the WUSD transfer. Use `/orders/{flow_id}/human-approval` to simulate the human stage, and watch the backend resume the StepAgent.
5. Monitor WeilAudit dashboards for `tool_event`, `plan_start`, `step_agent_run_result`, `human_waiting`, `human_decision`, `payment_confirmed`, and any MCP-related entries; each record should be correlated with the same flow ID and (ideally) the WUSD transaction hash.

## Testing and verification

- Rust: `cargo test` inside `applets/dropshipping-step-agent` with mocked MCP helpers to cover CartReview → PayWithWUSD and validate WeilAudit payloads.
- Python: automated tests can hit `/orders` and `/orders/{flow_id}/payment-confirmed` to assert LangGraph transitions, WeilAudit logging, and resumed contexts.
- Frontend: manually run the UI, connect WeilWallet, submit orders, pay WUSD, and trigger approvals/retries while watching the status dialog + audit URL change.

## Next steps

- Swap the audit stub for `weilliptic_sdk.audit.AuditClient` once credentials are provisioned.
- Replace the WeilWallet stub with the production SDK import and implement retry logic for WUSD transfers.
- Hook the backend to real Weilchain RPC endpoints (set via env vars) so MCP calls and StepAgent resumes occur on-chain.
