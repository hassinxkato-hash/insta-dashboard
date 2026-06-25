#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
店舗インスタ投稿状況 取得スクリプト（クラウド／GitHub Actions版）
=====================================================
GitHub Actions が毎日このスクリプトを実行し、
business_discovery で全店舗の最新投稿状況を取得して
docs/index.html（ダッシュボード）を再生成する。

トークン等は GitHub Secrets（環境変数）から読む。リポジトリには秘密を置かない。
  ACCESS_TOKEN  … 長期アクセストークン（必須）
  APP_ID        … アプリID（任意：トークン自動延長に使用）
  APP_SECRET    … app secret（任意：同上）
  IG_USER_ID    … 自社IGユーザーID（任意：空ならトークンから自動取得）
  ALERT_DAYS    … 未投稿アラートの日数（任意：既定14）

入力 : accounts.csv （列: 店舗名,エリア,インスタユーザー名,インスタURL,最終投稿日,今月の投稿数,直近の投稿内容）
出力 : docs/index.html, accounts.csv（更新）
"""

import os
import csv
import sys
import time
import datetime as dt

try:
    import requests
except ImportError:
    sys.exit("requests が必要です:  pip install requests")

HERE = os.path.dirname(os.path.abspath(__file__))
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "").strip()
APP_ID = os.environ.get("APP_ID", "").strip()
APP_SECRET = os.environ.get("APP_SECRET", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
PAGE_TOKEN = ""  # business_discovery はページトークンで叩く（#10対策）
ALERT_DAYS = int(os.environ.get("ALERT_DAYS", "14") or "14")
API_VERSION = os.environ.get("API_VERSION", "v22.0")
GRAPH = "https://graph.facebook.com/" + API_VERSION

INPUT_CSV = os.path.join(HERE, "accounts.csv")
DOCS_DIR = os.path.join(HERE, "docs")
OUTPUT_HTML = os.path.join(DOCS_DIR, "index.html")

if not ACCESS_TOKEN:
    sys.exit("環境変数 ACCESS_TOKEN が設定されていません。")


def refresh_token():
    global ACCESS_TOKEN
    if not (APP_ID and APP_SECRET):
        return
    r = requests.get(GRAPH + "/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": ACCESS_TOKEN,
    }, timeout=30).json()
    if "access_token" in r:
        ACCESS_TOKEN = r["access_token"]
        print("トークンを延長しました（このランのみ有効。Secret更新は別途）。")


def resolve_ig_user_id():
    """ページを走査し、IGビジネスアカウントとそのページトークンを採用する。"""
    global IG_USER_ID, PAGE_TOKEN
    r = requests.get(GRAPH + "/me/accounts", params={
        "fields": "name,access_token,instagram_business_account",
        "access_token": ACCESS_TOKEN}, timeout=30).json()
    if "error" in r:
        sys.exit("IG User ID 取得失敗: " + r["error"].get("message", ""))
    for page in r.get("data", []):
        iba = page.get("instagram_business_account")
        if not iba:
            continue
        # IG_USER_ID が未指定なら最初のIGビジネスアカウントを採用
        if not IG_USER_ID or IG_USER_ID == iba["id"]:
            IG_USER_ID = iba["id"]
            PAGE_TOKEN = page.get("access_token") or ""
            return IG_USER_ID
    sys.exit("FacebookページにInstagramビジネスアカウントが連携されていません。")


def fetch_account(username):
    fields = ("business_discovery.username(" + username +
              "){name,username,media_count,media{timestamp,caption}}")
    token = PAGE_TOKEN or ACCESS_TOKEN
    r = requests.get(GRAPH + "/" + IG_USER_ID,
                     params={"fields": fields, "access_token": token},
                     timeout=30).json()
    if "error" in r:
        return {"error": r["error"].get("message", "取得失敗")}
    bd = r.get("business_discovery", {})
    name = bd.get("name") or bd.get("username") or username
    media = bd.get("media", {}).get("data", [])
    if not media:
        return {"name": name, "last": "", "count": 0, "content": ""}
    latest = media[0]
    last_ts = latest.get("timestamp", "")[:10]
    content = (latest.get("caption", "") or "").replace("\n", " ")[:60]
    now = dt.date.today()
    ym = "{:04d}-{:02d}".format(now.year, now.month)
    count = sum(1 for m in media if m.get("timestamp", "")[:7] == ym)
    return {"name": name, "last": last_ts, "count": count, "content": content}


def build_dashboard(records):
    import json
    data_json = json.dumps(records, ensure_ascii=False)
    n = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    stamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}".format(n.year, n.month, n.day, n.hour, n.minute)
    html = DASHBOARD_TEMPLATE.replace("/*__DATA__*/", data_json)
    html = html.replace("__ALERT_DAYS__", str(ALERT_DAYS))
    html = html.replace("__UPDATED__", stamp + " (JST)")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    refresh_token()
    resolve_ig_user_id()
    print("IG User ID:", IG_USER_ID)

    with open(INPUT_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    col = {c: i for i, c in enumerate(header)}

    records, ok, ng = [], 0, 0
    for row in body:
        user = row[col["インスタユーザー名"]].strip()
        if not user:
            continue
        res = fetch_account(user)
        if "error" in res:
            ng += 1
            print("NG ", user, res["error"])
        else:
            ok += 1
            row[col["店舗名"]] = res["name"]
            row[col["最終投稿日"]] = res["last"]
            row[col["今月の投稿数"]] = res["count"]
            row[col["直近の投稿内容"]] = res["content"]
            print("OK ", user, res["name"], res["last"], res["count"])
        records.append({
            "name": row[col["店舗名"]] or user,
            "area": row[col["エリア"]],
            "user": user,
            "url": "https://www.instagram.com/" + user + "/",
            "last": row[col["最終投稿日"]],
            "content": row[col["直近の投稿内容"]],
            "count": int(row[col["今月の投稿数"]] or 0),
        })
        time.sleep(0.5)

    with open(INPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)

    build_dashboard(records)
    print("\n完了 成功", ok, "失敗", ng, "-> docs/index.html")


DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>店舗インスタ投稿ダッシュボード</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1f2430;--sub:#6b7280;--line:#e5e7eb;
--ok:#16a34a;--okbg:#dcfce7;--warn:#d97706;--warnbg:#fef3c7;--bad:#dc2626;--badbg:#fee2e2;--brand:#7c3aed;}
*{box-sizing:border-box}
body{margin:0;font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,system-ui,sans-serif;background:var(--bg);color:var(--ink);font-size:14px;}
header{background:linear-gradient(100deg,#7c3aed,#db2777);color:#fff;padding:20px 24px;}
header h1{margin:0;font-size:20px;} header p{margin:4px 0 0;opacity:.9;font-size:13px;}
.wrap{max-width:1280px;margin:0 auto;padding:20px 24px 60px;}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:18px 0;}
.toolbar input,.toolbar select{padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;font-size:13px;}
.toolbar label{font-size:12px;color:var(--sub);}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;}
.kpi .n{font-size:28px;font-weight:800;line-height:1;} .kpi .l{font-size:12px;color:var(--sub);margin-top:6px;}
.kpi.bad .n{color:var(--bad)}.kpi.ok .n{color:var(--ok)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-top:18px;overflow:hidden;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap;}
th{background:#fafafa;cursor:pointer;user-select:none;font-size:12px;color:var(--sub);position:sticky;top:0;}
td.content{white-space:normal;max-width:280px;color:var(--sub);}
tr:hover td{background:#fafbff;}
.pill{display:inline-block;padding:3px 9px;border-radius:999px;font-size:12px;font-weight:700;}
.pill.ok{background:var(--okbg);color:var(--ok)}.pill.warn{background:var(--warnbg);color:var(--warn)}.pill.bad{background:var(--badbg);color:var(--bad)}
a.ig{color:var(--brand);text-decoration:none;font-weight:600;} a.ig:hover{text-decoration:underline;}
.muted{color:var(--sub);font-size:12px;}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle;}
.upd{font-size:12px;opacity:.85;}
</style></head>
<body>
<header><h1>店舗インスタ投稿ダッシュボード</h1>
<p>アカウント名・最終投稿日・今月の投稿数・未投稿アラートをまとめて確認 <span class="upd">（最終更新: __UPDATED__）</span></p></header>
<div class="wrap">
  <div class="toolbar">
    <input type="text" id="q" placeholder="アカウント名で検索" oninput="render()">
    <select id="area" onchange="render()"><option value="">全エリア</option></select>
    <select id="status" onchange="render()">
      <option value="">全ステータス</option><option value="bad">未投稿アラートのみ</option>
      <option value="warn">投稿少なめ</option><option value="ok">良好</option></select>
    <label>アラート日数:<input type="text" id="thr" value="__ALERT_DAYS__" style="width:46px" oninput="render()"> 日以上未投稿</label>
  </div>
  <div class="kpis" id="kpis"></div>
  <div class="card"><table>
    <thead><tr>
      <th onclick="sortBy('name')">アカウント名</th><th onclick="sortBy('user')">ユーザー名</th>
      <th onclick="sortBy('area')">エリア</th><th onclick="sortBy('status')">ステータス</th>
      <th onclick="sortBy('last')">最終投稿日</th><th onclick="sortBy('days')">経過日数</th>
      <th onclick="sortBy('count')">今月の投稿数</th><th>直近の投稿内容</th><th>リンク</th>
    </tr></thead><tbody id="body"></tbody>
  </table></div>
  <div class="muted" style="margin-top:14px">
    <span class="dot" style="background:var(--ok)"></span>良好
    <span class="dot" style="background:var(--warn);margin-left:12px"></span>投稿少なめ
    <span class="dot" style="background:var(--bad);margin-left:12px"></span>未投稿アラート ／ 列見出しクリックで並び替え
  </div>
</div>
<script>
const DATA=/*__DATA__*/;
let sortKey="days",sortDir=-1;
function daysSince(d){if(!d)return 9999;const t=new Date(d+"T00:00:00");if(isNaN(t))return 9999;return Math.floor((Date.now()-t)/86400000);}
function statusOf(o){const thr=parseInt(document.getElementById('thr').value,10)||14;const d=daysSince(o.last);if(d>=thr)return"bad";if((o.count||0)<=3)return"warn";return"ok";}
const LABEL={ok:"良好",warn:"投稿少なめ",bad:"未投稿アラート"};
function initAreas(){const a=[...new Set(DATA.map(o=>o.area).filter(Boolean))].sort();
document.getElementById('area').innerHTML='<option value="">全エリア</option>'+a.map(x=>'<option>'+x+'</option>').join('');}
function rowsNow(){const q=document.getElementById('q').value.trim(),area=document.getElementById('area').value,st=document.getElementById('status').value;
let r=DATA.map(o=>({...o,days:daysSince(o.last),status:statusOf(o)}));
if(q)r=r.filter(o=>(o.name||'').includes(q)||(o.user||'').includes(q));
if(area)r=r.filter(o=>o.area===area); if(st)r=r.filter(o=>o.status===st);
r.sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(sortKey==="status"){const m={bad:0,warn:1,ok:2};x=m[a.status];y=m[b.status];}return x<y?-sortDir:x>y?sortDir:0;});return r;}
function render(){const r=rowsNow(),thr=parseInt(document.getElementById('thr').value,10)||14;
const all=DATA.map(o=>({...o,days:daysSince(o.last),status:statusOf(o)}));
const bad=all.filter(o=>o.status==="bad").length,week=all.filter(o=>o.days<=7).length,posts=all.reduce((s,o)=>s+(o.count||0),0);
document.getElementById('kpis').innerHTML='<div class="kpi"><div class="n">'+all.length+'</div><div class="l">登録店舗数</div></div>'
+'<div class="kpi ok"><div class="n">'+week+'</div><div class="l">今週投稿あり</div></div>'
+'<div class="kpi bad"><div class="n">'+bad+'</div><div class="l">未投稿アラート（'+thr+'日以上）</div></div>'
+'<div class="kpi"><div class="n">'+posts+'</div><div class="l">今月の総投稿数</div></div>';
document.getElementById('body').innerHTML=r.map(o=>'<tr>'
+'<td><b>'+(o.name||'')+'</b></td><td class="muted">@'+(o.user||'')+'</td><td>'+(o.area||'')+'</td>'
+'<td><span class="pill '+o.status+'">'+LABEL[o.status]+'</span></td>'
+'<td>'+(o.last||'<span class="muted">不明</span>')+'</td>'
+'<td>'+(o.days>=9999?'<span class="muted">—</span>':o.days+'日')+'</td>'
+'<td>'+(o.count||0)+'</td><td class="content">'+(o.content||'<span class="muted">—</span>')+'</td>'
+'<td><a class="ig" href="'+o.url+'" target="_blank">開く ↗</a></td></tr>').join('')
||'<tr><td colspan="9" class="muted" style="padding:20px">該当なし</td></tr>';}
function sortBy(k){if(sortKey===k)sortDir*=-1;else{sortKey=k;sortDir=(k==="name"||k==="area"||k==="user")?1:-1;}render();}
initAreas();render();
</script></body></html>"""


if __name__ == "__main__":
    main()
