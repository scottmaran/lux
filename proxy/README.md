# Proxy

A simple HTTP forward proxy used to log HTTP method/URL/status (and CONNECT targets for HTTPS).
It runs Squid and converts the access log into JSONL rows under `/logs/filtered_proxy.jsonl`.
Proxy auth is enabled so per-session/job usernames can be logged.

## Logs
- Raw access log: `/logs/squid_access.log`
- JSONL output: `/logs/filtered_proxy.jsonl`

## Notes
- HTTPS is tunneled via CONNECT; without MITM only host/port is available.
- Squid accepts any Basic auth username/password; the username is logged as `proxy_user`.
- The harness injects `session_...` or `job_...` usernames so proxy rows can be mapped
  into the filtered timeline for that run.
