"""Kiểm các câu chữ cố định trong template.html còn đúng với số liệu mới (JSON từ analyze_social_report.py).

    python src/check_report_claims.py social-report-data.json

In từng nhận định OK/SAI kèm số; exit 1 nếu có câu SAI -> sửa câu chữ trong template rồi chạy lại trước khi build/đẩy.
Mỗi kỳ mới: câu chữ trong template đổi thì sửa danh sách kiểm ở đây theo."""
import json
import re
import sys

D = json.load(open(sys.argv[1], encoding="utf-8"))
T, R = D["total"], D["roborock_total"]
bad = 0


def find(rows, key, val):
    return next((r for r in rows if r[key] == val), {})


def pc(v, d=2):
    return f"{v * 100:.{d}f}%"


def claim(ok, text, info=""):
    global bad
    bad += not ok
    print(f"{'OK ' if ok else 'SAI'} {text} | {info}")


acc = lambda n: find(D["accounts"], "account", n)  # noqa: E731
rob_acc = lambda n: find(D["roborock_by_account"], "account", n)  # noqa: E731
angle = lambda a: find(D["angles"], "angle", a)  # noqa: E731
prod = lambda p: find(D["products"], "product", p)  # noqa: E731
grp = lambda g: find(D["groups"], "group", g)  # noqa: E731
fmt = lambda t: find(D["roborock_types"], "type", t)  # noqa: E731

# ---- Key takeaways
top10 = D["top_roborock_views"][:10]
claim(all(p["paid"] > 0 for p in top10), "Reach: 'Ten boosted posts' (top 10 bài Roborock đều có view trả phí)",
      ", ".join(f"{p['account']} {p['paid']}/{p['views']}" for p in top10))
flag = rob_acc("Roborock Flagship")
claim(flag.get("posts", 0) > 0, "Reach / Summary: có nhóm Roborock Flagship", f"{flag.get('posts')} bài, DA rate {pc(flag.get('da_rate', 0))}")
exp, gift, promo, demo = angle("Experience / event"), angle("Gift 20/10"), angle("Promo / price"), angle("Demo / feature")
claim(exp["da_rate"] > max(gift["da_rate"], promo["da_rate"]), "Content: Experience DA rate > Gift và Promo",
      f"exp {pc(exp['da_rate'])} gift {pc(gift['da_rate'])} promo {pc(promo['da_rate'])}")
claim(min(gift["views_per_post"], promo["views_per_post"]) > max(exp["views_per_post"], demo["views_per_post"]),
      "Content: Gift/Promo 'buy reach' (view/bài cao hơn Experience/Demo)",
      f"gift {gift['views_per_post']:.0f} promo {promo['views_per_post']:.0f} exp {exp['views_per_post']:.0f} demo {demo['views_per_post']:.0f}")
claim(gift["organic_share"] < .5 and promo["organic_share"] < .5, "Content: Gift/Promo phần lớn trả phí",
      f"paid gift {pc(1 - gift['organic_share'], 0)} promo {pc(1 - promo['organic_share'], 0)}")
claim(demo["da_rate"] > gift["da_rate"], "Action: Demo DA rate > Gift", f"{pc(demo['da_rate'])} vs {pc(gift['da_rate'])}")
branded = sum(b["posts"] for b in D["brands"] if b["brand"] != "Unbranded / generic")
claim(R["posts"] / branded > .9, "Share: Roborock chiếm phần lớn bài floor care có brand", pc(R["posts"] / branded, 1))
comp = D["competitor_accounts"]
claim(all(acc(a["account"]).get("roborock_posts", 0) > 0 for a in comp), "Share: bài đối thủ đều từ cửa hàng đa brand (có cả bài Roborock)",
      " · ".join(f"{a['account']} {a['posts']}" for a in comp[:5]))

# ---- 1. Network
reel, post = fmt("Reel"), fmt("Post")
claim(reel["posts"] / R["posts"] > .5, "Network: 'Reels carry the network'", pc(reel["posts"] / R["posts"], 0))
claim(reel["views_per_post"] < post["views_per_post"] and reel["da_rate"] > post["da_rate"],
      "Network: Reel ít view/bài hơn Post nhưng DA rate cao hơn",
      f"vpp {reel['views_per_post']:.0f} vs {post['views_per_post']:.0f}, DA {pc(reel['da_rate'])} vs {pc(post['da_rate'])}")

# ---- 2. Dealers
bigmi = rob_acc("BigMi")
claim(all(a["posts"] <= bigmi["posts"] and a["da"] <= bigmi["da"] for a in D["roborock_by_account"]),
      "Dealer: BigMi nhiều bài Roborock + deep action nhất ('backbone')", f"{bigmi['posts']} bài, {pc(bigmi['da'] / R['da'], 1)} DA")
cm, dl, br = grp("CM"), grp("Dealer"), grp("Brand")
claim(br["da_rate"] < min(cm["da_rate"], dl["da_rate"]) and br["views"] / T["views"] > 3 * br["posts"] / T["posts"],
      "Dealer: Flagship 'buy reach, not conversation'",
      f"Brand {pc(br['posts'] / T['posts'], 1)} bài / {pc(br['views'] / T['views'], 0)} view, DA {pc(br['da_rate'])} | CM {pc(cm['da_rate'])} | Dealer {pc(dl['da_rate'])}")

# ---- 3. Organic
other = (T["organic"] - R["organic"]) / (T["views"] - R["views"])
claim(R["organic_share"] < other, "Organic: Roborock organic share < bài khác", f"{pc(R['organic_share'], 1)} vs {pc(other, 1)}")

# ---- 4. Category & brand
xi = find(D["brands"], "brand", "Xiaomi")
xi_top = max((p for p in D["top_competitor"] if p["brand"] == "Xiaomi"), key=lambda p: p["views"], default=None)
claim(bool(xi and xi_top) and xi_top["views"] / xi["views"] > .5 and xi_top["organic"] < xi_top["views"] / 2
      and bool(re.search(r"20/10|qu[aà]", xi_top["title"], re.I)), "SOV note: view Xiaomi phần lớn từ 1 bài gift-guide trả phí",
      f"{xi_top['views'] if xi_top else 0}/{xi.get('views', 0)}")

# ---- 5. Products
models = [p for p in D["products"] if p["product"] != "Roborock (generic)"]
saros, f25s, f25u = prod("Roborock Saros 20 Flow Complete"), prod("Roborock F25 Ultra Steam Gen 2"), prod("Roborock F25 Ultra")
q2p, qe2f, gen = prod("Roborock Qrevo 2 Pro"), prod("Roborock Qrevo Edge 2 Flow"), prod("Roborock (generic)")
claim(all(p["posts"] <= saros["posts"] for p in models) and saros["da_rate"] > R["da_rate"],
      "Product: Saros 20 Flow Complete nhiều bài nhất, DA rate > TB", f"{saros['posts']} bài, {pc(saros['da_rate'])}")
claim(f25s["da_rate"] > 1.5 * R["da_rate"] and f25s["organic_share"] > R["organic_share"],
      "Product: F25 Ultra Steam Gen 2 'conversation starter'", f"DA {pc(f25s['da_rate'])}, organic {pc(f25s['organic_share'], 0)}")
claim(qe2f["da_rate"] > 2 * R["da_rate"] and qe2f["views_per_post"] < R["views_per_post"],
      "Product: Qrevo Edge 2 Flow under-amplified", f"DA {pc(qe2f['da_rate'])}, {qe2f['views_per_post']:.0f} view/bài")
claim(all(p["views"] <= f25u["views"] for p in D["products"]) and f25u["organic_share"] < .2 and f25u["da_rate"] < R["da_rate"],
      "Product: F25 Ultra nhiều view nhất, phần lớn trả phí, DA rate < TB", f"{f25u['views']} view, paid {pc(1 - f25u['organic_share'], 0)}")
claim(q2p["organic_share"] < .2 and gen["da_rate"] < R["da_rate"], "Product: Qrevo 2 Pro paid-heavy, khuyến mãi chung DA rate < TB",
      f"Q2P paid {pc(1 - q2p['organic_share'], 0)}, generic DA {pc(gen['da_rate'])}")

# ---- 7. Actions & data quality
portfolio = {a["account"] for a in D["accounts"] if a["posts"] >= 8 and a["floor_posts"] / a["posts"] < .9}
for name in ("AKIA Smart Home", "Trustlinkvn", "Điện Máy Văn Khích", "Điện máy Đức Thanh Gia Lai"):
    a = acc(name)
    claim(name in portfolio and a["roborock_posts"] / a["posts"] < .5, f"Trade: '{name}' đa ngành, ít Roborock",
          f"{a.get('posts')} bài, {a.get('roborock_posts')} Roborock")
claim(acc("Domotek").get("posts", 99) < 5, "Trade: Domotek < 5 bài", str(acc("Domotek").get("posts")))
claim(not any("giang chi" in a["account"].lower() for a in D["accounts"]), "DQ: Giang Chi không có Page")
claim(bool(D["quality"]["excluded_pages"]) and acc("Danke").get("pages") == 1,
      "DQ: đã loại Page trong EXCLUDED_PAGES, Page robot Danke Đà Nẵng còn", json.dumps(D["quality"]["excluded_pages"], ensure_ascii=False))

tpl = next((p for p in D["top_roborock_da_rate"] if p["product"] != "Roborock (generic)" and p["type"] != "Post"), None)
print("\nXem lại: bài mẫu cho đại lý ->", tpl and f"{tpl['account']} · {tpl['product']} · {tpl['type']} · {tpl['views']} view · {pc(tpl['da_rate'])}")
print(f"{bad} câu SAI" if bad else "Tất cả câu chữ cố định đúng với số liệu", f"| kéo So9 {D['quality']['pulled']}, bài ít nhất {D['quality']['min_age_days']} ngày")
sys.exit(1 if bad else 0)
