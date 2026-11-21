#!/usr/bin/env python3
"""
scripts/maintenance/dillo_stonfi_pool_tracker.py
=============================================================================
DILLO MINER STON.FI DEX POOL TRACKER & FLEET VALUATION ENGINE
=============================================================================
1. Tracks live on-chain liquidity pool on STON.fi DEX:
   - Pool Address: EQDB5_GnpdtL6pECwcp_OOJ-FmHNodOJ7sWSRAwXtO7wEo2a
   - Token Contract: EQCVW2CmirqX91LOlwIPZ9TPQwwGg9giT5dQtNwAzG7ZAUUT (DILLO)
   - Pair: DILLO / TON (EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c)
2. Computes:
   - Real-time exchange rate (DILLO -> TON & DILLO -> USD)
   - Pool liquidity depth & 24h volume
   - Fleet DILLO reserves valuation
3. Can be run standalone or invoked on cron.
=============================================================================
"""

import os
import sys
import json
import urllib.request
import logging

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, BASE_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dillo_pool_tracker")

DILLO_JETTON = "EQCVW2CmirqX91LOlwIPZ9TPQwwGg9giT5dQtNwAzG7ZAUUT"
POOL_ADDRESS = "EQDB5_GnpdtL6pECwcp_OOJ-FmHNodOJ7sWSRAwXtO7wEo2a"
STONFI_POOLS_API = "https://api.ston.fi/v1/pools"

def get_stonfi_pool_data() -> dict:
    req = urllib.request.Request(
        STONFI_POOLS_API,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            pools = data.get("pool_list", [])
            for p in pools:
                if p.get("address") == POOL_ADDRESS:
                    return p
    except Exception as e:
        logger.error(f"Error querying STON.fi API: {e}")
    return {}

def get_ton_price_usd() -> float:
    try:
        url = "https://tonapi.io/v2/rates?tokens=ton&currencies=usd"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode())
            return float(d.get("rates", {}).get("TON", {}).get("prices", {}).get("USD", 1.50))
    except Exception:
        return 1.50

def analyze_pool():
    logger.info("=" * 75)
    logger.info("⛏️ DILLO MINER STON.FI DEX POOL AUDIT & VALUATION")
    logger.info("=" * 75)

    p = get_stonfi_pool_data()
    if not p:
        logger.error("Could not find DILLO pool on STON.fi")
        return

    ton_usd = get_ton_price_usd()

    # Reserves (decimals: DILLO=9, TON=9)
    res_dillo = float(p.get("reserve0", 0)) / 1e9
    res_ton = float(p.get("reserve1", 0)) / 1e9
    lp_usd = float(p.get("lp_total_supply_usd", 0))
    vol_24h = float(p.get("volume_24h_usd", 0))
    apy_7d = float(p.get("apy_7d", 0)) * 100

    price_ton = res_ton / res_dillo if res_dillo > 0 else 0.0
    price_usd = price_ton * ton_usd

    logger.info(f"🏊 Pool Address: {POOL_ADDRESS}")
    logger.info(f"💎 TON Reserve: {res_ton:,.2f} TON (${res_ton * ton_usd:,.2f} USD)")
    logger.info(f"🪙 DILLO Reserve: {res_dillo:,.0f} DILLO")
    logger.info(f"🌊 Total Liquidity: ${lp_usd:,.2f} USD")
    logger.info(f"📈 24h Volume: ${vol_24h:,.2f} USD | 7d APY: {apy_7d:.1f}%")
    logger.info(f"💲 1 DILLO = {price_ton:.10f} TON (${price_usd:.10f} USD)")
    logger.info(f"💲 1,000,000 DILLO = {price_ton * 1e6:.4f} TON (${price_usd * 1e6:.4f} USD)")

    # Read fleet DILLO balances from state
    try:
        from scripts.maintenance.dillo_referral_validator import call_dillo, load_data
        tokens, _ = load_data()
        m_tok = tokens.get("6727787768", {}).get("dillo_init_data")
        if m_tok:
            st = call_dillo(m_tok, "state", {})
            me = st.get("data", {}).get("me", {})
            pool_bal = float(me.get("pool", 0))
            pending_bal = float(me.get("pending", 0))
            tot_master = pool_bal + pending_bal
            logger.info("-" * 75)
            logger.info(f"👑 Master Account DILLO Balance: {tot_master:,.2f} DILLO ({pool_bal:,.2f} pool + {pending_bal:,.2f} pending)")
            logger.info(f"💰 Master Valuation: {tot_master * price_ton:.6f} TON (${tot_master * price_usd:.4f} USD)")
    except Exception as e:
        logger.debug(f"Fleet balance check note: {e}")

    logger.info("=" * 75)

if __name__ == "__main__":
    analyze_pool()
