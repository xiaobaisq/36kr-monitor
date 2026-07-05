#!/usr/bin/env python3
"""
36氪 RSS 监控脚本 (GitHub Actions 云端版)
每小时抓取主站文章和快讯，增量保存，生成 HTML 报告。
"""

import xml.etree.ElementTree as ET
import urllib.request
import json
import os
import sys
import io
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

TZ_BEIJING = timezone(timedelta(hours=8))

FEEDS = {
    "articles": "https://36kr.com/feed",
    "newsflash": "https://36kr.com/feed-newsflash",
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ARTICLES_FILE = os.path.join(DATA_DIR, "articles.json")
INDEX_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def fetch_feed(url):
    """抓取 RSS feed"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; 36kr-monitor/1.0)"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read().decode("utf-8")
    return ET.fromstring(data)


def parse_items(root):
    """解析 RSS items"""
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_date_str = item.findtext("pubDate", "")
        description = item.findtext("description", "")

        pub_date = None
        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S %z"]:
            try:
                pub_date = datetime.strptime(pub_date_str.strip(), fmt)
                break
            except (ValueError, AttributeError):
                continue
        if pub_date is None and pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str.strip()[:25], "%Y-%m-%d %H:%M:%S")
                pub_date = pub_date.replace(tzinfo=TZ_BEIJING)
            except:
                pass

        items.append({
            "title": title,
            "link": link,
            "time": pub_date.strftime("%m-%d %H:%M") if pub_date else pub_date_str[:16],
            "ts": pub_date.isoformat() if pub_date else pub_date_str,
            "desc": description[:300] if description else "",
        })
    return items


def load_articles():
    """加载已保存的文章"""
    if os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("articles", []), data.get("flash", [])
    return [], []


def save_articles(articles, flash):
    """保存文章（去重合并，保留最近200条）"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump({"articles": articles[:200], "flash": flash[:200],
                    "updated": datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M")},
                  f, ensure_ascii=False, indent=2)


def merge_items(old_items, new_items):
    """合并新旧文章，去重，按时间倒序"""
    seen = set()
    merged = []
    for item in new_items + old_items:
        if item["link"] not in seen:
            seen.add(item["link"])
            merged.append(item)
    merged.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return merged


def generate_html(articles, flash):
    """生成手机友好的 HTML 报告"""
    now = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M")
    article_count = len(articles)
    flash_count = len(flash)

    articles_html = ""
    for a in articles:
        articles_html += f"""
    <div class="card">
      <div class="time">{a['time']}</div>
      <a href="{a['link']}" target="_blank" class="title">{a['title']}</a>
      <div class="desc">{a['desc']}</div>
    </div>"""

    flash_html = ""
    for f in flash:
        flash_html += f"""
    <div class="card flash">
      <div class="time">{f['time']}</div>
      <a href="{f['link']}" target="_blank" class="title">{f['title']}</a>
      <div class="desc">{f['desc']}</div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>36氪监控 · {now}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f5f6f8; color: #222; line-height: 1.5;
  -webkit-text-size-adjust: 100%;
}}
.header {{
  background: linear-gradient(135deg, #1e80ff, #0b5cd6);
  color: #fff; padding: 20px 16px; position: sticky; top: 0; z-index: 10;
  text-align: center;
}}
.header h1 {{ font-size: 20px; font-weight: 700; }}
.header .info {{ font-size: 12px; opacity: 0.8; margin-top: 4px; }}
.tabs {{
  display: flex; background: #e8eaed; border-radius: 10px; margin: 12px; padding: 3px;
}}
.tab {{
  flex: 1; padding: 8px; border: none; background: none; border-radius: 8px;
  font-size: 14px; font-weight: 500; color: #666; cursor: pointer; transition: 0.2s;
}}
.tab.active {{ background: #fff; color: #1e80ff; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.container {{ padding: 0 12px 24px; }}
.card {{
  background: #fff; border-radius: 12px; padding: 14px; margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}}
.card.flash {{ background: #fffaed; border-left: 3px solid #faad14; }}
.card .time {{ font-size: 11px; color: #999; margin-bottom: 4px; }}
.card .title {{
  font-size: 15px; font-weight: 600; color: #222; text-decoration: none;
  display: block; margin-bottom: 6px; line-height: 1.4;
}}
.card.flash .title {{ color: #ad6800; font-size: 14px; }}
.card .title:active {{ opacity: 0.7; }}
.card .desc {{ font-size: 13px; color: #666; line-height: 1.6; }}
.footer {{
  text-align: center; padding: 24px 16px; color: #bbb; font-size: 12px;
}}
.stats {{
  display: flex; gap: 8px; padding: 0 12px; margin-bottom: 8px;
}}
.stat {{
  flex: 1; background: #fff; border-radius: 10px; padding: 12px; text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}}
.stat .num {{ font-size: 22px; font-weight: 700; color: #1e80ff; }}
.stat .label {{ font-size: 11px; color: #999; margin-top: 2px; }}
.refresh-tip {{ text-align: center; font-size: 11px; color: #bbb; padding: 8px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📡 36氪实时监控</h1>
  <div class="info">云端自动更新 · {now}</div>
</div>
<div class="tabs">
  <button class="tab active" onclick="showTab('articles')">📰 深度文章 ({article_count})</button>
  <button class="tab" onclick="showTab('flash')">⚡ 快讯 ({flash_count})</button>
</div>
<div class="stats">
  <div class="stat"><div class="num">{article_count}</div><div class="label">深度文章</div></div>
  <div class="stat"><div class="num">{flash_count}</div><div class="label">实时快讯</div></div>
</div>
<div class="container">
  <div id="tab-articles">{articles_html}</div>
  <div id="tab-flash" style="display:none">{flash_html}</div>
</div>
<div class="refresh-tip">⬇️ 下拉刷新页面获取最新内容</div>
<div class="footer">🚀 GitHub Actions 云端运行 · 每小时自动更新</div>
<script>
function showTab(t) {{
  document.getElementById('tab-articles').style.display = t==='articles'?'block':'none';
  document.getElementById('tab-flash').style.display = t==='flash'?'block':'none';
  document.querySelectorAll('.tab').forEach(function(b){{ b.classList.remove('active'); }});
  event.target.classList.add('active');
}}
</script>
</body>
</html>"""


def main():
    print("🔍 Fetching 36kr RSS feeds...")

    old_articles, old_flash = load_articles()

    new_articles = []
    new_flash = []

    for name, url in FEEDS.items():
        try:
            root = fetch_feed(url)
            items = parse_items(root)
            if name == "articles":
                new_articles = items
            else:
                new_flash = items
            print(f"  ✅ {name}: {len(items)} items")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    merged_articles = merge_items(old_articles, new_articles)
    merged_flash = merge_items(old_flash, new_flash)

    save_articles(merged_articles, merged_flash)

    html = generate_html(merged_articles, merged_flash)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n📄 Report generated: {INDEX_FILE}")
    print(f"   Articles: {len(merged_articles)} | Newsflash: {len(merged_flash)}")


if __name__ == "__main__":
    main()
