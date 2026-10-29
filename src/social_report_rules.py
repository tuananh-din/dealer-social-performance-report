"""Quy tắc cho Social Report toàn đại lý: gom Page -> đại lý/chuỗi, nhận diện ngành hàng + brand từ caption.
Dùng chung cho bước dò insight và bước xuất số liệu dashboard."""
import re
import unicodedata

# Đại lý / chuỗi: (tên hiển thị, nhóm, mẫu tìm trong tên Page không dấu). Nhóm "CM" = 11 cửa hàng key account của report CM.
ACCOUNTS = [
    ("BigMi", "CM", r"bigmi"),
    ("CellphoneS", "CM", r"cellphones"),
    ("H&T Smart Home", "CM", r"h&t|h & t|ht smart"),
    ("Homecare", "CM", r"homecare"),
    ("Danke", "CM", r"danke"),
    ("Domotek", "CM", r"domotek"),
    ("Hotek", "CM", r"hotek"),
    ("Mi360", "CM", r"mi 360|mi360"),
    ("Cường Phát", "CM", r"cuong phat"),
    ("Đại Hồng Phát", "CM", r"dhp|dai hong phat"),
    ("Giang Chi", "CM", r"giang chi"),
    ("Cao Thiên Phát", "Dealer", r"cao thien phat"),
    ("Thế Giới Robot Hút Bụi", "Dealer", r"thegioirobothutbui"),
    ("Roborock Flagship", "Brand", r"roborock flagship"),
]

# Page loại khỏi report (tên Page bỏ dấu, khớp nguyên tên). 29/10/2026 người dùng yêu cầu bỏ "DANKE Gia dụng cao cấp":
# Page gia dụng nhà bếp chiếm hơn nửa view cả mạng nên kéo lệch mọi tỉ lệ. Page robot của Danke ở Đà Nẵng vẫn giữ.
EXCLUDED_PAGES = {"danke gia dung cao cap"}

# Ngành hàng: thứ tự = ưu tiên (robot / chăm sóc sàn xét trước). Mẫu tìm trong caption không dấu.
CATEGORIES = [
    ("Floor care", r"robot hut bui|robot lau|hut bui lau nha|may lau (san|nha)|may hut bui|hut bui|robot|roborock|dreame|"
                   r"ecovacs|deebot|narwal|roomba|irobot|robovac|lydsto|tineco|qrevo|saros|s8 maxv|f25|"
                   r"lau nha|tram sac|tram rua|hut bui cam tay"),
    # bỏ dấu thì "nói"/"chào"/"lý do" trùng "nồi"/"chảo"/"ly" -> chỉ dùng cụm rõ nghĩa
    ("Kitchen", r"noi com|noi chien|noi ap suat|noi lau|bo noi|noi inox|bep tu|bep ga|bep hong ngoai|lo nuong|lo vi song|"
                r"may rua bat|may rua chen|may xay|may ep|am sieu toc|binh thuy|cuckoo|fissler|thot|chao chong dinh|"
                r"hop inox|cuitisan|may lam sua|binh giu nhiet|hydro flask|may pha ca phe|bat dia|joseph joseph|gia dung bep"),
    ("Air & climate", r"loc khong khi|may loc|hut am|dieu hoa|quat |may suoi|tao am"),
    ("Large appliances", r"tu lanh|may giat|may say quan|tivi|tv |man hinh|loa |stand by me"),
    ("Phones & IT", r"dien thoai|iphone|samsung galaxy|redmi|poco|xiaomi 1[0-9]|laptop|macbook|ipad|tablet|may tinh|"
                    r"tai nghe|airpods|dong ho thong minh|smartwatch|sac du phong"),
    ("Personal care", r"massage|may say toc|ban chai dien|may cao rau|ban ui|ban la|ui hoi|lam dep"),
    ("Smart home", r"camera|khoa cua|o cam thong minh|cong tac|den thong minh|nha thong minh|thung rac thong minh"),
]

# Brand trong ngành Floor care (Roborock nhận diện bằng bộ luật sản phẩm của app, các brand khác theo từ khóa).
COMPETITORS = [
    ("Dreame", r"dreame"),
    ("Ecovacs", r"ecovacs|deebot"),
    ("Xiaomi", r"xiaomi|mijia|mi robot"),
    ("Narwal", r"narwal"),
    ("iRobot", r"irobot|roomba"),
    ("Eufy", r"eufy|robovac"),
    ("Tineco", r"tineco"),
    ("Lydsto", r"lydsto"),
    ("Ezviz", r"ezviz"),
]


def plain(s: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (giữ khoảng trắng và &)."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def excluded(page_name: str) -> bool:
    return " ".join(plain(page_name).split()) in EXCLUDED_PAGES


_ACC = [(n, g, re.compile(p)) for n, g, p in ACCOUNTS]
_CAT = [(n, re.compile(p)) for n, p in CATEGORIES]
_COMP = [(n, re.compile(p)) for n, p in COMPETITORS]


def account_of(page_name: str, dealer_name: str | None) -> tuple[str, str]:
    """(đại lý, nhóm). Dealer đã gán trong app được ưu tiên; không khớp chuỗi nào thì lấy phần đầu tên Page."""
    t = plain(page_name)
    for name, group, pat in _ACC:
        if pat.search(t):
            return name, group
    if dealer_name:
        return dealer_name, "Dealer"
    # "Roborock Authorized Store - Robozen Đà Nẵng" / "Roborock - AnhSalem Quảng Bình": tên đại lý nằm SAU tiền tố
    name = re.sub(r"^\s*roborock(\s+authorized\s+store)?\s*[-–]\s*", "", page_name or "", flags=re.I)
    head = re.split(r"\s+[-–|]\s+", name)[0].strip()
    return (head or page_name or "(không tên)")[:40], "Dealer"


# Góc nội dung (content angle) theo caption không dấu; 1 bài có thể có nhiều góc, lấy góc đầu tiên khớp.
ANGLES = [
    ("Gift 20/10", r"20/10|20-10|phu nu viet nam|tang me|tang vo|qua tang cho nang|phai dep"),
    ("Promo / price", r"uu dai|giam gia|giam ngay|khuyen mai|sale|deal|tra gop|gia soc|gia tot|flash|voucher|chi con|qua tang"),
    ("Service / trust", r"bao hanh|lap dat|giao hang|ban giao|chinh hang|uy quyen|thong cao|ho tro ky thuat|ve sinh may"),
    ("Experience / event", r"trai nghiem|su kien|workshop|showroom|ghe tham|livestream|minigame"),
    ("Demo / feature", r"lau|hut|chai|nuoc nong|hoi nuoc|luc hut|tram|cong nghe|tinh nang|thong minh|tu dong|cam bien|"
                       r"long thu cung|tu giat|say"),
]
_ANG = [(n, re.compile(p)) for n, p in ANGLES]


def angle_of(title: str) -> str:
    t = plain(title)
    return next((n for n, pat in _ANG if pat.search(t)), "Other / no caption" if not t.strip() else "Lifestyle / other")


def classify(title: str, roborock_hit: bool) -> tuple[str, str]:
    """(ngành hàng, brand). Bài nhắc model Roborock -> Floor care / Roborock."""
    t = plain(title)
    if roborock_hit:
        return "Floor care", "Roborock"
    cat = next((n for n, pat in _CAT if pat.search(t + " ")), "Other / store post")
    if cat != "Floor care":
        return cat, ""
    brand = next((n for n, pat in _COMP if pat.search(t)), "Unbranded / generic")
    return cat, brand
