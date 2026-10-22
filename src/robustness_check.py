"""Kiểm tra insight còn đúng khi chỉ lấy bài 'đã chín' (đăng 07–17/10, đủ >= 4 ngày tích view)."""
from collections import defaultdict
from datetime import date

from sqlalchemy import select

from app import social  # noqa: F401
from app.db import SessionLocal
from app.social import Dealer, Product, SocialPage, SocialPost, product_matcher
from social_report_rules import account_of, angle_of, classify

with SessionLocal() as db:
    pages = {p.id: p for p in db.scalars(select(SocialPage))}
    dealers = {d.id: d.name for d in db.scalars(select(Dealer))}
    match = product_matcher(db.scalars(select(Product)).all())
    rows = [p for p in db.scalars(select(SocialPost)) if p.published_at and not p.duplicate_of
            and date(2026, 10, 7) <= p.published_at.date() <= date(2026, 10, 17)]


def rate(ps):
    v = sum(p.views for p in ps)
    return f"posts {len(ps):4} views {v:9,} vpp {v / len(ps) if ps else 0:6,.0f} da_rate {sum(p.comments + p.shares for p in ps) / v if v else 0:.4f} " \
           f"org {sum(p.views_organic for p in ps) / v if v else 0:.0%}"


rob = []
by_angle, by_prod, by_acc = defaultdict(list), defaultdict(list), defaultdict(list)
for p in rows:
    prod = match(p.title)
    if prod and prod.brand == "Roborock":
        rob.append(p)
        by_angle[angle_of(p.title)].append(p)
        by_prod[prod.name].append(p)
        pg = pages.get(p.page_id)
        by_acc[account_of(pg.name if pg else "", dealers.get(pg.dealer_id) if pg and pg.dealer_id else None)].append(p)
print("ROBOROCK mature", rate(rob))
for k in ("Experience / event", "Demo / feature", "Gift 20/10", "Promo / price", "Service / trust", "Lifestyle / other"):
    print(f"  {k:20}", rate(by_angle[k]))
for k in ("Roborock Saros 20 Flow Complete", "Roborock F25 Ultra Steam Gen 2", "Roborock F25 Ultra", "Roborock Qrevo 2 Pro",
          "Roborock Qrevo Edge 2 Flow", "Roborock (chung)"):
    hits = [n for n in by_prod if n.startswith(k)]
    print(f"  {k[:30]:30}", rate([p for n in hits for p in by_prod[n]]))
for k in ("BigMi", ("Danke", 'CM'), "H&T Smart Home", "CellphoneS", "Cường Phát"):
    name = k if isinstance(k, str) else k[0]
    print(f"  ACC {name:18}", rate([p for (a, g), ps in by_acc.items() if a == name for p in ps]))
pub = defaultdict(int)
for p in by_angle["Experience / event"]:
    pub[p.published_at.date().isoformat()] += 1
print("experience posts by day", sorted(pub.items()))
