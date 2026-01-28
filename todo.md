# High Impact, Medium Effort

1. Script Versioning/History
Track changes to script code over time
Allow reverting to previous versions
Show diff between versions
Why: Users make mistakes, need to track changes

2. Enhanced Execution Monitoring
Real-time execution progress (WebSocket updates)
Execution timeout controls
Resource usage monitoring (CPU, memory)
Kill running executions
Why: Better control over long-running scripts

3. Environment Variables Management
Per-script environment variables (stored encrypted)
UI to manage env vars without editing code
Support for .env files
Why: Scripts often need secrets/config

4. Advanced Scheduling
Calendar-based scheduling (not just cron)

5. Script Categories/Tags ✅
Organize scripts by tags/categories
Search/filter by tags

6. Advanced Security
Script sandboxing (Docker containers)
Resource limits per execution
Audit logging for all actions
Why: Safer execution of untrusted scripts
