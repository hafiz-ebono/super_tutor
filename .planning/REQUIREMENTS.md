# Requirements: Super Tutor

**Defined:** 2026-03-06
**Core Value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.

## v3.0 Requirements

Requirements for AgentOS Observability milestone. Each maps to roadmap phases.

### Integration

- [ ] **INT-01**: Backend FastAPI app wrapped with AgentOS (`base_app=app`) so existing SSE endpoints remain functional
- [ ] **INT-02**: All agents (notes, chat, research, flashcard, quiz) registered with AgentOS and given a `db=` for trace storage
- [ ] **INT-03**: Agno version confirmed and upgraded to support AgentOS if needed

### Tracing

- [ ] **TRAC-01**: All agent runs produce traces (inputs, outputs, latency) stored in SQLite
- [ ] **TRAC-02**: LLM token usage and model metadata captured per agent run
- [ ] **TRAC-03**: Errors and retry events (tenacity backoff) visible in traces
- [ ] **TRAC-04**: Traces isolated per user session (no cross-session bleed)

### Storage

- [ ] **STOR-01**: SQLite db configured for trace storage (file path configurable via env var)
- [ ] **STOR-02**: Database tables created automatically on startup (no manual migration step)

### Control Plane

- [ ] **CTRL-01**: Backend connected to AgentOS Control Plane at app.agno.com
- [ ] **CTRL-02**: Agent runs visible in Control Plane trace explorer
- [ ] **CTRL-03**: Session and cost data queryable from Control Plane UI

## Future Requirements

### Persistence (v4.0+)

- **SESS-01**: User sessions persisted in database (cross-device access)
- **SESS-02**: Session history visible in Control Plane

### Advanced Observability

- **OBS-01**: Custom dashboards for per-tutoring-mode usage breakdown
- **OBS-02**: Alerting on high error rates or cost spikes

## Out of Scope

| Feature | Reason |
|---------|--------|
| PostgreSQL for traces | SQLite sufficient for current scale; no deployment infra yet |
| User accounts / auth | Out of scope until v4.0+ |
| Third-party observability (Langfuse, LangSmith) | AgentOS native tracing preferred; no vendor lock-in |
| Custom trace dashboards | Control Plane UI covers this; no custom frontend needed in v3.0 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INT-01 | Phase 6 | Pending |
| INT-02 | Phase 6 | Pending |
| INT-03 | Phase 6 | Pending |
| TRAC-01 | Phase 6 | Pending |
| TRAC-02 | Phase 6 | Pending |
| TRAC-03 | Phase 6 | Pending |
| TRAC-04 | Phase 6 | Pending |
| STOR-01 | Phase 6 | Pending |
| STOR-02 | Phase 6 | Pending |
| CTRL-01 | Phase 7 | Pending |
| CTRL-02 | Phase 7 | Pending |
| CTRL-03 | Phase 7 | Pending |

**Coverage:**
- v3.0 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-06 after initial definition*
