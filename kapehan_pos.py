import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import hashlib
import hmac
import secrets
import os
import csv
import json
import shutil
import time
import importlib
from datetime import datetime, timedelta

# optional library, di mag-crash kung wala
try:
    Image = importlib.import_module("PIL.Image")
    ImageDraw = importlib.import_module("PIL.ImageDraw")
    ImageFont = importlib.import_module("PIL.ImageFont")
    ImageTk = importlib.import_module("PIL.ImageTk")
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------- settings ----------
SHOP_NAME = "Kapehan ni Bads"
TAGLINE = "Coffee, Pastries, and Sweets"
MAX_CHARS = 20
LOW_STOCK_LEVEL = 5
MAX_TRIES = 5
LOCK_SECS = 30
TEMP_CATS = ("Coffee", "Tea")      # may Hot / Cold lang yung mga ito

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "users.db")
IMG_DIR = os.path.join(HERE, "product_images")
LOGO_PATH = os.path.join(HERE, "logo.png")   # dapat nasa same folder ng file na ito
os.makedirs(IMG_DIR, exist_ok=True)

QUESTIONS = [
    "What City Were You Born in?",
    "What Is Your Favorite Color?",
    "What Was The Name of Your First Pet?",
]
BASE_CATEGORIES = ["Coffee", "Pastry", "Tea", "Bread"]

# kulay galing sa Figma design mo
COL = {
    "dark": "#401b01", "dark2": "#5a2a0a", "bg": "#e3dccf", "white": "#ffffff",
    "card": "#ededed", "field": "#d9d9d9", "orange": "#de8a2f", "orange2": "#c4731c",
    "brand": "#ff7f11", "line": "#e8c9a0", "text": "#1c1209", "gray": "#7a6f62",
    "green": "#2e8b57", "green2": "#24764a", "red": "#e02424", "red2": "#b81414",
    "soft": "#efe8dc", "tile": "#f0ece4", "tile_img": "#e4dccd", "edge": "#b9b2a6",
    "zebra": "#fbf8f2",
}

FONT = "Segoe UI"
TITLE = (FONT, 22, "bold")
BIG = (FONT, 20, "bold")
MED = (FONT, 14, "bold")
NORMAL = (FONT, 10)
BOLD = (FONT, 10, "bold")
SMALL = (FONT, 9)
TINY = (FONT, 8)
ENTRY_FONT = (FONT, 11)
BTN_FONT = (FONT, 11, "bold")


def money(n):
    return "PHP {:,.2f}".format(n)


# ---------- password stuff ----------
def hash_text(text, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", text.encode(), bytes.fromhex(salt), 120000)
    return "pbkdf2$" + salt + "$" + h.hex()


def check_hash(text, saved):
    if saved.startswith("pbkdf2$"):
        parts = saved.split("$")
        if len(parts) != 3:
            return False
        return hmac.compare_digest(hash_text(text, parts[1]), saved)
    # old accounts na plain sha256 pa
    return hmac.compare_digest(hashlib.sha256(text.encode()).hexdigest(), saved)


# ---------- images ----------
logo_cache = {}
prod_img_cache = {}
addon_img_cache = {}


def get_logo(size):
    # logo.png na ginawang bilog
    if not HAS_PIL or not os.path.exists(LOGO_PATH):
        return None
    if size not in logo_cache:
        try:
            im = Image.open(LOGO_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
            mask = Image.new("L", (size * 4, size * 4), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
            im.putalpha(mask.resize((size, size), Image.LANCZOS))
            logo_cache[size] = ImageTk.PhotoImage(im)
        except Exception:
            logo_cache[size] = None
    return logo_cache[size]


def clean_name(name):
    out = ""
    for ch in name:
        out += ch if ch.isalnum() else "_"
    return out[:20] or "product"


def copy_product_photo(src, name):
    ext = os.path.splitext(src)[1].lower() or ".png"
    fname = "{}_{}{}".format(clean_name(name), int(time.time() * 1000), ext)
    shutil.copy2(src, os.path.join(IMG_DIR, fname))
    return fname


def get_product_img(fname, size=120):
    if not fname or not HAS_PIL:
        return None
    key = (fname, size)
    if key not in prod_img_cache:
        try:
            im = Image.open(os.path.join(IMG_DIR, fname)).convert("RGB")
            prod_img_cache[key] = ImageTk.PhotoImage(im.resize((size, size), Image.LANCZOS))
        except Exception:
            prod_img_cache[key] = None
    return prod_img_cache[key]


def get_addon_icon_img(fname, size=60):
    if not fname or not HAS_PIL:
        return None
    key = (fname, size)
    if key not in addon_img_cache:
        try:
            im = Image.open(os.path.join(IMG_DIR, os.path.basename(fname))).convert("RGBA")
            addon_img_cache[key] = ImageTk.PhotoImage(im.resize((size, size), Image.LANCZOS))
        except Exception:
            addon_img_cache[key] = None
    return addon_img_cache[key]


def make_placeholder(name, category):
    # simpleng picture kung walang photo yung product
    if not HAS_PIL:
        return None
    colors = {
        "Coffee": ("#7a3f1d", "#f3d7b7"),
        "Tea": ("#5b7c4d", "#e3f0d8"),
        "Pastry": ("#c77b36", "#f8e8d0"),
        "Bread": ("#b97c43", "#f4dfc2"),
    }
    bg, accent = colors.get(category, ("#7a3f1d", "#f3d7b7"))
    fname = "{}_{}.png".format(clean_name(name).lower(), int(time.time() * 1000))
    im = Image.new("RGB", (400, 300), bg)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 20, 380, 280), radius=28, fill=accent)
    d.rounded_rectangle((60, 60, 340, 220), radius=22, fill=bg)
    try:
        f = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        f = ImageFont.load_default()
    d.text((200, 140), name[:16], anchor="mm", font=f, fill="white")
    im.save(os.path.join(IMG_DIR, fname))
    return fname


# ---------- cart line helpers ----------
def line_unit(l):
    return l["price"] + sum(t["price"] * t["qty"] for t in l["toppings"])


def line_total(l):
    return line_unit(l) * l["qty"]


def line_label(l):
    return l["name"] + (" (%s)" % l["temp"] if l["temp"] else "")


def toppings_text(l):
    return ", ".join("%s x%d" % (t["name"], t["qty"]) for t in l["toppings"])


# ---------- database ----------
class DB:
    def __init__(self):
        self.con = sqlite3.connect(DB_PATH)
        c = self.con
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'cashier',
            secret_question TEXT NOT NULL,
            secret_answer_hash TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            image_filename TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_datetime TEXT NOT NULL,
            items_json TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            total REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS addons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            icon TEXT)""")
        # dagdag columns kung luma pa yung db
        cols = [r[1] for r in c.execute("PRAGMA table_info(orders)")]
        if "cashier" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN cashier TEXT")
        if "tendered" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN tendered REAL")
        pcols = [r[1] for r in c.execute("PRAGMA table_info(products)")]
        if "active" not in pcols:
            c.execute("ALTER TABLE products ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        c.commit()

        # default admin
        n = c.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        if n == 0:
            self.add_user("admin", "admin123", "admin", QUESTIONS[0], "manila")

        # default products
        n = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if n == 0:
            starter = [
                ("Caf\u00e9 Latte", "Coffee", 120, 100), ("Espresso", "Coffee", 90, 100),
                ("Iced Mocha", "Coffee", 150, 100), ("Cheese Ensaymada", "Pastry", 65, 100),
                ("Blueberry Muffin", "Pastry", 80, 100), ("Hot Choco", "Tea", 110, 100),
                ("Milk Tea", "Tea", 120, 100), ("Bacon Bread", "Bread", 70, 100),
            ]
            for name, cat, price, stock in starter:
                self.add_product(name, cat, price, stock, make_placeholder(name, cat))

        # default toppings / add-ons (palitan mo na lang ang presyo)
        n = c.execute("SELECT COUNT(*) FROM addons").fetchone()[0]
        if n == 0:
            starter = [
                ("Whipped Cream", "Sweet & Creamy", 10, "Whipped-Cream-Recipe-SQ.jpg"),
                ("Chocolate Drizzle", "Sweet & Creamy", 15, "Chocolate-Drizzle-Recipe-SQ.jpg"),
                ("Caramel Drizzle", "Sweet & Creamy", 15, "Caramel-Drizzle-Recipe-SQ.jpg"),
                ("Strawberry Sauce", "Sweet & Creamy", 15, "Strawberry-Sauce-Recipe-SQ.jpg"),
                ("Oreo Crumbs", "Crunchy", 20, "Oreo-Crumbs-Recipe-SQ.jpg"),
                ("Biscoff Crumbs", "Crunchy", 25, "Biscoff-Crumbs-Recipe-SQ.jpg"),
            ]
            for name, cat, price, icon in starter:
                icon = os.path.basename(icon)
                c.execute("INSERT INTO addons (name, category, price, icon) VALUES (?,?,?,?)",
                          (name, cat, price, icon))

        old_icons = c.execute("SELECT id, icon FROM addons WHERE icon IS NOT NULL AND icon != ''").fetchall()
        for aid, icon in old_icons:
            if icon and os.path.isabs(icon):
                c.execute("UPDATE addons SET icon=? WHERE id=?", (os.path.basename(icon), aid))

        # lagyan ng picture yung walang picture
        rows = c.execute("SELECT id, name, category FROM products WHERE image_filename IS NULL OR image_filename=''").fetchall()
        for pid, name, cat in rows:
            img = make_placeholder(name, cat)
            if img:
                c.execute("UPDATE products SET image_filename=? WHERE id=?", (img, pid))
        c.commit()

    # users
    def user_exists(self, username):
        return self.con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone() is not None

    def add_user(self, username, pw, role, question, answer):
        self.con.execute(
            "INSERT INTO users (username, password_hash, role, secret_question, secret_answer_hash) VALUES (?,?,?,?,?)",
            (username, hash_text(pw), role, question, hash_text(answer.strip().lower())))
        self.con.commit()

    def login(self, username, pw):
        row = self.con.execute("SELECT role, password_hash FROM users WHERE username=?", (username,)).fetchone()
        if row is None or not check_hash(pw, row[1]):
            return None
        if not row[1].startswith("pbkdf2$"):
            # i-upgrade yung lumang hash
            self.con.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_text(pw), username))
            self.con.commit()
        return row[0]

    def is_admin_password(self, pw):
        rows = self.con.execute("SELECT password_hash FROM users WHERE role='admin'").fetchall()
        for r in rows:
            if check_hash(pw, r[0]):
                return True
        return False

    def get_question(self, username):
        row = self.con.execute("SELECT secret_question FROM users WHERE username=?", (username,)).fetchone()
        if row:
            return row[0]
        return None

    def answer_ok(self, username, answer):
        row = self.con.execute("SELECT secret_answer_hash FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            return False
        return check_hash(answer.strip().lower(), row[0])

    def set_password(self, username, new_pw):
        self.con.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_text(new_pw), username))
        self.con.commit()

    # products
    def add_product(self, name, cat, price, stock, img=None):
        self.con.execute("INSERT INTO products (name, category, price, stock, image_filename) VALUES (?,?,?,?,?)",
                         (name, cat, price, stock, img))
        self.con.commit()

    def edit_product(self, pid, name, cat, price, stock, img=None):
        if img:
            self.con.execute("UPDATE products SET name=?, category=?, price=?, stock=?, image_filename=? WHERE id=?",
                             (name, cat, price, stock, img, pid))
        else:
            self.con.execute("UPDATE products SET name=?, category=?, price=?, stock=? WHERE id=?",
                             (name, cat, price, stock, pid))
        self.con.commit()

    def set_active(self, pid, flag):
        self.con.execute("UPDATE products SET active=? WHERE id=?", (1 if flag else 0, pid))
        self.con.commit()

    def add_stock(self, pid, qty):
        self.con.execute("UPDATE products SET stock = stock + ? WHERE id=?", (qty, pid))
        self.con.commit()

    def products(self, search="", category="All"):
        # para sa POS: active lang
        sql = "SELECT id, name, category, price, stock, image_filename FROM products WHERE active=1"
        args = []
        if search:
            sql += " AND name LIKE ?"
            args.append("%" + search + "%")
        if category != "All":
            sql += " AND category=?"
            args.append(category)
        sql += " ORDER BY name"
        return self.con.execute(sql, args).fetchall()

    def inventory_rows(self, search=""):
        sql = "SELECT id, name, category, price, stock, image_filename, active FROM products"
        args = []
        if search:
            sql += " WHERE name LIKE ?"
            args.append("%" + search + "%")
        sql += " ORDER BY name"
        return self.con.execute(sql, args).fetchall()

    def product(self, pid):
        return self.con.execute(
            "SELECT id, name, category, price, stock, image_filename FROM products WHERE id=?", (pid,)).fetchone()

    def is_active(self, pid):
        row = self.con.execute("SELECT active FROM products WHERE id=?", (pid,)).fetchone()
        return bool(row and row[0])

    def categories(self):
        found = [r[0] for r in self.con.execute("SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category")]
        for c in BASE_CATEGORIES:
            if c not in found:
                found.append(c)
        return found

    def all_categories(self):
        found = [r[0] for r in self.con.execute("SELECT DISTINCT category FROM products ORDER BY category")]
        for c in BASE_CATEGORIES:
            if c not in found:
                found.append(c)
        return found

    def low_stock_count(self):
        return self.con.execute("SELECT COUNT(*) FROM products WHERE active=1 AND stock <= ?", (LOW_STOCK_LEVEL,)).fetchone()[0]

    # add-ons
    def addons(self, search="", category="All"):
        sql = "SELECT id, name, category, price, icon FROM addons WHERE 1=1"
        args = []
        if search:
            sql += " AND name LIKE ?"
            args.append("%" + search + "%")
        if category != "All":
            sql += " AND category=?"
            args.append(category)
        sql += " ORDER BY id"
        return self.con.execute(sql, args).fetchall()

    def addon_categories(self):
        return [r[0] for r in self.con.execute("SELECT DISTINCT category FROM addons ORDER BY category")]

    def add_addon(self, name, category, price, icon=None):
        self.con.execute(
            "INSERT INTO addons (name, category, price, icon) VALUES (?,?,?,?)",
            (name, category, price, icon))
        self.con.commit()

    def edit_addon(self, addon_id, name, category, price, icon=None):
        self.con.execute(
            "UPDATE addons SET name=?, category=?, price=?, icon=? WHERE id=?",
            (name, category, price, icon, addon_id))
        self.con.commit()

    # orders
    def save_order(self, items, method, total, cashier, tendered):
        try:
            # check muna kung kulang stock (pinagsama kada product)
            need = {}
            for it in items:
                need[it["product_id"]] = need.get(it["product_id"], 0) + it["qty"]
            for pid, qty in need.items():
                row = self.con.execute("SELECT name, stock FROM products WHERE id=?", (pid,)).fetchone()
                if row is None:
                    raise ValueError("A product in your order is no longer in the product list.")
                if row[1] < qty:
                    raise ValueError("Not enough stock for '{}' (only {} left).".format(row[0], row[1]))
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur = self.con.execute(
                "INSERT INTO orders (order_datetime, items_json, payment_method, total, cashier, tendered) VALUES (?,?,?,?,?,?)",
                (now, json.dumps(items), method, total, cashier, tendered))
            for pid, qty in need.items():
                self.con.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, pid))
            self.con.commit()
            return cur.lastrowid, now
        except Exception:
            self.con.rollback()
            raise

    def orders(self, period="All Time"):
        sql = "SELECT id, order_datetime, items_json, payment_method, total, cashier, tendered FROM orders"
        args = []
        now = datetime.now()
        if period == "Today":
            sql += " WHERE order_datetime >= ?"
            args.append(now.strftime("%Y-%m-%d 00:00:00"))
        elif period == "This Week":
            monday = now - timedelta(days=now.weekday())
            sql += " WHERE order_datetime >= ?"
            args.append(monday.strftime("%Y-%m-%d 00:00:00"))
        elif period == "This Month":
            sql += " WHERE order_datetime >= ?"
            args.append(now.strftime("%Y-%m-01 00:00:00"))
        sql += " ORDER BY order_datetime DESC"
        return self.con.execute(sql, args).fetchall()

    def clear_orders(self):
        try:
            cur = self.con.execute("DELETE FROM orders")
            self.con.commit()
            return cur.rowcount
        except sqlite3.Error:
            self.con.rollback()
            raise

    def summary(self, period):
        rows = self.orders(period)
        counts = {}
        total = 0
        for o in rows:
            total += o[4]
            try:
                items = json.loads(o[2])
            except Exception:
                items = []
            for it in items:
                key = it.get("base_name", it["name"])
                counts[key] = counts.get(key, 0) + it.get("qty", 0)
        if counts:
            best = max(counts, key=counts.get)
            best_qty = counts[best]
        else:
            best, best_qty = "N/A", 0
        return {"sales": total, "orders": len(rows), "best": best, "best_qty": best_qty}


# ---------- widget helpers ----------
# (bg, hover, fg, border)
BUTTONS = {
    "primary": (COL["orange"], COL["orange2"], "white", None),
    "brand": (COL["brand"], "#e86d00", "white", None),
    "white": ("#ffffff", "#f1ece3", COL["text"], "#cfc7ba"),
    "outline": ("#fbf8f3", "#f1ece3", COL["text"], COL["line"]),
    "tab": ("#d9d9d9", "#cbcbcb", COL["text"], "#e8b27a"),
    "secondary": ("#ffffff", COL["soft"], COL["text"], "#cfc7ba"),
    "success": (COL["green"], COL["green2"], "white", None),
    "danger": (COL["red"], COL["red2"], "white", None),
    "ghost": ("#fbf8f3", COL["soft"], COL["orange2"], None),
}


def make_button(parent, text, cmd=None, kind="primary", font=BOLD, padx=16, pady=8):
    bg, hover, fg, border = BUTTONS[kind]
    b = tk.Button(parent, text=text, command=cmd, font=font, bg=bg, fg=fg, relief="flat", bd=0,
                  padx=padx, pady=pady, cursor="hand2", activebackground=hover, activeforeground=fg,
                  highlightthickness=1 if border else 0, highlightbackground=border or bg,
                  highlightcolor=border or bg)
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


def make_entry(parent, show=None, bg=None, width=None, auth=False):
    # auth=True -> gray na field na may orange border (gaya sa login design)
    kw = {}
    if width:
        kw["width"] = width
    if auth:
        return tk.Entry(parent, font=ENTRY_FONT, bg=COL["field"], fg=COL["text"], relief="flat", bd=0,
                        highlightthickness=1, highlightbackground="#f0a35e", highlightcolor=COL["brand"],
                        insertbackground=COL["text"], show=show, disabledbackground="#e4e4e4", **kw)
    return tk.Entry(parent, font=ENTRY_FONT, bg=bg or "white", fg=COL["text"], relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=COL["edge"], highlightcolor=COL["orange"],
                    insertbackground=COL["text"], show=show, **kw)


class PEntry(tk.Entry):
    # entry na may placeholder text
    def __init__(self, parent, placeholder, **kw):
        super().__init__(parent, **kw)
        self.ph = placeholder
        self.showing = False
        self.bind("<FocusIn>", self._in)
        self.bind("<FocusOut>", self._out)
        self._show()

    def _show(self):
        if not self.get():
            self.insert(0, self.ph)
            self.config(fg=COL["gray"])
            self.showing = True

    def _in(self, _e):
        if self.showing:
            self.delete(0, tk.END)
            self.config(fg=COL["text"])
            self.showing = False

    def _out(self, _e):
        self._show()

    def value(self):
        return "" if self.showing else self.get().strip()


def max_chars(entry, n=MAX_CHARS):
    check = entry.register(lambda s: len(s) <= n)
    entry.config(validate="key", validatecommand=(check, "%P"))


def password_box(parent, bg):
    frame = tk.Frame(parent, bg=bg)
    e = make_entry(frame, show="\u2022", auth=True)
    max_chars(e)
    e.pack(side="left", fill="x", expand=True, ipady=7)
    shown = [False]

    def toggle():
        shown[0] = not shown[0]
        if shown[0]:
            e.config(show="")
            btn.config(text="Hide")
        else:
            e.config(show="\u2022")
            btn.config(text="Show")

    btn = tk.Button(frame, text="Show", command=toggle, relief="flat", bd=0, bg=bg,
                    fg=COL["orange2"], font=(FONT, 9, "bold"), activebackground=bg, cursor="hand2")
    btn.pack(side="left", padx=(8, 0))
    return frame, e


def label(parent, text, bg=None):
    return tk.Label(parent, text=text, font=BOLD, bg=bg or COL["card"], fg=COL["text"], anchor="w")


def toggle_row(parent, options, current, on_pick, inactive="outline"):
    row = tk.Frame(parent, bg=COL["bg"])
    for name in options:
        active = (name == current)
        kind = "primary" if active else inactive
        make_button(row, name, lambda n=name: on_pick(n), kind,
                    font=BOLD if active else NORMAL, padx=18, pady=6).pack(side="left", padx=(0, 8))
    return row


def hover_border(border, normal, active):
    def enter(_e):
        border.config(bg=active)

    def leave(_e):
        x, y = border.winfo_pointerxy()
        w = border.winfo_containing(x, y)
        while w is not None:
            if w is border:
                return
            w = w.master
        border.config(bg=normal)

    def bind_all(w):
        w.bind("<Enter>", enter, add="+")
        w.bind("<Leave>", leave, add="+")
        for c in w.winfo_children():
            bind_all(c)

    bind_all(border)


def center_window(win, parent):
    win.update_idletasks()
    top = parent.winfo_toplevel()
    x = top.winfo_rootx() + (top.winfo_width() - win.winfo_width()) // 2
    y = top.winfo_rooty() + (top.winfo_height() - win.winfo_height()) // 2
    win.geometry("+%d+%d" % (max(x, 0), max(y, 0)))


def logo_widget(parent, size, bg):
    img = get_logo(size)
    if img:
        lb = tk.Label(parent, image=img, bg=bg, bd=0)
        lb.image = img
        return lb
    cv = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
    cv.create_oval(2, 2, size - 2, size - 2, fill="#f4e3c1", outline=COL["orange"], width=2)
    cv.create_text(size // 2, size // 2, text="\u2615", font=(FONT, int(size * 0.4)))
    return cv


class RoundedCard(tk.Canvas):
    # gray na card na bilugan ang gilid (gaya sa login design)
    def __init__(self, parent, bg=COL["card"], outer=COL["bg"], radius=28, padx=46, pady=34):
        super().__init__(parent, bg=outer, highlightthickness=0, bd=0)
        self.fill, self.r, self.px, self.py = bg, radius, padx, pady
        self.inner = tk.Frame(self, bg=bg)
        self.create_window(padx, pady, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._resize)

    def _resize(self, _e=None):
        w = self.inner.winfo_reqwidth() + 2 * self.px
        h = self.inner.winfo_reqheight() + 2 * self.py
        self.config(width=w, height=h)
        self.delete("bg")
        r = self.r
        pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
        self.create_polygon(pts, smooth=True, fill=self.fill, outline=self.fill, tags="bg")
        self.tag_lower("bg")


class ScrollFrame(tk.Frame):
    # puting scroll area na may grid ng cards sa loob
    def __init__(self, parent, card_w=None, on_cols=None, bg="white"):
        super().__init__(parent, bg=bg, highlightthickness=1, highlightbackground=COL["edge"])
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._resize)
        self.card_w = card_w
        self.on_cols = on_cols
        self.cols = 3

    def _resize(self, e):
        self.canvas.itemconfig(self.win, width=e.width)
        if self.card_w:
            cols = max(1, e.width // (self.card_w + 16))
            if cols != self.cols:
                self.cols = cols
                if self.on_cols:
                    self.on_cols()

    def spread(self):
        for c in range(12):
            self.inner.grid_columnconfigure(c, weight=1 if c < self.cols else 0)


def make_receipt(order_id, when, items, method, total, cashier=None, tendered=None):
    w = 38
    out = [SHOP_NAME.center(w), TAGLINE.center(w), "-" * w,
           "Order #" + str(order_id), "Date : " + when]
    if cashier:
        out.append("Cashier: " + cashier)
    out.append("-" * w)
    for it in items:
        out.append(it["name"][:34])
        left = "   {} x {:.2f}".format(it["qty"], it["price"])
        out.append(left.ljust(w - 12) + "{:>12,.2f}".format(it["qty"] * it["price"]))
        for t in it.get("toppings", []):
            out.append("   + {} x{}".format(t["name"], t["qty"])[:w])
        if it.get("comment"):
            out.append("   Note: " + it["comment"][:28])
    out.append("-" * w)
    out.append("TOTAL".ljust(w - 18) + "{:>18}".format(money(total)))
    out.append("Payment: " + method)
    if tendered:
        out.append("Tendered".ljust(w - 18) + "{:>18}".format(money(tendered)))
        out.append("Change".ljust(w - 18) + "{:>18}".format(money(max(tendered - total, 0))))
    out.append("-" * w)
    out.append("Salamat po! Balik kayo ulit :)".center(w))
    return "\n".join(out)


class ReceiptWindow(tk.Toplevel):
    def __init__(self, parent, text, order_id):
        super().__init__(parent)
        self.title("Receipt #" + str(order_id))
        self.configure(bg=COL["white"])
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.text = text
        tk.Frame(self, bg=COL["orange"], height=4).pack(fill="x")
        box = tk.Text(self, width=40, height=min(text.count("\n") + 2, 32), font=("Consolas", 10),
                      bg="#fffdf7", fg=COL["text"], relief="flat", padx=16, pady=16)
        box.insert("1.0", text)
        box.config(state="disabled")
        box.pack(padx=14, pady=(14, 8))
        row = tk.Frame(self, bg=COL["white"])
        row.pack(pady=(0, 14))
        make_button(row, "Save as .txt", self.save, "secondary").pack(side="left", padx=4)
        make_button(row, "Close", self.destroy, "primary").pack(side="left", padx=4)
        center_window(self, parent)
        self.grab_set()

    def save(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")],
                                            initialfile="receipt.txt", parent=self)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text)


# ---------- base pages ----------
def brand_block(parent, logo_size, name_font, bg=COL["dark"]):
    box = tk.Frame(parent, bg=bg)
    logo_widget(box, logo_size, bg).pack(side="left", padx=(0, 14))
    txt = tk.Frame(box, bg=bg)
    txt.pack(side="left")
    tk.Label(txt, text=SHOP_NAME, font=name_font, bg=bg, fg="white").pack(anchor="w")
    tk.Label(txt, text=TAGLINE, font=TINY, bg=bg, fg="#e6d9c3").pack(anchor="w")
    return box


class AuthPage(tk.Frame):
    # parent class ng login, signup, forgot password
    def __init__(self, parent, app):
        super().__init__(parent, bg=COL["bg"])
        self.app = app
        bar = tk.Frame(self, bg=COL["dark"], height=80)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)
        brand_block(bar, 52, (FONT, 13)).place(relx=0.5, rely=0.5, anchor="center")
        self.slot = tk.Frame(self, bg=COL["bg"])
        self.slot.place(relx=0.5, rely=0.54, anchor="center")

    def new_card(self, padx=46, pady=34):
        for w in self.slot.winfo_children():
            w.destroy()
        card = RoundedCard(self.slot, padx=padx, pady=pady)
        card.pack()
        return card.inner

    def title(self, card, text):
        tk.Label(card, text=text, font=BIG, bg=COL["card"], fg=COL["text"], justify="center").pack(pady=(0, 14))


class MainPage(tk.Frame):
    # parent class ng mga pages after login (may navbar sa taas)
    def __init__(self, parent, app):
        super().__init__(parent, bg=COL["bg"])
        self.app = app
        self.bar = tk.Frame(self, bg=COL["dark"], height=80)
        self.bar.pack(side="top", fill="x")
        self.bar.pack_propagate(False)
        self.content = tk.Frame(self, bg=COL["bg"])
        self.content.pack(fill="both", expand=True, padx=30, pady=20)

    def draw_navbar(self):
        for w in self.bar.winfo_children():
            w.destroy()
        brand_block(self.bar, 48, (FONT, 12)).pack(side="left", padx=(30, 0), pady=10)

        nav = tk.Frame(self.bar, bg=COL["dark"])
        nav.pack(side="right", padx=30)
        make_button(nav, "Log out", self.app.logout, "primary", font=(FONT, 9, "bold"), pady=7, padx=22).pack(side="right", padx=(8, 0))

        if self.app.role == "admin":
            links = [("Dashboard", DashboardPage), ("Inventory", InventoryPage), ("Back to menu", POSPage)]
        else:
            links = [("Back to menu", POSPage)]
        links = [(t, p) for t, p in links if not isinstance(self, p)]
        for text, page in reversed(links):   # reversed kasi side=right
            make_button(nav, text, lambda p=page: self.app.show(p), "white",
                        font=(FONT, 9, "bold"), pady=7, padx=20).pack(side="right", padx=(8, 0))

    def reset(self):
        self.draw_navbar()
        for w in self.content.winfo_children():
            w.destroy()


# ---------- login ----------
class LoginPage(AuthPage):
    def on_show(self):
        card = self.new_card()
        self.title(card, "Welcome back")
        tk.Label(card, text="Log in to start your shift", font=NORMAL, bg=COL["card"], fg=COL["gray"]).pack(pady=(0, 14))

        label(card, "Username").pack(fill="x")
        self.user_e = make_entry(card, auth=True, width=34)
        max_chars(self.user_e)
        self.user_e.pack(fill="x", ipady=7, pady=(3, 12))

        label(card, "Password").pack(fill="x")
        pf, self.pw_e = password_box(card, COL["card"])
        pf.pack(fill="x", pady=(3, 6))

        forgot = tk.Label(card, text="Forgot password?", fg=COL["orange2"], bg=COL["card"],
                          cursor="hand2", font=(FONT, 9, "underline"))
        forgot.pack(anchor="e", pady=(0, 16))
        forgot.bind("<Button-1>", lambda e: self.app.show(ForgotPage))

        make_button(card, "Login", self.try_login, "brand", font=BTN_FONT, pady=10).pack(fill="x", pady=(0, 14))

        row = tk.Frame(card, bg=COL["card"])
        row.pack()
        tk.Label(row, text="Don't have an account? ", bg=COL["card"], font=SMALL, fg=COL["gray"]).pack(side="left")
        link = tk.Label(row, text="Sign up", bg=COL["card"], fg=COL["orange2"], font=(FONT, 9, "bold"), cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: self.app.show(SignupPage))

        self.user_e.bind("<Return>", lambda e: self.try_login())
        self.pw_e.bind("<Return>", lambda e: self.try_login())
        self.user_e.focus_set()

    def try_login(self):
        wait = self.app.locked_until - time.time()
        if wait > 0:
            messagebox.showwarning("Too many attempts", "Please wait %d seconds before trying again." % (int(wait) + 1))
            return
        username = self.user_e.get().strip()
        pw = self.pw_e.get()
        role = self.app.db.login(username, pw)
        if role:
            self.app.fails = 0
            self.app.role = role
            self.app.username = username
            self.app.cart = []
            if role == "admin":
                self.app.show(DashboardPage)
            else:
                self.app.show(POSPage)
        else:
            self.app.fails += 1
            if self.app.fails >= MAX_TRIES:
                self.app.locked_until = time.time() + LOCK_SECS
                self.app.fails = 0
                messagebox.showerror("Locked", "Too many wrong attempts. Try again in %d seconds." % LOCK_SECS)
            else:
                messagebox.showerror("Login Failed", "Incorrect username or password.")


# ---------- sign up ----------
class SignupPage(AuthPage):
    def on_show(self):
        card = self.new_card(pady=26)
        self.title(card, "Create Account")

        label(card, "Username").pack(fill="x")
        self.user_e = make_entry(card, auth=True, width=34)
        max_chars(self.user_e)
        self.user_e.pack(fill="x", ipady=6, pady=(2, 8))

        label(card, "Password").pack(fill="x")
        pf, self.pw_e = password_box(card, COL["card"])
        pf.pack(fill="x", pady=(2, 1))
        tk.Label(card, text="Max %d characters for username and password" % MAX_CHARS,
                 font=TINY, fg=COL["gray"], bg=COL["card"]).pack(anchor="w", pady=(0, 8))

        label(card, "Account Type  (admin needs an existing admin's password)").pack(fill="x")
        self.role_var = tk.StringVar(value="cashier")
        ttk.Combobox(card, textvariable=self.role_var, values=["cashier", "admin"],
                     state="readonly", font=ENTRY_FONT).pack(fill="x", ipady=3, pady=(2, 8))

        label(card, "Secret Question").pack(fill="x")
        self.q_var = tk.StringVar()
        ttk.Combobox(card, textvariable=self.q_var, values=QUESTIONS,
                     state="readonly", font=ENTRY_FONT).pack(fill="x", ipady=3, pady=(2, 8))

        label(card, "Your Answer").pack(fill="x")
        self.ans_e = make_entry(card, auth=True)
        self.ans_e.pack(fill="x", ipady=6, pady=(2, 14))

        make_button(card, "Create Account", self.create, "brand", font=BTN_FONT, pady=10).pack(fill="x", pady=(0, 10))
        back = tk.Label(card, text="Already have an account? Login", bg=COL["card"], fg=COL["orange2"],
                        font=(FONT, 9, "bold"), cursor="hand2")
        back.pack()
        back.bind("<Button-1>", lambda e: self.app.show(LoginPage))
        self.ans_e.bind("<Return>", lambda e: self.create())
        self.user_e.focus_set()

    def create(self):
        username = self.user_e.get().strip()
        pw = self.pw_e.get()
        role = self.role_var.get()
        question = self.q_var.get()
        answer = self.ans_e.get().strip()

        if not username or not pw or not question or not answer:
            messagebox.showwarning("Incomplete", "Please fill in all fields.")
            return
        if len(pw) < 4:
            messagebox.showwarning("Weak password", "Password must be at least 4 characters.")
            return
        if self.app.db.user_exists(username):
            messagebox.showerror("Username Taken", "That username is already registered.")
            return
        if role == "admin":
            admin_pw = simpledialog.askstring("Admin approval", "Enter an existing ADMIN password to continue:",
                                              show="*", parent=self)
            if not admin_pw or not self.app.db.is_admin_password(admin_pw):
                messagebox.showerror("Not allowed", "Wrong admin password. Account not created.")
                return
        self.app.db.add_user(username, pw, role, question, answer)
        messagebox.showinfo("Account Created", "Your account has been created. You can now log in.")
        self.app.show(LoginPage)


# ---------- forgot password (step 1) ----------
class ForgotPage(AuthPage):
    def on_show(self):
        card = self.new_card()
        self.title(card, "Forgot Password")

        label(card, "Enter your username").pack(fill="x")
        self.user_e = make_entry(card, auth=True, width=34)
        self.user_e.pack(fill="x", ipady=7, pady=(3, 10))
        self.user_e.bind("<KeyRelease>", lambda e: self.refresh_question())

        label(card, "Secret Question").pack(fill="x")
        self.q_var = tk.StringVar()
        ttk.Combobox(card, textvariable=self.q_var, values=QUESTIONS,
                     state="disabled", font=ENTRY_FONT).pack(fill="x", ipady=4, pady=(3, 10))

        label(card, "Your Answer").pack(fill="x")
        self.ans_e = make_entry(card, auth=True)
        self.ans_e.config(state="disabled")
        self.ans_e.pack(fill="x", ipady=7, pady=(3, 2))
        self.ans_e.bind("<KeyRelease>", self.check_answer)
        self.status = tk.Label(card, text="", font=SMALL, bg=COL["card"])
        self.status.pack(anchor="w", pady=(0, 14))

        make_button(card, "Set New Password", self.proceed, "brand", font=BTN_FONT, pady=10).pack(fill="x")
        back = tk.Label(card, text="Back to Login", bg=COL["card"], fg=COL["orange2"], font=(FONT, 9, "bold"), cursor="hand2")
        back.pack(pady=(12, 0))
        back.bind("<Button-1>", lambda e: self.app.show(LoginPage))

        self.ans_e.bind("<Return>", lambda e: self.proceed())
        self.verified = False
        self.user_e.focus_set()

    def border(self, color):
        self.ans_e.config(highlightbackground=color, highlightcolor=color)

    def refresh_question(self):
        # lalabas agad yung secret question kapag nakita yung username
        q = self.app.db.get_question(self.user_e.get().strip())
        self.verified = False
        self.status.config(text="")
        self.border("#f0a35e")
        self.ans_e.config(state="normal")
        self.ans_e.delete(0, tk.END)
        if q:
            self.q_var.set(q)
        else:
            self.q_var.set("")
            self.ans_e.config(state="disabled")

    def check_answer(self, event=None):
        username = self.user_e.get().strip()
        ans = self.ans_e.get()
        if ans == "":
            self.border("#f0a35e")
            self.status.config(text="")
            self.verified = False
        elif self.app.db.answer_ok(username, ans):
            self.border(COL["green"])
            self.status.config(text="\u2714 Correct answer", fg=COL["green"])
            self.verified = True
        else:
            self.border(COL["red"])
            self.status.config(text="\u2716 Incorrect answer", fg=COL["red"])
            self.verified = False

    def proceed(self):
        username = self.user_e.get().strip()
        if not self.app.db.get_question(username):
            messagebox.showerror("Not Found", "No account found with that username.")
            return
        if not self.verified or not self.app.db.answer_ok(username, self.ans_e.get()):
            messagebox.showwarning("Verify First", "Please answer your secret question correctly first.")
            return
        self.app.reset_user = username
        self.app.show(ResetPage)


# ---------- create new password (step 2) ----------
class ResetPage(AuthPage):
    def on_show(self):
        if not self.app.reset_user:
            self.app.show(LoginPage)
            return
        card = self.new_card()
        tk.Label(card, text="Create new\npassword", font=BIG, bg=COL["card"], fg=COL["text"], justify="center").pack(pady=(0, 14))

        label(card, "Create new Password").pack(fill="x")
        self.pw1 = make_entry(card, show="\u2022", auth=True, width=34)
        max_chars(self.pw1)
        self.pw1.pack(fill="x", ipady=7, pady=(3, 4))

        self.show_var = tk.BooleanVar(value=False)
        tk.Checkbutton(card, text="Show password", variable=self.show_var, command=self.toggle, bg=COL["card"],
                       activebackground=COL["card"], font=SMALL, anchor="w", cursor="hand2").pack(fill="x")
        tk.Label(card, text="Use at least 4 characters (up to %d).\nA mix of letters, numbers, and symbols is stronger." % MAX_CHARS,
                 font=TINY, fg=COL["gray"], bg=COL["card"], justify="left").pack(anchor="w", pady=(2, 10))

        label(card, "Confirm your password").pack(fill="x")
        self.pw2 = make_entry(card, show="\u2022", auth=True)
        max_chars(self.pw2)
        self.pw2.pack(fill="x", ipady=7, pady=(3, 16))

        make_button(card, "Create new password", self.save, "brand", font=BTN_FONT, pady=10).pack(fill="x")
        back = tk.Label(card, text="Cancel", bg=COL["card"], fg=COL["orange2"], font=(FONT, 9, "bold"), cursor="hand2")
        back.pack(pady=(12, 0))
        back.bind("<Button-1>", lambda e: self.app.show(LoginPage))
        self.pw2.bind("<Return>", lambda e: self.save())
        self.pw1.focus_set()

    def toggle(self):
        ch = "" if self.show_var.get() else "\u2022"
        self.pw1.config(show=ch)
        self.pw2.config(show=ch)

    def save(self):
        new_pw = self.pw1.get()
        if len(new_pw) < 4:
            messagebox.showwarning("Weak password", "Password must be at least 4 characters.")
            return
        if new_pw != self.pw2.get():
            messagebox.showwarning("Not matching", "The two passwords are not the same.")
            return
        self.app.db.set_password(self.app.reset_user, new_pw)
        self.app.reset_user = None
        messagebox.showinfo("Success", "Password updated. Please log in.")
        self.app.show(LoginPage)


# ---------- POS ----------
class POSPage(MainPage):
    def on_show(self):
        self.reset()
        if not hasattr(self, "category"):
            self.category = "All"
        self.search_text = ""

        left = tk.Frame(self.content, bg=COL["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 22))

        sr = tk.Frame(left, bg=COL["bg"])
        sr.pack(fill="x")
        self.search_e = make_entry(sr, bg="white")
        self.search_e.pack(side="left", fill="x", expand=True, ipady=9)
        self.search_e.bind("<KeyRelease>", lambda e: self.do_search())
        make_button(sr, "SEARCH", self.do_search, "primary", font=(FONT, 11), padx=26, pady=6).pack(side="left", padx=(8, 0))
        tk.Label(left, text="Search products:", font=SMALL, bg=COL["bg"], fg=COL["text"]).pack(anchor="w", pady=(4, 10))

        self.cat_holder = tk.Frame(left, bg=COL["bg"])
        self.cat_holder.pack(fill="x", pady=(0, 10))
        self.draw_categories()

        self.sg = ScrollFrame(left, card_w=180, on_cols=self.draw_products)
        self.sg.pack(fill="both", expand=True)

        # kanan: preview ng product + total + hot/cold
        border = tk.Frame(self.content, bg=COL["edge"], padx=1, pady=1, width=360)
        border.pack(side="right", fill="y")
        border.pack_propagate(False)
        wrap = tk.Frame(border, bg="white")
        wrap.pack(fill="both", expand=True)
        right = tk.Frame(wrap, bg="white")
        right.pack(fill="both", expand=True, padx=14, pady=14)

        prev = tk.Frame(right, bg=COL["tile_img"], highlightthickness=1, highlightbackground=COL["edge"], height=230)
        prev.pack(fill="x")
        prev.pack_propagate(False)
        self.prev_img = tk.Label(prev, bg=COL["tile_img"], fg=COL["gray"], font=NORMAL)
        self.prev_img.pack(expand=True)
        self.prev_name = tk.Label(right, text="", font=(FONT, 13, "bold"), bg="white", fg=COL["text"], anchor="w")
        self.prev_name.pack(fill="x", pady=(10, 0))
        self.prev_price = tk.Label(right, text="", font=SMALL, bg="white", fg=COL["gray"], anchor="w")
        self.prev_price.pack(fill="x")
        self.count_lbl = tk.Label(right, text="", font=SMALL, bg="white", fg=COL["gray"], anchor="w")
        self.count_lbl.pack(fill="x", pady=(8, 0))
        self.total_lbl = tk.Label(right, text="Total: PHP 0.00", font=(FONT, 12, "bold"), bg="white", fg=COL["text"], anchor="w")
        self.total_lbl.pack(fill="x", pady=(2, 8))

        trow = tk.Frame(right, bg="white")
        trow.pack(fill="x", pady=(0, 10))
        self.temp_var = tk.StringVar(value=self.app.temp)
        for t in ("Hot", "Cold"):
            tk.Radiobutton(trow, text=t, variable=self.temp_var, value=t, bg="white", activebackground="white",
                           font=SMALL, cursor="hand2", highlightthickness=0, bd=0, command=self.set_temp).pack(side="left", padx=(0, 18))

        make_button(right, "Customize", lambda: self.app.show(CustomizePage), "primary", font=(FONT, 11), pady=8).pack(fill="x", pady=(0, 8))
        make_button(right, "Checkout", self.checkout, "primary", font=(FONT, 11), pady=8).pack(fill="x")
        make_button(right, "Clear order", self.clear, "ghost", font=SMALL, pady=3).pack(pady=(10, 0))

        self.draw_products()
        self.draw_preview()

    def set_temp(self):
        self.app.temp = self.temp_var.get()

    def draw_categories(self):
        for w in self.cat_holder.winfo_children():
            w.destroy()
        names = ["All"] + self.app.db.categories()
        toggle_row(self.cat_holder, names, self.category, self.pick_category, inactive="tab").pack(anchor="w")

    def pick_category(self, name):
        self.category = name
        self.draw_categories()
        self.draw_products()

    def do_search(self):
        self.search_text = self.search_e.get().strip()
        self.draw_products()

    def select(self, pid):
        self.app.selected_pid = pid
        self.draw_preview()

    def draw_products(self):
        inner = self.sg.inner
        for w in inner.winfo_children():
            w.destroy()
        self.sg.spread()
        cols = self.sg.cols
        items = self.app.db.products(self.search_text, self.category)
        for i, p in enumerate(items):
            pid, name, cat, price, stock, img_file = p
            border = tk.Frame(inner, bg=COL["edge"], padx=1, pady=1)
            border.grid(row=i // cols, column=i % cols, padx=8, pady=8)
            card = tk.Frame(border, bg=COL["tile"], width=172, height=232)
            card.pack()
            card.pack_propagate(False)

            top = tk.Frame(card, bg=COL["tile_img"])
            top.pack(fill="x", padx=5, pady=(5, 6))
            img = get_product_img(img_file, 104)
            if img:
                lb = tk.Label(top, image=img, bg=COL["tile_img"])
                lb.image = img
            else:
                lb = tk.Label(top, text="\u2615", font=(FONT, 30), bg=COL["tile_img"], fg=COL["orange2"], height=2)
            lb.pack(pady=4)

            n = tk.Label(card, text=name, font=BOLD, bg=COL["tile"], fg=COL["text"], wraplength=150)
            n.pack()
            tk.Label(card, text=money(price).replace("PHP ", "PHP "), font=SMALL, bg=COL["tile"], fg=COL["gray"]).pack()

            if stock <= 0:
                txt, color = "Sold out", COL["red"]
            elif stock <= LOW_STOCK_LEVEL:
                txt, color = "Only %d left" % stock, COL["orange2"]
            else:
                txt, color = "%d in stock" % stock, COL["gray"]
            tk.Label(card, text=txt, font=TINY, bg=COL["tile"], fg=color).pack()

            if stock > 0:
                make_button(card, "Add to cart", lambda r=p: self.add(r), "primary",
                            font=(FONT, 8, "bold"), pady=3, padx=12).pack(pady=(5, 6))
            else:
                tk.Button(card, text="Sold out", state="disabled", font=(FONT, 8, "bold"), relief="flat",
                          bg="#d6d0c4", pady=3, padx=12).pack(pady=(5, 6))
            for w in (top, lb, n):
                w.bind("<Button-1>", lambda e, x=pid: self.select(x))
            hover_border(border, COL["edge"], COL["orange"])

        if len(items) == 0:
            tk.Label(inner, text="No products found.", font=ENTRY_FONT, bg="white", fg=COL["gray"]).grid(row=0, column=0, pady=30, padx=10)

    def draw_preview(self):
        p = self.app.db.product(self.app.selected_pid) if self.app.selected_pid else None
        if p and self.app.db.is_active(p[0]):
            img = get_product_img(p[5], 200)
            if img:
                self.prev_img.config(image=img, text="")
                self.prev_img.image = img
            else:
                self.prev_img.config(image="", text="\u2615", font=(FONT, 48))
            self.prev_name.config(text=p[1])
            self.prev_price.config(text=money(p[3]))
        else:
            self.prev_img.config(image="", text="Tap a product\nto preview it", font=NORMAL)
            self.prev_img.image = None
            self.prev_name.config(text="Name Product")
            self.prev_price.config(text="")
        self.refresh_totals()

    def refresh_totals(self):
        n = sum(l["qty"] for l in self.app.cart)
        self.count_lbl.config(text="%d item%s in your order" % (n, "" if n == 1 else "s"))
        self.total_lbl.config(text="Total: " + money(self.app.cart_total()))

    def add(self, row):
        self.app.add_to_cart(row)
        self.select(row[0])

    def clear(self):
        if self.app.cart and messagebox.askyesno("Clear order", "Remove all items from the order?"):
            self.app.cart = []
            self.app.sel_line = None
            self.refresh_totals()

    def checkout(self):
        if not self.app.cart:
            messagebox.showwarning("Empty Cart", "Add at least one item before checking out.")
            return
        self.app.show(CheckoutPage)


# ---------- customize (toppings + your order) ----------
class CustomizePage(MainPage):
    def on_show(self):
        self.reset()
        self.category = "All"
        self.search_text = ""
        self.qty_vars = {}
        self.app.fix_selection()

        left = tk.Frame(self.content, bg=COL["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 22))

        sr = tk.Frame(left, bg=COL["bg"])
        sr.pack(fill="x")
        self.search_e = make_entry(sr, bg="white")
        self.search_e.pack(side="left", fill="x", expand=True, ipady=9)
        self.search_e.bind("<KeyRelease>", lambda e: self.do_search())
        make_button(sr, "SEARCH", self.do_search, "primary", font=(FONT, 11), padx=26, pady=6).pack(side="left", padx=(8, 0))
        if self.app.role == "admin":
            addon_actions = tk.Frame(left, bg=COL["bg"])
            addon_actions.pack(fill="x", pady=(8, 2))
            make_button(addon_actions, "+ Add Topping", self.add_addon, "primary",
                        font=SMALL, pady=5, padx=12).pack(side="left", padx=(0, 6))
            make_button(addon_actions, "Edit Selected Topping", self.edit_addon, "outline",
                        font=SMALL, pady=5, padx=12).pack(side="left")
        tk.Label(left, text="Search toppings:", font=SMALL, bg=COL["bg"], fg=COL["text"]).pack(anchor="w", pady=(4, 10))

        self.cat_holder = tk.Frame(left, bg=COL["bg"])
        self.cat_holder.pack(fill="x", pady=(0, 10))
        self.draw_categories()

        self.sg = ScrollFrame(left, card_w=180, on_cols=self.draw_addons)
        self.sg.pack(fill="both", expand=True)

        border = tk.Frame(self.content, bg=COL["edge"], padx=1, pady=1, width=400)
        border.pack(side="right", fill="y")
        border.pack_propagate(False)
        wrap = tk.Frame(border, bg="white")
        wrap.pack(fill="both", expand=True)
        right = tk.Frame(wrap, bg="white")
        right.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(right, text="Your order", font=(FONT, 15, "bold"), bg="white", fg=COL["text"]).pack(anchor="w")
        tk.Label(right, text="item  \u00b7  customized toppings  \u00b7  amount", font=TINY, bg="white", fg=COL["gray"]).pack(anchor="w", pady=(0, 6))

        self.order_sf = ScrollFrame(right, bg=COL["tile"])
        self.order_sf.pack(fill="both", expand=True)

        self.total_lbl = tk.Label(right, text="Total: PHP 0.00", font=(FONT, 13, "bold"), bg="white", fg=COL["text"], anchor="w")
        self.total_lbl.pack(fill="x", pady=(10, 4))

        trow = tk.Frame(right, bg="white")
        trow.pack(fill="x")
        self.temp_var = tk.StringVar(value="Hot")
        self.temp_btns = []
        for t in ("Hot", "Cold"):
            rb = tk.Radiobutton(trow, text=t, variable=self.temp_var, value=t, bg="white", activebackground="white",
                                font=SMALL, cursor="hand2", highlightthickness=0, bd=0, command=self.set_line_temp)
            rb.pack(side="left", padx=(0, 18))
            self.temp_btns.append(rb)

        tk.Label(right, text="Add comment", font=SMALL, bg="white", fg=COL["gray"], anchor="w").pack(fill="x", pady=(6, 2))
        self.comment_e = make_entry(right, bg="white")
        self.comment_e.pack(fill="x", ipady=6)
        self.comment_e.bind("<KeyRelease>", lambda e: self.save_comment())

        make_button(right, "Checkout", self.checkout, "primary", font=(FONT, 11), pady=8).pack(fill="x", pady=(12, 0))

        self.draw_addons()
        self.draw_order()

    # ----- toppings (kaliwa) -----
    def draw_categories(self):
        for w in self.cat_holder.winfo_children():
            w.destroy()
        names = ["All"] + self.app.db.addon_categories()
        toggle_row(self.cat_holder, names, self.category, self.pick_category, inactive="tab").pack(anchor="w")

    def pick_category(self, name):
        self.category = name
        self.draw_categories()
        self.draw_addons()

    def do_search(self):
        self.search_text = self.search_e.get().strip()
        self.draw_addons()

    def draw_addons(self):
        inner = self.sg.inner
        for w in inner.winfo_children():
            w.destroy()
        self.sg.spread()
        cols = self.sg.cols
        rows = self.app.db.addons(self.search_text, self.category)
        for i, (aid, name, cat, price, icon) in enumerate(rows):
            border = tk.Frame(inner, bg=COL["edge"], padx=1, pady=1)
            border.grid(row=i // cols, column=i % cols, padx=8, pady=8)
            card = tk.Frame(border, bg=COL["tile"], width=172, height=222)
            card.pack()
            card.pack_propagate(False)
            top = tk.Frame(card, bg=COL["tile_img"])
            top.pack(fill="x", padx=5, pady=(5, 6))
            def choose_addon(aid=aid, b=border):
                self.selected_addon_id = aid
                for child in self.sg.inner.winfo_children():
                    child.config(bg=COL["orange"] if child is b else COL["edge"])
            for widget in (border, card, top):
                widget.bind("<Button-1>", lambda e, aid=aid, b=border: choose_addon(aid, b), add="+")
            img = get_addon_icon_img(icon, 60) if icon else None
            if img is not None:
                tk.Label(top, image=img, bg=COL["tile_img"], compound="center", width=60, height=60).pack(pady=4)
            else:
                tk.Label(top, text=icon or "\u2615", font=(FONT, 30), bg=COL["tile_img"], height=2).pack(pady=4)
            name_lbl = tk.Label(card, text=name, font=BOLD, bg=COL["tile"], fg=COL["text"], wraplength=150)
            name_lbl.pack()
            price_lbl = tk.Label(card, text=money(price), font=SMALL, bg=COL["tile"], fg=COL["gray"])
            price_lbl.pack()
            for widget in (name_lbl, price_lbl):
                widget.bind("<Button-1>", lambda e, aid=aid, b=border: choose_addon(aid, b), add="+")

            var = self.qty_vars.setdefault(aid, tk.IntVar(value=1))
            st = tk.Frame(card, bg=COL["tile"])
            st.pack(pady=(6, 4))
            tk.Button(st, text="\u2212", width=2, font=BOLD, bg="white", relief="flat", cursor="hand2",
                      command=lambda v=var: v.set(max(1, v.get() - 1))).pack(side="left")
            tk.Label(st, textvariable=var, font=BOLD, bg=COL["tile"], width=3).pack(side="left")
            tk.Button(st, text="+", width=2, font=BOLD, bg="white", relief="flat", cursor="hand2",
                      command=lambda v=var: v.set(min(20, v.get() + 1))).pack(side="left")
            make_button(card, "ADD", lambda a=(name, price), v=var: self.add_topping(a, v.get()), "primary",
                        font=(FONT, 8, "bold"), pady=3, padx=24).pack(pady=(2, 6))
            hover_border(border, COL["edge"], COL["orange"])

        if len(rows) == 0:
            tk.Label(inner, text="No toppings found.", font=ENTRY_FONT, bg="white", fg=COL["gray"]).grid(row=0, column=0, pady=30, padx=10)

    def add_addon(self):
        if self.app.role != "admin":
            return
        AddonWindow(self, self.app.db, after_save=self.refresh_addons)

    def edit_addon(self):
        if self.app.role != "admin":
            return
        selected = getattr(self, "selected_addon_id", None)
        if selected is None:
            messagebox.showinfo("Select topping", "Click a topping card first, then choose Edit Selected Topping.")
            return
        row = next((r for r in self.app.db.addons() if r[0] == selected), None)
        if row:
            AddonWindow(self, self.app.db, addon=row, after_save=self.refresh_addons)

    def refresh_addons(self):
        self.qty_vars = {}
        self.draw_categories()
        self.draw_addons()

    def add_topping(self, addon, qty):
        name, price = addon
        line = self.app.get_line(self.app.sel_line)
        if line is None:
            messagebox.showwarning("No item", "Add a product to your order first, then pick a topping.")
            return
        if line["qty"] > 1:
            # hiwalay na line para isang cup lang yung may topping
            line["qty"] -= 1
            new = dict(line, id=self.app.new_line_id(), qty=1, toppings=[dict(t) for t in line["toppings"]])
            self.app.cart.insert(self.app.cart.index(line) + 1, new)
            line = new
            self.app.sel_line = new["id"]
        for t in line["toppings"]:
            if t["name"] == name:
                t["qty"] += qty
                break
        else:
            line["toppings"].append({"name": name, "price": float(price), "qty": qty})
        self.draw_order()

    # ----- order (kanan) -----
    def draw_order(self):
        inner = self.order_sf.inner
        for w in inner.winfo_children():
            w.destroy()
        if not self.app.cart:
            tk.Label(inner, text="Your order is empty.\nGo back to the menu to add items.", font=NORMAL,
                     bg=COL["tile"], fg=COL["gray"], justify="center").pack(pady=40, padx=20)
        for l in self.app.cart:
            sel = (l["id"] == self.app.sel_line)
            edge = tk.Frame(inner, bg=COL["orange"] if sel else COL["tile"], padx=2, pady=2)
            edge.pack(fill="x", padx=6, pady=4)
            row = tk.Frame(edge, bg="white" if sel else COL["tile"], padx=8, pady=6)
            row.pack(fill="x")
            bg = row["bg"]
            top = tk.Frame(row, bg=bg)
            top.pack(fill="x")
            tk.Label(top, text=line_label(l), font=BOLD, bg=bg, fg=COL["text"], anchor="w", wraplength=210, justify="left").pack(side="left")
            tk.Label(top, text=money(line_total(l)), font=BOLD, bg=bg, fg=COL["text"]).pack(side="right")
            tops = toppings_text(l)
            tk.Label(row, text=("+ " + tops) if tops else "No toppings", font=TINY, bg=bg,
                     fg=COL["orange2"] if tops else COL["gray"], anchor="w", wraplength=290, justify="left").pack(fill="x")
            if l["comment"]:
                tk.Label(row, text="\u201c" + l["comment"] + "\u201d", font=(FONT, 8, "italic"), bg=bg, fg=COL["gray"],
                         anchor="w", wraplength=290, justify="left").pack(fill="x")
            bot = tk.Frame(row, bg=bg)
            bot.pack(fill="x", pady=(4, 0))
            lid = l["id"]
            tk.Button(bot, text="\u2212", width=2, font=BOLD, bg=COL["soft"], relief="flat", cursor="hand2",
                      command=lambda i=lid: self.minus(i)).pack(side="left")
            tk.Label(bot, text=str(l["qty"]), font=BOLD, bg=bg, width=3).pack(side="left")
            tk.Button(bot, text="+", width=2, font=BOLD, bg=COL["soft"], relief="flat", cursor="hand2",
                      command=lambda i=lid: self.plus(i)).pack(side="left")
            if l["toppings"]:
                tk.Button(bot, text="clear toppings", font=TINY, bg=bg, fg=COL["orange2"], relief="flat", bd=0, cursor="hand2",
                          command=lambda i=lid: self.clear_toppings(i)).pack(side="left", padx=10)
            tk.Button(bot, text="\u2715", font=(FONT, 9, "bold"), bg=bg, fg=COL["red"], relief="flat", bd=0, cursor="hand2",
                      command=lambda i=lid: self.remove(i)).pack(side="right")
            self.bind_select(edge, lid)
        self.total_lbl.config(text="Total: " + money(self.app.cart_total()))
        self.sync_controls()

    def bind_select(self, widget, lid):
        if not isinstance(widget, tk.Button):
            widget.bind("<Button-1>", lambda e, i=lid: self.select_line(i), add="+")
            for c in widget.winfo_children():
                self.bind_select(c, lid)

    def select_line(self, lid):
        self.app.sel_line = lid
        self.draw_order()

    def sync_controls(self):
        line = self.app.get_line(self.app.sel_line)
        self.comment_e.delete(0, tk.END)
        if line:
            self.comment_e.insert(0, line["comment"])
        can_temp = bool(line and line["category"] in TEMP_CATS)
        self.temp_var.set(line["temp"] if can_temp and line["temp"] else "Hot")
        for rb in self.temp_btns:
            rb.config(state="normal" if can_temp else "disabled")
        self.comment_e.config(state="normal" if line else "disabled")

    def set_line_temp(self):
        line = self.app.get_line(self.app.sel_line)
        if line and line["category"] in TEMP_CATS:
            line["temp"] = self.temp_var.get()
            self.draw_order()

    def save_comment(self):
        line = self.app.get_line(self.app.sel_line)
        if line:
            line["comment"] = self.comment_e.get().strip()[:60]

    def plus(self, lid):
        self.app.plus_line(lid)
        self.draw_order()

    def minus(self, lid):
        self.app.minus_line(lid)
        self.draw_order()

    def remove(self, lid):
        self.app.remove_line(lid)
        self.draw_order()

    def clear_toppings(self, lid):
        l = self.app.get_line(lid)
        if l:
            l["toppings"] = []
        self.draw_order()

    def checkout(self):
        if not self.app.cart:
            messagebox.showwarning("Empty Cart", "Add at least one item before checking out.")
            return
        self.app.show(CheckoutPage)


# ---------- checkout (cash lang) ----------
class CheckoutPage(MainPage):
    METHOD = "Cash"

    def on_show(self):
        self.reset()
        left = tk.Frame(self.content, bg=COL["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 22))
        tk.Label(left, text="Your Order", font=TITLE, bg=COL["bg"], fg=COL["text"]).pack(anchor="w")
        tk.Label(left, text="Review the items before taking payment", font=SMALL, bg=COL["bg"], fg=COL["text"]).pack(anchor="w", pady=(0, 12))

        self.tree = ttk.Treeview(left, columns=("name", "top", "qty", "price", "sub"), show="headings", height=12)
        for col, text, w, anc in [("name", "Item", 180, "w"), ("top", "Toppings", 260, "w"), ("qty", "Qty", 60, "center"),
                                  ("price", "Unit Price", 120, "e"), ("sub", "Subtotal", 130, "e")]:
            self.tree.heading(col, text=text, anchor="center")
            self.tree.column(col, width=w, anchor=anc)
        self.tree.tag_configure("odd", background=COL["zebra"])
        self.tree.pack(fill="both", expand=True)
        for n, l in enumerate(self.app.cart):
            self.tree.insert("", "end", tags=("odd" if n % 2 else "",),
                             values=(line_label(l), toppings_text(l) or "-", l["qty"], money(line_unit(l)), money(line_total(l))))

        border = tk.Frame(self.content, bg=COL["edge"], padx=1, pady=1, width=370)
        border.pack(side="right", fill="y")
        border.pack_propagate(False)
        wrap = tk.Frame(border, bg="white")
        wrap.pack(fill="both", expand=True)
        right = tk.Frame(wrap, bg="white")
        right.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(right, text="Payment", font=(FONT, 15, "bold"), bg="white", fg=COL["text"]).pack(anchor="w")
        tk.Label(right, text="Cash only", font=SMALL, bg="white", fg=COL["gray"]).pack(anchor="w", pady=(0, 10))

        self.total = self.app.cart_total()
        tk.Label(right, text="Total due", font=SMALL, bg="white", fg=COL["gray"]).pack(anchor="w")
        tk.Label(right, text=money(self.total), font=(FONT, 22, "bold"), bg="white", fg=COL["orange2"]).pack(anchor="w", pady=(0, 10))
        tk.Frame(right, bg=COL["line"], height=1).pack(fill="x", pady=(0, 12))

        tk.Label(right, text="Cash received", font=BOLD, bg="white", fg=COL["gray"]).pack(anchor="w")
        self.cash_e = make_entry(right)
        self.cash_e.pack(fill="x", ipady=9, pady=(3, 6))
        self.cash_e.bind("<KeyRelease>", lambda e: self.show_change())
        self.cash_e.bind("<Return>", lambda e: self.confirm())
        self.change_lbl = tk.Label(right, text="Change: PHP 0.00", font=(FONT, 13, "bold"), bg="white", fg=COL["green"])
        self.change_lbl.pack(anchor="w", pady=(2, 10))

        quick = tk.Frame(right, bg="white")
        quick.pack(anchor="w")
        make_button(quick, "", lambda: self.fill_cash(self.total), "ghost", font=SMALL, pady=4, padx=10).pack(side="left", padx=(0, 4))
        for amt in ():
            make_button(quick, str(amt), lambda a=amt: self.fill_cash(a), "ghost", font=SMALL, pady=4, padx=8).pack(side="left", padx=2)

        make_button(right, "Confirm Order", self.confirm, "brand", font=BTN_FONT, pady=11).pack(side="bottom", fill="x")
        make_button(right, "Back to Order", lambda: self.app.show(CustomizePage), "secondary", pady=8).pack(side="bottom", fill="x", pady=(0, 8))
        self.cash_e.focus_set()

    def fill_cash(self, amount):
        self.cash_e.delete(0, tk.END)
        self.cash_e.insert(0, ("%.2f" % amount).rstrip("0").rstrip("."))
        self.show_change()

    def get_cash(self):
        try:
            return float(self.cash_e.get().replace(",", "").strip())
        except (ValueError, AttributeError):
            return None

    def show_change(self):
        cash = self.get_cash()
        if cash is None:
            self.change_lbl.config(text="Change: PHP 0.00", fg=COL["green"])
        elif cash < self.total:
            self.change_lbl.config(text="Short by " + money(self.total - cash), fg=COL["red"])
        else:
            self.change_lbl.config(text="Change: " + money(cash - self.total), fg=COL["green"])

    def confirm(self):
        if not self.app.cart:
            messagebox.showwarning("Empty Cart", "Add at least one item before checking out.")
            return
        cash = self.get_cash()
        if cash is None or cash < self.total:
            messagebox.showwarning("Cash", "Enter the cash received (it must cover the total).")
            return
        items = []
        for l in self.app.cart:
            items.append({"product_id": l["product_id"], "name": line_label(l), "base_name": l["name"],
                          "qty": l["qty"], "price": line_unit(l), "toppings": l["toppings"], "comment": l["comment"]})
        try:
            order_id, when = self.app.db.save_order(items, self.METHOD, self.total, self.app.username, cash)
        except ValueError as err:
            messagebox.showerror("Cannot complete order", str(err))
            return
        text = make_receipt(order_id, when, items, self.METHOD, self.total, self.app.username, cash)
        self.app.cart = []
        self.app.sel_line = None
        self.app.show(POSPage)
        ReceiptWindow(self.app, text, order_id)


# ---------- dashboard (Sales History & Reports) ----------
class DashboardPage(MainPage):
    PERIODS = ["Today", "This Week", "This Month", "All Time"]

    def on_show(self):
        self.draw()

    def draw(self):
        self.reset()
        if not hasattr(self, "period"):
            self.period = "Today"

        head = tk.Frame(self.content, bg=COL["bg"])
        head.pack(fill="x")
        titles = tk.Frame(head, bg=COL["bg"])
        titles.pack(side="left")
        tk.Label(titles, text="Sales History & Reports", font=TITLE, bg=COL["bg"], fg=COL["text"]).pack(anchor="w")
        tk.Label(titles, text="Filter by date range, review orders, export to CSV", font=SMALL, bg=COL["bg"], fg=COL["text"]).pack(anchor="w")
        acts = tk.Frame(head, bg=COL["bg"])
        acts.pack(side="right", anchor="s")
        make_button(acts, "Export CSV", self.export, "outline", font=SMALL, pady=6).pack(side="right", padx=(8, 0))
        make_button(acts, "+ Add Sales", lambda: self.app.show(POSPage), "outline", font=SMALL, pady=6).pack(side="right")
        make_button(acts, "Clear All Sales", self.clear_sales, "danger", font=SMALL, pady=6).pack(side="right", padx=(0, 8))

        toggle_row(self.content, self.PERIODS, self.period, self.set_period).pack(anchor="w", pady=(14, 14))

        s = self.app.db.summary(self.period)
        low = self.app.db.low_stock_count()
        stats = tk.Frame(self.content, bg=COL["bg"])
        stats.pack(fill="x")
        boxes = [("Total sales", money(s["sales"]), 1), ("Total orders", str(s["orders"]), 1),
                 ("Best-seller", "%s ( %d sold )" % (s["best"], s["best_qty"]), 2),
                 ("Low / out of stock", str(low), 1)]
        for i, (title, value, weight) in enumerate(boxes):
            stats.grid_columnconfigure(i, weight=weight, uniform="stat")
            b = tk.Frame(stats, bg=COL["edge"], padx=1, pady=1)
            b.grid(row=0, column=i, sticky="nsew", padx=(0, 12 if i < len(boxes) - 1 else 0))
            inner = tk.Frame(b, bg="white", padx=16, pady=10)
            inner.pack(fill="both", expand=True)
            tk.Label(inner, text=title, bg="white", fg=COL["gray"], font=TINY).pack(anchor="w")
            color = COL["red"] if (title.startswith("Low") and low) else COL["text"]
            tk.Label(inner, text=value, bg="white", fg=color, font=(FONT, 14, "bold")).pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self.content, bg=COL["bg"])
        body.pack(fill="both", expand=True, pady=(14, 0))

        # breakdown sa kanan
        bd = tk.Frame(body, bg=COL["edge"], padx=1, pady=1, width=360)
        bd.pack(side="right", fill="y", padx=(16, 0))
        bd.pack_propagate(False)
        bdi = tk.Frame(bd, bg="white", padx=14, pady=12)
        bdi.pack(fill="both", expand=True)
        tk.Label(bdi, text="Order Breakdown", font=(FONT, 13, "bold"), bg="white", fg=COL["text"]).pack(anchor="w")
        self.bd_sub = tk.Label(bdi, text="Order#  \u00b7  Date and Time  \u00b7  Payment", font=TINY, bg="white", fg=COL["gray"])
        self.bd_sub.pack(anchor="w", pady=(0, 8))
        self.bd_text = tk.Text(bdi, font=("Consolas", 9), bg="white", fg=COL["text"], relief="flat", wrap="none", height=10)
        self.bd_text.pack(fill="both", expand=True)
        self.bd_text.insert("1.0", "Select an order on the left to see its items.")
        self.bd_text.config(state="disabled")

        tf = tk.Frame(body, bg=COL["bg"])
        tf.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=("id", "dt", "items", "pay", "total"), show="headings", height=12)
        for col, text, w, anc, stretch in [("id", "Order#", 90, "center", False), ("dt", "Date and time", 175, "center", False),
                                           ("items", "Items", 260, "w", True), ("pay", "Payment", 90, "center", False),
                                           ("total", "Total", 120, "e", False)]:
            self.tree.heading(col, text=text, anchor="center")
            self.tree.column(col, width=w, anchor=anc, stretch=stretch)
        self.tree.tag_configure("odd", background=COL["zebra"])
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.order_map = {}
        for n, o in enumerate(self.app.db.orders(self.period)):
            self.order_map[str(o[0])] = o
            try:
                names = ", ".join("%s x%s" % (i["name"], i["qty"]) for i in json.loads(o[2]))
            except Exception:
                names = ""
            if len(names) > 48:
                names = names[:46] + "\u2026"
            self.tree.insert("", "end", iid=str(o[0]), tags=("odd" if n % 2 else "",),
                             values=(o[0], o[1], names, o[3], money(o[4])))
        self.tree.bind("<<TreeviewSelect>>", self.show_breakdown)
        self.tree.bind("<Double-1>", self.open_receipt)

    def set_period(self, p):
        self.period = p
        self.draw()

    def clear_sales(self):
        order_count = self.app.db.con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if not order_count:
            messagebox.showinfo("Clear Sales", "There are no sales orders to clear.")
            return
        confirmed = messagebox.askyesno(
            "Clear All Sales",
            "Permanently delete all %d sales order(s) from Sales History and Reports?\n\n"
            "This cannot be undone. Current inventory stock will not change." % order_count,
            default=messagebox.NO)
        if not confirmed:
            return
        try:
            deleted = self.app.db.clear_orders()
        except sqlite3.Error as err:
            messagebox.showerror("Clear Sales Failed", "Could not clear sales orders:\n%s" % err)
            return
        messagebox.showinfo("Clear Sales", "%d sales order(s) cleared. Inventory stock was not changed." % deleted)
        self.draw()

    def order_text(self, o):
        try:
            items = json.loads(o[2])
        except Exception:
            items = []
        return make_receipt(o[0], o[1], items, o[3], o[4], o[5], o[6])

    def show_breakdown(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        o = self.order_map[sel[0]]
        self.bd_sub.config(text="Order #%s  \u00b7  %s  \u00b7  %s" % (o[0], o[1], o[3]))
        self.bd_text.config(state="normal")
        self.bd_text.delete("1.0", tk.END)
        self.bd_text.insert("1.0", self.order_text(o))
        self.bd_text.config(state="disabled")

    def open_receipt(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        o = self.order_map[sel[0]]
        ReceiptWindow(self.app, self.order_text(o), o[0])

    def export(self):
        rows = self.app.db.orders(self.period)
        if not rows:
            messagebox.showinfo("Export", "No orders to export for this period.")
            return
        fname = "sales_%s_%s.csv" % (self.period.replace(" ", "_").lower(), datetime.now().strftime("%Y%m%d"))
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV (Excel)", "*.csv")], initialfile=fname)
        if not path:
            return
        grand = 0
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Order #", "Date/Time", "Cashier", "Payment", "Items", "Total"])
            for o in rows:
                try:
                    parts = []
                    for i in json.loads(o[2]):
                        txt = "%s x%s" % (i["name"], i["qty"])
                        if i.get("toppings"):
                            txt += " [+" + ", ".join("%s x%s" % (t["name"], t["qty"]) for t in i["toppings"]) + "]"
                        parts.append(txt)
                    names = ", ".join(parts)
                except Exception:
                    names = ""
                w.writerow([o[0], o[1], o[5] or "", o[3], names, "%.2f" % o[4]])
                grand += o[4]
            w.writerow([])
            w.writerow(["", "", "", "", "TOTAL", "%.2f" % grand])
        messagebox.showinfo("Export", "Saved to:\n" + path)


# ---------- add / edit product window ----------
class ProductWindow(tk.Toplevel):
    def __init__(self, parent, db, product=None, after_save=None):
        super().__init__(parent)
        self.db = db
        self.product = product
        self.after_save = after_save
        self.new_image = None
        self.title("Edit Product" if product else "Add Product")
        self.configure(bg=COL["card"], padx=30, pady=24)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        tk.Label(self, text=self.title(), font=BIG, bg=COL["card"], fg=COL["text"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self.name_e = make_entry(self, auth=True)
        self.price_e = make_entry(self, auth=True)
        self.stock_e = make_entry(self, auth=True)
        self.cat_var = tk.StringVar()
        self.cat_box = ttk.Combobox(self, textvariable=self.cat_var, values=db.all_categories(), font=ENTRY_FONT, width=28)

        fields = [("Name", self.name_e), ("Category", self.cat_box),
                  ("Price (PHP)", self.price_e), ("Stock", self.stock_e)]
        r = 1
        for text, widget in fields:
            label(self, text).grid(row=r, column=0, columnspan=2, sticky="w")
            pad = 4 if widget is self.cat_box else 6
            widget.grid(row=r + 1, column=0, columnspan=2, sticky="ew", ipady=pad, pady=(2, 10))
            r += 2

        self.img_lbl = tk.Label(self, text="No new image", font=SMALL, bg=COL["card"], fg=COL["gray"])
        make_button(self, "Choose photo\u2026", self.pick_image, "secondary", font=SMALL, pady=5).grid(row=r, column=0, sticky="w")
        self.img_lbl.grid(row=r, column=1, sticky="w", padx=8)
        r += 1
        bar = tk.Frame(self, bg=COL["card"])
        bar.grid(row=r, column=0, columnspan=2, sticky="e", pady=(18, 0))
        make_button(bar, "Cancel", self.destroy, "secondary").pack(side="left", padx=4)
        make_button(bar, "Save", self.save, "brand").pack(side="left", padx=4)

        if product:
            self.name_e.insert(0, product[1])
            self.cat_var.set(product[2])
            self.price_e.insert(0, "%g" % product[3])
            self.stock_e.insert(0, str(product[4]))
            if product[5]:
                self.img_lbl.config(text="Current photo kept unless you pick a new one")
        self.name_e.focus_set()
        center_window(self, parent)
        self.grab_set()

    def pick_image(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if path:
            self.new_image = path
            self.img_lbl.config(text=os.path.basename(path)[:30])

    def save(self):
        name = self.name_e.get().strip()
        cat = self.cat_var.get().strip()
        if not name or not cat:
            messagebox.showwarning("Required", "Name and category are required.", parent=self)
            return
        try:
            price = float(self.price_e.get().replace(",", ""))
            stock = int(self.stock_e.get())
            if price < 0 or stock < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid", "Price must be a number and stock a whole number (0 or more).", parent=self)
            return

        fname = None
        if self.new_image:
            try:
                fname = copy_product_photo(self.new_image, name)
            except OSError as err:
                messagebox.showerror("Image", "Could not copy image: %s" % err, parent=self)
                return
        elif self.product is None:
            fname = make_placeholder(name, cat)

        if self.product:
            self.db.edit_product(self.product[0], name, cat, price, stock, fname or self.product[5])
        else:
            self.db.add_product(name, cat, price, stock, fname)
        if self.after_save:
            self.after_save()
        self.destroy()


# ---------- add / edit topping window ----------
class AddonWindow(tk.Toplevel):
    def __init__(self, parent, db, addon=None, after_save=None):
        super().__init__(parent)
        self.db = db
        self.addon = addon
        self.after_save = after_save
        self.new_image = None
        self.title("Edit Topping" if addon else "Add Topping")
        self.configure(bg=COL["card"], padx=30, pady=24)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        tk.Label(self, text=self.title(), font=BIG, bg=COL["card"], fg=COL["text"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self.name_e = make_entry(self, auth=True)
        self.cat_var = tk.StringVar()
        self.cat_box = ttk.Combobox(self, textvariable=self.cat_var,
                                    values=db.addon_categories(), font=ENTRY_FONT, width=28)
        self.price_e = make_entry(self, auth=True)
        fields = [("Topping Name", self.name_e),
                  ("Category (pwede mag-type ng bago)", self.cat_box),
                  ("Price (PHP)", self.price_e)]
        r = 1
        for text, widget in fields:
            label(self, text).grid(row=r, column=0, columnspan=2, sticky="w")
            widget.grid(row=r + 1, column=0, columnspan=2, sticky="ew",
                        ipady=4 if widget is self.cat_box else 6, pady=(2, 10))
            r += 2

        self.img_lbl = tk.Label(self, text="No new image selected", font=SMALL,
                                bg=COL["card"], fg=COL["gray"])
        make_button(self, "Choose photo...", self.pick_image, "secondary",
                    font=SMALL, pady=5).grid(row=r, column=0, sticky="w")
        self.img_lbl.grid(row=r, column=1, sticky="w", padx=8)
        r += 1
        bar = tk.Frame(self, bg=COL["card"])
        bar.grid(row=r, column=0, columnspan=2, sticky="e", pady=(18, 0))
        make_button(bar, "Cancel", self.destroy, "secondary").pack(side="left", padx=4)
        make_button(bar, "Save", self.save, "brand").pack(side="left", padx=4)

        if addon:
            self.name_e.insert(0, addon[1])
            self.cat_var.set(addon[2])
            self.price_e.insert(0, "%g" % addon[3])
            self.img_lbl.config(text=("Current photo: " + os.path.basename(addon[4])) if addon[4] else "No current photo")
        self.name_e.focus_set()
        center_window(self, parent)
        self.grab_set()

    def pick_image(self):
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if path:
            self.new_image = path
            self.img_lbl.config(text=os.path.basename(path)[:30])

    def save(self):
        name = self.name_e.get().strip()
        category = self.cat_var.get().strip()
        if not name or not category:
            messagebox.showwarning("Required", "Topping name and category are required.", parent=self)
            return
        try:
            price = float(self.price_e.get().replace(",", ""))
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid price", "Enter a valid price (0 or more).", parent=self)
            return

        icon = self.addon[4] if self.addon else None
        if self.new_image:
            try:
                icon = copy_product_photo(self.new_image, name)
            except OSError as err:
                messagebox.showerror("Image", "Could not copy image: %s" % err, parent=self)
                return

        if self.addon:
            self.db.edit_addon(self.addon[0], name, category, price, icon)
        else:
            self.db.add_addon(name, category, price, icon)

        addon_img_cache.clear()
        if self.after_save:
            self.after_save()
        self.destroy()


# ---------- inventory ----------
class InventoryPage(MainPage):
    def on_show(self):
        self.reset()
        head = tk.Frame(self.content, bg=COL["bg"])
        head.pack(fill="x", pady=(0, 14))
        titles = tk.Frame(head, bg=COL["bg"])
        titles.pack(side="left")
        tk.Label(titles, text="Inventory", font=TITLE, bg=COL["bg"], fg=COL["text"]).pack(anchor="w")
        tk.Label(titles, text="Manage your stock, photo, and stock levels", font=SMALL, bg=COL["bg"], fg=COL["text"]).pack(anchor="w")

        acts = tk.Frame(head, bg=COL["bg"])
        acts.pack(side="right", anchor="s")
        self.search_e = PEntry(acts, "Search products...", font=SMALL, bg="white", fg=COL["gray"], relief="flat", bd=0,
                               highlightthickness=1, highlightbackground=COL["edge"], highlightcolor=COL["orange"], width=22)
        self.search_e.pack(side="left", ipady=6, padx=(0, 10))
        self.search_e.bind("<KeyRelease>", lambda e: self.fill_table())
        make_button(acts, "+ Add Product", self.add, "primary", font=SMALL, pady=6).pack(side="left", padx=(0, 8))
        make_button(acts, "Edit", self.edit, "outline", font=SMALL, pady=6, padx=18).pack(side="left", padx=(0, 8))
        make_button(acts, "Restock", self.restock, "outline", font=SMALL, pady=6, padx=14).pack(side="left", padx=(0, 8))
        self.toggle_btn = make_button(acts, "Disable", self.toggle_active, "danger", font=SMALL, pady=6, padx=14)
        self.toggle_btn.pack(side="left")

        tf = tk.Frame(self.content, bg=COL["bg"])
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, style="Inv.Treeview", columns=("name", "category", "price", "stock", "status"),
                                 show="tree headings", height=10)
        self.tree.heading("#0", text="Photo", anchor="center")
        self.tree.column("#0", width=90, anchor="center", stretch=False)
        for col, text, w, anc in [("name", "Product", 260, "center"), ("category", "Category", 140, "center"),
                                  ("price", "Price", 140, "center"), ("stock", "Stock", 100, "center"),
                                  ("status", "Status", 140, "center")]:
            self.tree.heading(col, text=text, anchor="center")
            self.tree.column(col, width=w, anchor=anc)
        self.tree.tag_configure("odd", background=COL["zebra"])
        self.tree.tag_configure("low", foreground=COL["orange2"])
        self.tree.tag_configure("out", background=COL["orange"], foreground="#ff1f1f")
        self.tree.tag_configure("off", foreground="#a39a8c")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.edit())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_toggle())
        self.fill_table()

    def fill_table(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for n, (pid, name, cat, price, stock, img_file, active) in enumerate(self.app.db.inventory_rows(self.search_e.value())):
            tags = []
            if n % 2:
                tags.append("odd")
            if not active:
                status = "Disabled"
                tags.append("off")
            elif stock <= 0:
                status = "Out of Stock"
                tags.append("out")
            elif stock <= LOW_STOCK_LEVEL:
                status = "Low Stock"
                tags.append("low")
            else:
                status = "In Stock"
            img = get_product_img(img_file, 44)
            self.tree.insert("", "end", iid=str(pid), image=img if img else "",
                             values=(name, cat, money(price), stock, status), tags=tuple(tags))
        self.update_toggle()

    def update_toggle(self):
        sel = self.tree.selection()
        off = bool(sel) and "off" in self.tree.item(sel[0], "tags")
        self.toggle_btn.config(text="Enable" if off else "Disable")

    def selected_id(self, action):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select a product to %s." % action)
            return None
        return int(sel[0])

    def add(self):
        ProductWindow(self, self.app.db, after_save=self.fill_table)

    def edit(self):
        pid = self.selected_id("edit")
        if pid:
            ProductWindow(self, self.app.db, self.app.db.product(pid), after_save=self.fill_table)

    def restock(self):
        pid = self.selected_id("restock")
        if not pid:
            return
        qty = simpledialog.askinteger("Restock", "How many units to add?", minvalue=1, parent=self)
        if qty:
            self.app.db.add_stock(pid, qty)
            self.fill_table()
            self.tree.selection_set(str(pid))

    def toggle_active(self):
        pid = self.selected_id("disable or enable")
        if not pid:
            return
        p = self.app.db.product(pid)
        if self.app.db.is_active(pid):
            if messagebox.askyesno("Disable product", "Disable '%s'?\nIt will be hidden from the POS (past orders are kept)." % p[1]):
                self.app.db.set_active(pid, False)
                self.app.cart = [l for l in self.app.cart if l["product_id"] != pid]
        else:
            self.app.db.set_active(pid, True)
        self.fill_table()
        self.tree.selection_set(str(pid))


# ---------- main app ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(SHOP_NAME)
        self.geometry("1280x780")
        self.minsize(1050, 700)
        self.configure(bg=COL["bg"])
        icon = get_logo(64)
        if icon:
            try:
                self.iconphoto(True, icon)
            except tk.TclError:
                pass
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass
        self.fullscreen = False
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))
        self.bind_all("<MouseWheel>", self.on_wheel)
        self.bind_all("<Button-4>", self.on_wheel)
        self.bind_all("<Button-5>", self.on_wheel)

        self.setup_style()
        self.db = DB()
        self.role = None
        self.username = None
        self.cart = []
        self.temp = "Hot"
        self.selected_pid = None
        self.sel_line = None
        self.line_seq = 0
        self.reset_user = None
        self.fails = 0
        self.locked_until = 0.0

        self.pages = {}
        for cls in (LoginPage, SignupPage, ForgotPage, ResetPage, POSPage, CustomizePage, CheckoutPage,
                    DashboardPage, InventoryPage):
            page = cls(self, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[cls] = page
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.show(LoginPage)

    def setup_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        for name, rh in (("Treeview", 40), ("Inv.Treeview", 58)):
            st.configure(name, rowheight=rh, font=(FONT, 10), background="white", fieldbackground="white",
                         foreground=COL["text"], borderwidth=0)
            st.configure(name + ".Heading", font=(FONT, 10, "bold"), background=COL["dark"], foreground="white",
                         relief="flat", padding=(8, 10))
            st.map(name, background=[("selected", COL["orange"])], foreground=[("selected", "white")])
            st.map(name + ".Heading", background=[("active", COL["dark2"])])
        st.configure("TCombobox", padding=4, fieldbackground=COL["field"], background=COL["field"])
        st.configure("Vertical.TScrollbar", background=COL["soft"], troughcolor=COL["bg"], borderwidth=0)

    def on_wheel(self, e):
        # i-scroll yung scroll area na nasa ilalim ng mouse
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            return
        while w is not None:
            if isinstance(w, ScrollFrame):
                if getattr(e, "num", 0) == 4:
                    step = -1
                elif getattr(e, "num", 0) == 5:
                    step = 1
                else:
                    step = -1 if e.delta > 0 else 1
                try:
                    w.canvas.yview_scroll(step, "units")
                except tk.TclError:
                    pass
                return
            w = getattr(w, "master", None)

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)

    def show(self, cls):
        # admin lang sa dashboard at inventory
        if cls in (DashboardPage, InventoryPage) and self.role != "admin":
            if self.role is None:
                cls = LoginPage
            else:
                messagebox.showwarning("Not allowed", "Admin access only.")
                return
        if cls in (POSPage, CustomizePage, CheckoutPage) and self.role is None:
            cls = LoginPage
        page = self.pages[cls]
        page.tkraise()
        if hasattr(page, "on_show"):
            page.on_show()

    # ----- cart (bawat line = isang item na may temp, toppings, comment) -----
    def new_line_id(self):
        self.line_seq += 1
        return self.line_seq

    def get_line(self, lid):
        for l in self.cart:
            if l["id"] == lid:
                return l
        return None

    def fix_selection(self):
        if self.get_line(self.sel_line) is None:
            self.sel_line = self.cart[-1]["id"] if self.cart else None

    def cart_qty(self, pid):
        return sum(l["qty"] for l in self.cart if l["product_id"] == pid)

    def add_to_cart(self, row):
        pid, name, cat, price, stock, _img = row[:6]
        if self.cart_qty(pid) >= stock:
            messagebox.showwarning("Stock limit", "Only %d of '%s' available." % (stock, name))
            return
        temp = self.temp if cat in TEMP_CATS else ""
        for l in self.cart:
            if l["product_id"] == pid and l["temp"] == temp and not l["toppings"] and not l["comment"]:
                l["qty"] += 1
                self.sel_line = l["id"]
                return
        line = {"id": self.new_line_id(), "product_id": pid, "name": name, "category": cat, "price": float(price),
                "qty": 1, "temp": temp, "toppings": [], "comment": ""}
        self.cart.append(line)
        self.sel_line = line["id"]

    def plus_line(self, lid):
        l = self.get_line(lid)
        if not l:
            return
        p = self.db.product(l["product_id"])
        if p and self.cart_qty(l["product_id"]) >= p[4]:
            messagebox.showwarning("Stock limit", "Only %d of '%s' available." % (p[4], l["name"]))
            return
        l["qty"] += 1

    def minus_line(self, lid):
        l = self.get_line(lid)
        if not l:
            return
        if l["qty"] > 1:
            l["qty"] -= 1
        else:
            self.remove_line(lid)

    def remove_line(self, lid):
        self.cart = [l for l in self.cart if l["id"] != lid]
        self.fix_selection()

    def cart_total(self):
        return sum(line_total(l) for l in self.cart)

    def logout(self):
        self.username = None
        self.role = None
        self.cart = []
        self.sel_line = None
        self.selected_pid = None
        self.show(LoginPage)


if __name__ == "__main__":
    App().mainloop()
