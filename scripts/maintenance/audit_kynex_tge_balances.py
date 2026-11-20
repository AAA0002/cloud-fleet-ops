import os
import sys
import asyncio
import aiohttp
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from kynex_miner import authenticate_kynex

async def check_all():
    with open('accounts.json') as f:
        accs = json.load(f)
    with open('fleet_miniapp_tokens.json') as f:
        tokens = json.load(f)
        
    async with aiohttp.ClientSession() as s:
        print(f"| # | Name | UID | Level | KNX Balance | Est. USD | Tasks |")
        print(f"|---|------|-----|-------|-------------|----------|-------|")
        total_knx = 0
        ready_count = 0
        for i, acc in enumerate(accs, 1):
            uid = str(acc['user_id'])
            name = acc.get('name', 'Unknown')
            tok_d = tokens.get(uid, {})
            init_data = tok_d.get('kynex_init_data', '')
            refresh_tok = tok_d.get('kynex_refresh_token', '')
            if not init_data and not refresh_tok:
                print(f"| {i:02d} | {name} | {uid} | No Token | - | - | - |")
                continue
            auth = await authenticate_kynex(s, init_data, refresh_tok)
            if not auth:
                print(f"| {i:02d} | {name} | {uid} | Auth Fail | - | - | - |")
                continue
            id_token = auth['id_token']
            fb_uid = auth['uid']
            async with s.get(f"https://keynex-e9511-default-rtdb.europe-west1.firebasedatabase.app/users/{fb_uid}.json?auth={id_token}") as r:
                p = await r.json() or {}
                bal = float(p.get('knxBalance', 0) or 0)
                lvl = p.get('level', 1)
                tasks = len(p.get('tasksClaimed', {}) or {})
                usd = bal * 0.00008
                total_knx += bal
                if usd >= 5.0:
                    ready_count += 1
                print(f"| {i:02d} | {name} | {uid} | Lvl {lvl} | {bal:,.1f} | ${usd:.2f} | {tasks} |")
                
        print(f"\nTotal Fleet KNX: {total_knx:,.1f} (${total_knx*0.00008:.2f} USD)")
        print(f"Accounts with >= $5.00 min threshold: {ready_count}/23")

if __name__ == '__main__':
    asyncio.run(check_all())
