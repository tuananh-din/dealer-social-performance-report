"""Số liệu Social Report toàn đại lý (bài Fanpage công khai). Chỉ đọc DB. In tóm tắt + ghi JSON cho dashboard.
Chạy trong container app: PYTHONPATH=/code:/tmp python /tmp/analyze_social_report.py /tmp/social-report-data.json"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app import social  # noqa: F401
from app.db import SessionLocal
from app.social import Dealer, Product, SocialPage, SocialPost, product_matcher
from social_report_rules import account_of, angle_of, classify

START, END = date(2026, 10, 7), date(2026, 10, 20)          # 2 tuần trọn vẹn (21/10 mới có nửa ngày)
WEEKS = [("W1 · 07–13/10", date(2026, 10, 7), date(2026, 10, 13)), ("W2 · 14–20/10", date(2026, 10, 14), date(2026, 10, 20))]
TOP_N = 12


def num(p, k):
    return getattr(p, k) or 0


def summ(posts):
    s = Counter()
    for p in posts:
        rx = p.r_like + p.r_love + p.r_haha + p.r_wow + p.r_sorry + p.r_anger
        s.update(posts=1, views=p.views, organic=p.views_organic, paid=p.views_paid, reactions=rx, comments=p.comments,
                 shares=p.shares, clicks=p.clicks, da=p.comments + p.shares, engagement=rx + p.comments + p.shares + p.clicks,
                 paid_posts=1 if p.views_paid else 0, follower=p.views_follower, nonfollower=p.views_nonfollower)
    v = s["views"]
    rcs = s["reactions"] + s["comments"] + s["shares"]
    out = dict(s)
    out.update(da_rate=s["da"] / v if v else 0, er=rcs / v if v else 0, organic_share=s["organic"] / v if v else 0,
               views_per_post=v / s["posts"] if s["posts"] else 0, da_per_post=s["da"] / s["posts"] if s["posts"] else 0,
               nonfollower_share=s["nonfollower"] / (s["follower"] + s["nonfollower"]) if s["follower"] + s["nonfollower"] else 0)
    return out


def post_row(p, ctx):
    rx = p.r_like + p.r_love + p.r_haha + p.r_wow + p.r_sorry + p.r_anger
    return {"title": re.sub(r"\s+", " ", p.title or "")[:160], "link": p.permalink, "page": ctx["page"], "account": ctx["account"],
            "type": p.post_type, "product": ctx["product"], "brand": ctx["brand"], "category": ctx["category"],
            "date": p.published_at.strftime("%d/%m") if p.published_at else "", "views": p.views, "organic": p.views_organic,
            "paid": p.views_paid, "da": p.comments + p.shares, "comments": p.comments, "shares": p.shares, "reactions": rx,
            "da_rate": (p.comments + p.shares) / p.views if p.views else 0}


def main(out_path):
    with SessionLocal() as db:
        pages = {p.id: p for p in db.scalars(select(SocialPage))}
        dealers = {d.id: d.name for d in db.scalars(select(Dealer))}
        match = product_matcher(db.scalars(select(Product)).all())
        rows = [p for p in db.scalars(select(SocialPost)) if p.published_at and not p.duplicate_of
                and START <= p.published_at.date() <= END]
    ctx = {}
    for p in rows:
        pg = pages.get(p.page_id)
        acc, group = account_of(pg.name if pg else "", dealers.get(pg.dealer_id) if pg and pg.dealer_id else None)
        prod = match(p.title)
        rob = bool(prod and prod.brand == "Roborock")
        cat, brand = classify(p.title, rob)
        ctx[p.id] = {"page": (pg.name if pg else "?"), "account": acc, "group": group, "category": cat, "brand": brand,
                     "angle": angle_of(p.title),
                     "product": prod.name if rob and prod.priority < 9000 else ("Roborock (generic)" if rob else "")}

    def by(key, posts=rows):
        g = defaultdict(list)
        for p in posts:
            g[key(p)].append(p)
        return g

    total = summ(rows)
    weeks = [{"label": lab, **summ([p for p in rows if a <= p.published_at.date() <= b])} for lab, a, b in WEEKS]
    days = []
    for d in (START + timedelta(n) for n in range((END - START).days + 1)):
        day_rows = [p for p in rows if p.published_at.date() == d]
        rob_day = summ([p for p in day_rows if ctx[p.id]["brand"] == "Roborock"])
        days.append({"day": d.strftime("%d/%m"), **summ(day_rows), "rob_posts": rob_day.get("posts", 0),
                     "rob_da_rate": rob_day["da_rate"]})
    accounts = []
    for acc, ps in by(lambda p: ctx[p.id]["account"]).items():
        s = summ(ps)
        cats = Counter(ctx[p.id]["category"] for p in ps)
        floor = [p for p in ps if ctx[p.id]["category"] == "Floor care"]
        rob = [p for p in floor if ctx[p.id]["brand"] == "Roborock"]
        accounts.append({"account": acc, "group": ctx[ps[0].id]["group"], "pages": len({p.page_id for p in ps}), **s,
                         "floor_posts": len(floor), "floor_views": sum(p.views for p in floor),
                         "roborock_posts": len(rob), "roborock_views": sum(p.views for p in rob),
                         "roborock_da": sum(p.comments + p.shares for p in rob),
                         "category_posts": dict(cats)})
    accounts.sort(key=lambda a: -a["views"])
    page_rows = []
    for pid, ps in by(lambda p: p.page_id).items():
        page_rows.append({"page": ctx[ps[0].id]["page"], "account": ctx[ps[0].id]["account"], **summ(ps)})
    page_rows.sort(key=lambda a: -a["organic"])
    categories = [{"category": c, **summ(ps)} for c, ps in by(lambda p: ctx[p.id]["category"]).items()]
    categories.sort(key=lambda a: -a["views"])
    floor_posts = [p for p in rows if ctx[p.id]["category"] == "Floor care"]
    brands = [{"brand": b, **summ(ps)} for b, ps in by(lambda p: ctx[p.id]["brand"], floor_posts).items()]
    brands.sort(key=lambda a: -a["views"])
    rob_posts = [p for p in floor_posts if ctx[p.id]["brand"] == "Roborock"]
    products = [{"product": k, **summ(ps)} for k, ps in by(lambda p: ctx[p.id]["product"], rob_posts).items()]
    products.sort(key=lambda a: -a["views"])
    types = [{"type": k or "?", **summ(ps)} for k, ps in by(lambda p: p.post_type, rows).items()]
    rob_types = [{"type": k or "?", **summ(ps)} for k, ps in by(lambda p: p.post_type, rob_posts).items()]
    top = lambda ps, key, n=TOP_N: [post_row(p, ctx[p.id]) for p in sorted(ps, key=key)[:n]]  # noqa: E731
    angles = [{"angle": k, **summ(ps)} for k, ps in by(lambda p: ctx[p.id]["angle"], rob_posts).items()]
    angles.sort(key=lambda a: -a["posts"])
    groups = [{"group": k, **summ(ps)} for k, ps in by(lambda p: ctx[p.id]["group"]).items()]
    ex_danke = summ([p for p in rows if ctx[p.id]["account"] != "Danke"])
    rob_by_account = []
    for acc, ps in by(lambda p: ctx[p.id]["account"], rob_posts).items():
        rob_by_account.append({"account": acc, "group": ctx[ps[0].id]["group"], **summ(ps)})
    rob_by_account.sort(key=lambda a: -a["views"])
    data = {
        "angles": angles, "groups": groups, "ex_danke": ex_danke, "roborock_by_account": rob_by_account,
        "period": {"start": START.isoformat(), "end": END.isoformat(), "weeks": [w[0] for w in WEEKS],
                   "generated": datetime.now().strftime("%d/%m/%Y %H:%M")},
        "total": total, "weeks": weeks, "days": days, "accounts": accounts, "pages": page_rows,
        "categories": categories, "brands": brands, "products": products, "types": types, "roborock_types": rob_types,
        "roborock_total": summ(rob_posts), "floor_total": summ(floor_posts),
        "top_roborock_views": top(rob_posts, lambda p: -p.views),
        "top_roborock_da": top(rob_posts, lambda p: -(p.comments + p.shares)),
        "top_roborock_da_rate": top([p for p in rob_posts if p.views >= 1000], lambda p: -(p.comments + p.shares) / p.views),
        "top_all_views": top(rows, lambda p: -p.views),
        "top_competitor": top([p for p in floor_posts if ctx[p.id]["brand"] not in ("Roborock", "Unbranded / generic")],
                              lambda p: -p.views, 8),
        "quality": {
            "posts_in_window": len(rows), "pages": len({p.page_id for p in rows}),
            "pages_with_dealer_in_app": sum(1 for p in pages.values() if p.dealer_id),
            "posts_no_title": sum(1 for p in rows if not (p.title or "").strip()),
            "posts_zero_views": sum(1 for p in rows if not p.views),
            "views_split_mismatch": sum(1 for p in rows if p.views and p.views_organic + p.views_paid != p.views),
            "other_store_posts": sum(1 for p in rows if ctx[p.id]["category"] == "Other / store post"),
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)

    # ------------- tóm tắt để đọc
    f = lambda x: f"{x:,.0f}"  # noqa: E731
    print("TOTAL", {k: round(v, 4) if isinstance(v, float) else v for k, v in total.items()})
    for w in weeks:
        print("WEEK", w["label"], "posts", w["posts"], "views", f(w["views"]), "da", w["da"], "da_rate", round(w["da_rate"], 4))
    print("\nCATEGORIES")
    for c in categories:
        print(f"  {c['category']:20} posts {c['posts']:5} views {f(c['views']):>10} org {c['organic_share']:.0%} da {c['da']:5} "
              f"da_rate {c['da_rate']:.4f} vpp {c['views_per_post']:,.0f}")
    print("\nBRANDS in Floor care")
    for b in brands:
        print(f"  {b['brand']:20} posts {b['posts']:5} views {f(b['views']):>10} da {b['da']:5} da_rate {b['da_rate']:.4f} "
              f"org {b['organic_share']:.0%}")
    print("\nACCOUNTS")
    for a in accounts:
        print(f"  {a['account'][:26]:26} {a['group']:6} pg {a['pages']:2} posts {a['posts']:4} views {f(a['views']):>9} "
              f"org {a['organic_share']:.0%} da {a['da']:5} rate {a['da_rate']:.4f} | floor {a['floor_posts']}/{a['posts']} "
              f"rob {a['roborock_posts']} rob_views {f(a['roborock_views'])}")
    print("\nPRODUCTS (Roborock)")
    for pr in products[:25]:
        print(f"  {pr['product'][:34]:34} posts {pr['posts']:4} views {f(pr['views']):>9} da {pr['da']:4} rate {pr['da_rate']:.4f} "
              f"vpp {pr['views_per_post']:,.0f} org {pr['organic_share']:.0%}")
    print("\nTYPES all", [(t["type"], t["posts"], f(t["views"]), round(t["da_rate"], 4), round(t["views_per_post"])) for t in types])
    print("TYPES rob", [(t["type"], t["posts"], f(t["views"]), round(t["da_rate"], 4), round(t["views_per_post"])) for t in rob_types])
    print("\nTOP ORGANIC PAGES")
    for pg in page_rows[:15]:
        print(f"  {pg['page'][:40]:40} posts {pg['posts']:4} views {f(pg['views']):>9} org {f(pg['organic']):>9} "
              f"share {pg['organic_share']:.0%} da_rate {pg['da_rate']:.4f}")
    print("\nTOP ROBOROCK POSTS by views")
    for r in data["top_roborock_views"][:8]:
        print(f"  {r['views']:7} org {r['organic']:7} da {r['da']:4} {r['type']:5} {r['account'][:16]:16} {r['product'][:22]:22} | {r['title'][:70]}")
    print("TOP ROBOROCK by DA")
    for r in data["top_roborock_da"][:8]:
        print(f"  da {r['da']:4} views {r['views']:7} {r['type']:5} {r['account'][:16]:16} {r['product'][:22]:22} | {r['title'][:70]}")
    print("TOP COMPETITOR")
    for r in data["top_competitor"][:8]:
        print(f"  {r['views']:7} da {r['da']:4} {r['brand']:8} {r['account'][:16]:16} | {r['title'][:70]}")
    print("\nQUALITY", data["quality"])
    print("\nEX-DANKE", {k: round(v, 4) if isinstance(v, float) else v for k, v in ex_danke.items()})
    print("GROUPS", [(g["group"], g["posts"], f(g["views"]), round(g["organic_share"], 3), round(g["da_rate"], 4)) for g in groups])
    print("ROBOROCK TOTAL", {k: round(v, 4) if isinstance(v, float) else v for k, v in data["roborock_total"].items()})
    print("\nANGLES (Roborock posts)")
    for a in angles:
        print(f"  {a['angle']:20} posts {a['posts']:4} views {f(a['views']):>9} vpp {a['views_per_post']:7,.0f} org {a['organic_share']:.0%} "
              f"da {a['da']:4} da_rate {a['da_rate']:.4f} da/post {a['da_per_post']:.2f}")
    print("TYPES rob paid share", [(t["type"], round(1 - t["organic_share"], 2), round(t["da_per_post"], 2)) for t in rob_types])
    print("\nROBOROCK BY ACCOUNT")
    tot_da = data["roborock_total"]["da"]
    for a in rob_by_account[:20]:
        print(f"  {a['account'][:26]:26} {a['group']:6} posts {a['posts']:4} views {f(a['views']):>8} org {a['organic_share']:.0%} "
              f"paid_posts {a['paid_posts']:3} da {a['da']:4} rate {a['da_rate']:.4f} share_da {a['da'] / tot_da:.1%}")
    print("\nORGANIC PER POST (pages >= 8 posts, ex Danke)")
    cand = [pg for pg in page_rows if pg["posts"] >= 8 and pg["account"] != "Danke"]
    for pg in sorted(cand, key=lambda r: -r["organic"] / r["posts"])[:12]:
        print(f"  {pg['page'][:42]:42} posts {pg['posts']:3} org/post {pg['organic'] / pg['posts']:6,.0f} share {pg['organic_share']:.0%} "
              f"da_rate {pg['da_rate']:.4f}")


if __name__ == "__main__":
    main(sys.argv[1])
