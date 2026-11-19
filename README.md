# ⚡ AAA AUTO Fleet — Cloud Operations & Sweeper Runner

Autonomous headless cloud runner for the AAA AUTO mining fleet, running scheduled side-task sweepers, proactive 4-hour token refreshers, and automated disaster recovery vault snapshots on GitHub Actions public runners with unlimited free minutes.

## 🛡️ Architecture & Security Directives
- **Zero Plaintext Secrets (Rule 6)**: This repository contains **0 plaintext secrets, tokens, private keys, or sessions**. All runtime configuration is dynamically injected via GitHub Encrypted Secrets.
- **Single Source of Truth (SSOT)**: State is synchronized directly with **Turso LibSQL** (`kv_mesh`) and **Supabase PostgreSQL** (`fleet_accounts`).
- **Disaster Recovery**: Automated snapshots stream directly to the private Telegram vault channel (`@myagyai`).

## 🔄 Active Workflows
1. **`fleet_sidetask_sweeper.yml`**: Runs multi-bot harvesting, daily bonuses, tap claims, and on-chain withdrawal readiness sweeps.
2. **`proactive_token_refresher.yml`**: Refreshes WebApp tokens every 4 hours via cloud MTProto and pushes updates to Turso LibSQL, Supabase, and Cloudflare KV.
3. **`weekly_vault_snapshot.yml`**: Generates encrypted disaster recovery backups and posts them to `@myagyai`.
4. **`secret_scanning.yml`**: Scans all repository files on every push to maintain strict zero-secret hygiene.
