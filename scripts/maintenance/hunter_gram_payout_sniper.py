#!/usr/bin/env python3
"""
scripts/maintenance/hunter_gram_payout_sniper.py
=============================================================================
HUNTER MINER (@GramHtrsbot) GRAM CASHOUT SNIPER & 12H MINING COORDINATOR
=============================================================================
1. Tracks Master Account (6727787768) and worker accounts on Hunter Miner:
   - Current GRAM balance (min threshold: 0.50 GRAM)
   - Mining session expiration timer
2. As soon as mining session countdown reaches 0:
   - Dispatches on-chain withdrawal directly to Master Binance TON Vault:
     UQBPZiSvitdPU3VUyJK2mRaHVBl69xejw5aOrh1KfKA7gwDT
   - Dispatches notification to Payouts Channel (-1004402765950).
   - Instantly starts the next 12-hour mining session.
3. Supports single-run check (--once) or daemon loop (--watch).
=============================================================================
"""

import os
import sys
import json
import time
import urllib.request
import logging

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, BASE_DIR)

from hunter_miner import HunterClient, TARGET_TON_VAULT, REPORT_BOT_TOKEN, ADMIN_CHANNEL_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hunter_sniper")

MASTER_UID = "6727787768"
PAYOUT_CHANNEL_ID = os.getenv("PAYOUTS_CHANNEL_ID", "-1004402765950")

def send_payout_alert(amount: float, dest_wallet: str, tx_info: dict):
    if not REPORT_BOT_TOKEN:
        return
    text = (
        f"🎯 <b>HUNTER MINER ON-CHAIN TON PAYOUT CONFIRMED</b> 💎\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Withdrawn Amount:</b> <b>+{amount:.4f} GRAM</b> ✅\n"
        f"🏦 <b>Destination Vault:</b> <code>{dest_wallet}</code>\n"
        f"👤 <b>Account:</b> <code>Arif Hossain (👑 Master - {MASTER_UID})</code>\n"
        f"📋 <b>Receipt Details:</b> <code>{json.dumps(tx_info)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Status:</b> 🟢 <code>Direct Binance TON Vault deposit</code>"
    )
    for cid in [ADMIN_CHANNEL_ID, PAYOUT_CHANNEL_ID]:
        if not cid:
            continue
        url = f"https://api.telegram.org/bot{REPORT_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": cid,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception as e:
            logger.warning(f"Telegram alert to {cid} failed: {e}")

def check_and_snipe_account(acc: dict, tok_dict: dict):
    uid = str(acc.get("user_id") or acc.get("id"))
    name = acc.get("name", "Unknown")
    init_data = tok_dict.get("hunter_init_data") or tok_dict.get("hunter")
    cached_jwt = tok_dict.get("hunter_jwt")

    if isinstance(init_data, dict):
        init_data = init_data.get("hunter_init_data", "")

    if not init_data and not cached_jwt:
        return

    username = acc.get("username", "")

    client = HunterClient(
        uid=uid,
        name=name,
        init_data=init_data or "",
        username=username,
        jwt_token=cached_jwt or ""
    )

    if not client.authenticate():
        logger.warning(f"[{name}] Auth failed on Hunter Miner")
        return

    u_info = client.user_data or {}
    m_info = client.mining_data or {}

    wb = float(u_info.get("withdrawable_balance", 0.0) or 0.0)
    mb = float(u_info.get("mining_balance", 0.0) or 0.0)
    gb = float(u_info.get("gram_balance", 0.0) or 0.0)
    cb = float(u_info.get("coin_balance", 0.0) or 0.0)
    bal = wb if wb > 0 else (cb if cb > 0 else mb)

    is_active = bool(m_info.get("mining_active"))
    ends_in = int(m_info.get("time_remaining", 0) or 0)

    logger.info(f"[{name}] Balance: {bal:.4f} GRAM | Mining Active: {is_active} | Ends In: {ends_in}s ({ends_in/60:.1f}m)")

    # 1. Finalize finished session if needed
    if m_info.get("needs_stop"):
        stop_res = client.stop_mining()
        if stop_res.get("success"):
            m_info = client.mining_data
            logger.info(f"[{name}] 🛑 Stopped Finished Session (+{stop_res.get('reward', 0):.4f} GRAM)")

    # 2. Claim mined GRAM
    if m_info.get("can_claim"):
        cl_res = client.claim_mining()
        if cl_res.get("success"):
            c_amt = cl_res.get("claimed", 0) or cl_res.get("mined_coins", 0)
            bal += c_amt
            m_info = client.mining_data
            logger.info(f"[{name}] ⛏️ Harvested: +{c_amt:.4f} GRAM! New Bal: {bal:.4f}")

    # 3. If mining has ended/inactive and balance is >= 0.50 GRAM (official server threshold):
    if not is_active and bal >= 0.50:
        logger.info(f"[{name}] 🚨 IDLE SESSION & ELIGIBLE BALANCE DETECTED! DISPATCHING CASHOUT: {bal:.4f} GRAM -> {TARGET_TON_VAULT}")
        wd_res = client.withdraw_gram(bal, TARGET_TON_VAULT)
        logger.info(f"[{name}] Withdrawal Response: {wd_res}")
        if wd_res.get("success") or "withdraw" in str(wd_res).lower():
            send_payout_alert(bal, TARGET_TON_VAULT, wd_res)

        # Restart mining immediately
        logger.info(f"[{name}] ⛏️ Restarting 12-hour mining session...")
        start_res = client.start_mining()
        logger.info(f"[{name}] Mining Restarted: {start_res}")
    elif not is_active and (m_info.get("can_start_mining") or not m_info.get("mining_active")):
        # Just restart mining
        logger.info(f"[{name}] ⛏️ Session idle. Restarting 12-hour mining...")
        start_res = client.start_mining()
        logger.info(f"[{name}] Mining Restarted: {start_res}")

def main():
    logger.info("=" * 75)
    logger.info("🎯 HUNTER MINER CASHOUT SNIPER & MINING SESSION WATCHER")
    logger.info(f"Target Vault: {TARGET_TON_VAULT}")
    logger.info("=" * 75)

    tok_file = os.path.join(BASE_DIR, "fleet_miniapp_tokens.json")
    acc_file = os.path.join(BASE_DIR, "accounts.json")

    with open(tok_file, "r") as f:
        tokens = json.load(f)
    with open(acc_file, "r") as f:
        accounts = json.load(f)

    watch_mode = "--watch" in sys.argv

    while True:
        # Check Master Account first
        master_acc = accounts[0]
        m_uid = str(master_acc["user_id"])
        check_and_snipe_account(master_acc, tokens.get(m_uid, {}))

        # Check worker accounts
        for acc in accounts[1:]:
            uid = str(acc["user_id"])
            check_and_snipe_account(acc, tokens.get(uid, {}))

        if not watch_mode:
            break

        logger.info("Sleeping 120s before next sniper check...")
        time.sleep(120)

if __name__ == "__main__":
    main()
