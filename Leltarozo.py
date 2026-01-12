import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import pymongo
from bson.objectid import ObjectId
import bcrypt
import sys
import os

# --- MEGJELENÉS ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- ADATBÁZIS KAPCSOLAT ---
# FONTOS: Ide majd azt a MongoDB linket írd, amit a "leltar_user"-nek hozol létre (lásd lejjebb az útmutatót)
# NE az admin jelszavadat használd!
URI = "mongodb+srv://leltar_user:LpoegGd0Nv2YR04D@cluster0.vistb9x.mongodb.net/?appName=Cluster0"

try:
    # A connect=False segít, hogy ne fagyjon le induláskor, ha nincs net
    client = pymongo.MongoClient(URI, serverSelectionTimeoutMS=5000)
    db = client["ruha_leltar_db"]
    raktar_col = db["raktar"]
    kiadott_col = db["kiadott_ruhak"]
    tajegysegek_col = db["tajegysegek"]
    users_col = db["users"]

    # Gyors kapcsolat teszt
    # client.server_info()
except Exception as e:
    # Ha exe-ként fut, akkor is kell látni a hibát
    pass


# --- JELSZÓ KEZELÉS (BCRYPT) ---
def hash_pass(password):
    """Jelszó titkosítása biztonságosan"""
    # A bcrypt byte-okat vár (encode), és byte-ot ad vissza
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed  # Ezt mentjük az adatbázisba


def check_pass(plain_password, stored_hash):
    """Jelszó ellenőrzése"""
    try:
        # Ha a stored_hash stringként jön az adatbázisból, vissza kell alakítani byte-ra
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        return bcrypt.checkpw(plain_password.encode('utf-8'), stored_hash)
    except ValueError:
        return False


# ==========================================
# 1. BEJELENTKEZŐ ÉS REGISZTRÁCIÓS ABLAK
# ==========================================
class LoginApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Bejelentkezés - Leltár Pro")
        self.root.geometry("400x450")
        self.root.resizable(False, False)

        ctk.CTkLabel(self.root, text="Leltár Pro v1.1", font=("Arial", 24, "bold"), text_color="#1A8F63").pack(
            pady=(40, 20))

        self.frame = ctk.CTkFrame(self.root)
        self.frame.pack(pady=10, padx=30, fill="both", expand=True)

        ctk.CTkLabel(self.frame, text="Felhasználónév:").pack(pady=(20, 5))
        self.user_entry = ctk.CTkEntry(self.frame, width=250)
        self.user_entry.pack(pady=5)

        ctk.CTkLabel(self.frame, text="Jelszó:").pack(pady=(10, 5))
        self.pass_entry = ctk.CTkEntry(self.frame, width=250, show="*")
        self.pass_entry.pack(pady=5)

        ctk.CTkButton(self.frame, text="BELÉPÉS", command=self.login, width=200, height=40, fg_color="#1A8F63").pack(
            pady=20)

        ctk.CTkLabel(self.root, text="Nincs még fiókod?").pack(side="bottom", pady=(0, 5))
        ctk.CTkButton(self.root, text="Regisztráció", command=self.register_window, fg_color="transparent",
                      text_color="#3498db", hover=False).pack(side="bottom", pady=(0, 20))

        # Adatbázis kapcsolat ellenőrzése induláskor
        try:
            client.server_info()
        except:
            messagebox.showerror("Hálózati Hiba",
                                 "Nem sikerült kapcsolódni a szerverhez!\nEllenőrizd az internetkapcsolatot.")

        self.root.mainloop()

    def login(self):
        u = self.user_entry.get().strip()
        p = self.pass_entry.get().strip()

        try:
            # Itt már csak a felhasználónevet keressük először
            user = users_col.find_one({"username": u})

            if user and check_pass(p, user["password"]):
                is_admin = (user.get("role") == "admin")
                self.root.destroy()
                root = ctk.CTk()
                app = LeltarAppDB(root, is_admin=is_admin, user_name=u)
                root.mainloop()
            else:
                messagebox.showerror("Hiba", "Hibás felhasználónév vagy jelszó!")
        except Exception as e:
            messagebox.showerror("Hiba", f"Hiba a belépésnél: {e}")

    def register_window(self):
        top = ctk.CTkToplevel(self.root)
        top.geometry("300x350")
        top.title("Regisztráció")
        top.transient(self.root)
        top.grab_set()

        ctk.CTkLabel(top, text="Új fiók létrehozása", font=("Arial", 16, "bold")).pack(pady=20)
        u_ent = ctk.CTkEntry(top, placeholder_text="Felhasználónév")
        u_ent.pack(pady=10)
        p_ent = ctk.CTkEntry(top, placeholder_text="Jelszó", show="*")
        p_ent.pack(pady=10)

        def save():
            u = u_ent.get().strip()
            p = p_ent.get().strip()
            if not u or not p:
                messagebox.showwarning("Hiány", "Minden mezőt tölts ki!")
                return

            try:
                if users_col.find_one({"username": u}):
                    messagebox.showerror("Hiba", "Ez a felhasználónév már foglalt!")
                    return

                count = users_col.count_documents({})
                role = "admin" if count == 0 else "user"

                # Itt használjuk az új hash függvényt
                users_col.insert_one({
                    "username": u,
                    "password": hash_pass(p),
                    "role": role
                })
                msg = "Te vagy az első felhasználó, így ADMIN jogot kaptál!" if role == "admin" else "Sikeres regisztráció (Felhasználó szint)."
                messagebox.showinfo("Siker", msg)
                top.destroy()
            except Exception as e:
                messagebox.showerror("Hiba", f"Regisztrációs hiba: {e}")

        ctk.CTkButton(top, text="REGISZTRÁCIÓ", command=save, fg_color="#3498db").pack(pady=20)


# ==========================================
# 2. FŐ ALKALMAZÁS
# ==========================================
class LeltarAppDB:
    def __init__(self, root, is_admin=False, user_name="Vendég"):
        self.root = root
        self.is_admin = is_admin
        self.user_name = user_name

        role_text = "ADMIN" if self.is_admin else "FELHASZNÁLÓ"
        self.root.title(f"Leltár Pro v1.1 - {role_text} MÓD | Belépve: {self.user_name}")
        self.root.geometry("1300x800")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.COL_CONFIG = {
            "Kod": {"db_key": "kod", "label": "Kód", "width": 80},
            "Szemely": {"db_key": "szemely", "label": "Személy", "width": 150},
            "Nem": {"db_key": "nem", "label": "Nem", "width": 80},
            "Megnevezes": {"db_key": "nev", "label": "Megnevezés", "width": 200},
            "Szin": {"db_key": "szin", "label": "Szín", "width": 100},
            "Meret": {"db_key": "meret", "label": "Méret", "width": 70},
            "Tajegyseg": {"db_key": "tajegyseg", "label": "Tájegység", "width": 150},
            "Egyeb": {"db_key": "egyeb", "label": "Egyéb", "width": 250}
        }

        self.tajegysegek = ["Válassz..."]
        self.frissit_tajegyseg_listat()
        self.apply_treeview_style()
        self.create_widgets()

        try:
            self.frissit_mindent()
        except:
            pass

    def apply_treeview_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1d1d1d", foreground="white", fieldbackground="#1d1d1d", borderwidth=0,
                        font=("Arial", 10))
        style.configure("Treeview.Heading", background="#333333", foreground="white", borderwidth=1,
                        font=("Arial", 10, "bold"))
        style.map("Treeview", background=[('selected', '#1A8F63')], foreground=[('selected', 'white')])

    def frissit_tajegyseg_listat(self):
        try:
            docs = tajegysegek_col.find().sort("nev", 1)
            self.tajegysegek = ["Válassz..."] + [doc["nev"] for doc in docs]
        except:
            self.tajegysegek = ["Válassz..."]

    def create_widgets(self):
        self.main_container = ctk.CTkFrame(self.root, corner_radius=0)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self.main_container, segmented_button_selected_color="#1A8F63")
        self.tabview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.tab1 = self.tabview.add("📦 Raktár Készlet")
        self.tab2 = self.tabview.add("👤 Kiadott Ruhák")

        for tab in [self.tab1, self.tab2]:
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(2, weight=1)

        self.setup_raktar_tab()
        self.setup_kiadott_tab()

    def create_input_fields(self, parent, fields_list, target_dict):
        for key in fields_list:
            conf = self.COL_CONFIG[key]
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(side="left", padx=5, pady=2)
            ctk.CTkLabel(f, text=conf["label"], font=("Arial", 11)).pack(anchor="w")

            if key == "Tajegyseg":
                target_dict[key] = ctk.CTkOptionMenu(f, values=self.tajegysegek, width=130)
                target_dict[key].set("Válassz...")
            elif key == "Nem":
                target_dict[key] = ctk.CTkOptionMenu(f, values=["Válassz...", "Férfi", "Nő"], width=130)
                target_dict[key].set("Válassz...")
            else:
                target_dict[key] = ctk.CTkEntry(f, placeholder_text=conf["label"], width=130)

            target_dict[key].pack()

    # ==========================
    # RAKTÁR FÜL BEÁLLÍTÁSAI
    # ==========================
    def setup_raktar_tab(self):
        self.mode_var = tk.StringVar(value="Új felvitel")

        self.top_container = ctk.CTkFrame(self.tab1, fg_color="transparent", height=110)
        self.top_container.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        # --- FELVITEL / SZERKESZTÉS PANEL ---
        self.input_card = ctk.CTkFrame(self.top_container, fg_color="transparent")
        self.input_scroll = ctk.CTkScrollableFrame(self.input_card, orientation="horizontal", height=90,
                                                   fg_color="transparent")
        self.input_scroll.pack(fill="x", expand=True)
        self.entries = {}
        self.create_input_fields(self.input_scroll, ["Kod", "Nem", "Megnevezes", "Szin", "Meret", "Tajegyseg", "Egyeb"],
                                 self.entries)

        btn_box = ctk.CTkFrame(self.input_scroll, fg_color="transparent")
        btn_box.pack(side="left", padx=10, pady=10)

        self.btn_action_raktar = ctk.CTkButton(btn_box, text="✚ RÖGZÍTÉS", fg_color="#1A8F63", command=self.hozzaad_db,
                                               width=120, height=40)
        self.btn_action_raktar.pack(side="left", padx=5)

        ctk.CTkButton(btn_box, text="✖ ÜRÍTÉS", fg_color="#555555", command=self.torol_input_mezok, width=100,
                      height=40).pack(side="left", padx=5)

        # --- KERESÉS PANEL ---
        self.filter_card = ctk.CTkFrame(self.top_container, fg_color="transparent")
        self.filter_scroll = ctk.CTkScrollableFrame(self.filter_card, orientation="horizontal", height=90,
                                                    fg_color="transparent")
        self.filter_scroll.pack(fill="x", expand=True)
        self.r_filters = {}
        self.create_input_fields(self.filter_scroll,
                                 ["Kod", "Nem", "Megnevezes", "Szin", "Meret", "Tajegyseg", "Egyeb"],
                                 self.r_filters)
        btn_f = ctk.CTkFrame(self.filter_scroll, fg_color="transparent")
        btn_f.pack(side="left", padx=5)

        ctk.CTkButton(btn_f, text="🔍 KERESÉS", width=120, height=40, command=self.alkalmaz_szures_raktar).pack(
            side="left", padx=5)
        ctk.CTkButton(btn_f, text="✖ ÜRÍTÉS", width=100, height=40, fg_color="#555555",
                      command=self.frissit_mindent).pack(side="left", padx=5)

        # MÓDVÁLASZTÓ GOMBOK
        if self.is_admin:
            self.switch_btn = ctk.CTkSegmentedButton(self.tab1, values=["Új felvitel", "Keresés", "Szerkesztés"],
                                                     variable=self.mode_var, command=self.valt_modot_raktar,
                                                     selected_color="#1A8F63", unselected_color="#444444",
                                                     font=("Arial", 12, "bold"))
            self.switch_btn.grid(row=0, column=0, pady=(10, 5))
            self.valt_modot_raktar("Új felvitel")
        else:
            self.filter_card.pack(fill="both", expand=True)
            ctk.CTkLabel(self.tab1, text="⚠️ Csak keresési jogosultság", text_color="gray").grid(row=0, column=0,
                                                                                                 pady=5)

        self.raktar_bottom_frame = ctk.CTkFrame(self.tab1, fg_color="transparent")
        self.raktar_bottom_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.raktar_bottom_frame.grid_columnconfigure(0, weight=1)
        self.raktar_bottom_frame.grid_rowconfigure(0, weight=1)

        self.tree = self.setup_treeview(self.raktar_bottom_frame,
                                        ("id", "kod", "nem", "nev", "szin", "meret", "tajegyseg", "egyeb"))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.raktar_kivalasztas_kezelo())

        self.detail_text_r = ctk.CTkTextbox(self.tab1, height=60, corner_radius=10, border_width=1)
        self.detail_text_r.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        bottom_f = ctk.CTkFrame(self.tab1, fg_color="transparent")
        bottom_f.grid(row=4, column=0, padx=10, pady=10, sticky="ew")

        if self.is_admin:
            ctk.CTkButton(bottom_f, text="☑ MIND", command=lambda: self.mindent_kijelol(self.tree), width=80,
                          fg_color="#555555").pack(side="left", padx=5)
            ctk.CTkButton(bottom_f, text="🗑 TÖRLÉS", fg_color="#F53527", command=self.torol_db, width=120).pack(
                side="left", padx=5)
            ctk.CTkButton(bottom_f, text="📦 KIADÁS", command=self.kiad_ablak, width=120).pack(side="left", padx=5)
            ctk.CTkButton(bottom_f, text="🗺 KEZELÉS", fg_color="gray30", command=self.tajegyseg_kezeles_ablak,
                          width=120).pack(side="left", padx=5)

        self.count_label_r = ctk.CTkLabel(bottom_f, text="...", font=("Arial", 12, "bold"))
        self.count_label_r.pack(side="right", padx=10)

    def valt_modot_raktar(self, value):
        self.input_card.pack_forget()
        self.filter_card.pack_forget()

        if value == "Új felvitel":
            self.input_card.pack(fill="both", expand=True)
            self.switch_btn.configure(selected_color="#1A8F63")
            self.btn_action_raktar.configure(text="✚ RÖGZÍTÉS", command=self.hozzaad_db, fg_color="#1A8F63")
            self.torol_input_mezok()

        elif value == "Keresés":
            self.filter_card.pack(fill="both", expand=True)
            self.switch_btn.configure(selected_color="#3498db")

        elif value == "Szerkesztés":
            self.input_card.pack(fill="both", expand=True)
            self.switch_btn.configure(selected_color="#e67e22")
            self.btn_action_raktar.configure(text="💾 MENTÉS", command=self.mentes_raktar, fg_color="#e67e22")
            self.raktar_kivalasztas_kezelo()

    # ==========================
    # KIADOTT FÜL BEÁLLÍTÁSAI
    # ==========================
    def setup_kiadott_tab(self):
        self.mode_var_k = tk.StringVar(value="Keresés")

        self.kiadott_top_container = ctk.CTkFrame(self.tab2, fg_color="transparent", height=110)
        self.kiadott_top_container.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        # --- KIADOTT SZERKESZTÉS PANEL ---
        self.input_card_k = ctk.CTkFrame(self.kiadott_top_container, fg_color="transparent")
        self.input_scroll_k = ctk.CTkScrollableFrame(self.input_card_k, orientation="horizontal", height=90,
                                                     fg_color="transparent")
        self.input_scroll_k.pack(fill="x", expand=True)
        self.entries_k = {}
        self.create_input_fields(self.input_scroll_k,
                                 ["Kod", "Szemely", "Nem", "Megnevezes", "Szin", "Meret", "Tajegyseg", "Egyeb"],
                                 self.entries_k)

        btn_box_k = ctk.CTkFrame(self.input_scroll_k, fg_color="transparent")
        btn_box_k.pack(side="left", padx=10)
        ctk.CTkButton(btn_box_k, text="💾 MENTÉS", fg_color="#e67e22", command=self.mentes_kiadott, width=120,
                      height=40).pack(side="left", padx=5)

        # --- KIADOTT KERESÉS PANEL ---
        self.filter_card_k = ctk.CTkFrame(self.kiadott_top_container, fg_color="transparent")
        self.filter_scroll_k = ctk.CTkScrollableFrame(self.filter_card_k, orientation="horizontal", height=90,
                                                      fg_color="transparent")
        self.filter_scroll_k.pack(fill="x", expand=True)
        self.k_filters = {}
        self.create_input_fields(self.filter_scroll_k,
                                 ["Kod", "Szemely", "Nem", "Megnevezes", "Szin", "Meret", "Tajegyseg", "Egyeb"],
                                 self.k_filters)

        btn_f_k = ctk.CTkFrame(self.filter_scroll_k, fg_color="transparent")
        btn_f_k.pack(side="left", padx=10)
        ctk.CTkButton(btn_f_k, text="KERESÉS", command=self.alkalmaz_szures_kiadott, width=120, height=40).pack(
            side="left", padx=10)
        ctk.CTkButton(btn_f_k, text="✖ ÜRÍTÉS", command=self.frissit_mindent, width=100, height=40,
                      fg_color="#555555").pack(side="left", padx=5)

        # MÓDVÁLASZTÓ GOMBOK KIADOTTNÁL
        if self.is_admin:
            self.switch_btn_k = ctk.CTkSegmentedButton(self.tab2, values=["Keresés", "Szerkesztés"],
                                                       variable=self.mode_var_k, command=self.valt_modot_kiadott,
                                                       selected_color="#3498db", unselected_color="#444444",
                                                       font=("Arial", 12, "bold"))
            self.switch_btn_k.grid(row=0, column=0, pady=(10, 5))
            self.valt_modot_kiadott("Keresés")
        else:
            self.filter_card_k.pack(fill="both", expand=True)

        self.kiadott_bottom_frame = ctk.CTkFrame(self.tab2, fg_color="transparent")
        self.kiadott_bottom_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.kiadott_bottom_frame.grid_columnconfigure(0, weight=1)
        self.kiadott_bottom_frame.grid_rowconfigure(0, weight=1)

        self.tree_kiadott = self.setup_treeview(self.kiadott_bottom_frame,
                                                ("id", "kod", "szemely", "nem", "nev", "szin", "meret", "tajegyseg",
                                                 "egyeb"),
                                                is_kiadott=True)
        self.tree_kiadott.bind("<<TreeviewSelect>>", lambda e: self.kiadott_kivalasztas_kezelo())

        self.detail_text_k = ctk.CTkTextbox(self.tab2, height=60, corner_radius=10)
        self.detail_text_k.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        bottom_f = ctk.CTkFrame(self.tab2, fg_color="transparent")
        bottom_f.grid(row=4, column=0, padx=10, pady=10, sticky="ew")

        if self.is_admin:
            ctk.CTkButton(bottom_f, text="☑ MIND", command=lambda: self.mindent_kijelol(self.tree_kiadott), width=80,
                          fg_color="#555555").pack(side="left", padx=5)
            ctk.CTkButton(bottom_f, text="🔄 VISSZAVÉTEL", command=self.visszavesz_db, width=150).pack(side="left",
                                                                                                      padx=5)

        self.count_label_k = ctk.CTkLabel(bottom_f, text="...", font=("Arial", 12, "bold"))
        self.count_label_k.pack(side="right", padx=10)

    def valt_modot_kiadott(self, value):
        self.input_card_k.pack_forget()
        self.filter_card_k.pack_forget()

        if value == "Keresés":
            self.filter_card_k.pack(fill="both", expand=True)
            self.switch_btn_k.configure(selected_color="#3498db")
        elif value == "Szerkesztés":
            self.input_card_k.pack(fill="both", expand=True)
            self.switch_btn_k.configure(selected_color="#e67e22")
            self.kiadott_kivalasztas_kezelo()

    def setup_treeview(self, parent, columns, is_kiadott=False):
        tree_container = ctk.CTkFrame(parent, fg_color="#1d1d1d", corner_radius=10)
        tree_container.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        tree = ttk.Treeview(tree_container, columns=columns, show='headings', height=18)
        vsb = ctk.CTkScrollbar(tree_container, orientation="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        hsb = ctk.CTkScrollbar(tree_container, orientation="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky='nsew', padx=2, pady=2)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        for col in columns:
            if col == "id": continue

            header_text = col.capitalize()
            col_width = 100

            for k, c in self.COL_CONFIG.items():
                if c["db_key"] == col:
                    header_text = c["label"]
                    col_width = c["width"]
                    break

            tree.heading(col, text=header_text, command=lambda _c=col: self.tree_sort(tree, _c, False))
            tree.column(col, width=col_width, anchor="center")

        tree["displaycolumns"] = [c for c in columns if c != "id"]
        return tree

    # --- INPUT MEZŐK ÜRÍTÉSE ---
    def torol_input_mezok(self):
        for key, widget in self.entries.items():
            if isinstance(widget, ctk.CTkOptionMenu):
                widget.set("Válassz...")
            else:
                widget.delete(0, tk.END)

    # --- ÚJ FUNKCIÓ: MINDEN KIJELÖLÉSE ---
    def mindent_kijelol(self, tree):
        children = tree.get_children()
        tree.selection_set(children)

    # --- KIVÁLASZTÁS ÉS MEZŐKITÖLTÉS LOGIKA ---
    def betolt_adatok_mezokbe(self, tree, input_dict):
        sel = tree.selection()
        if not sel: return

        values = tree.item(sel[0])['values']
        columns = tree["columns"]

        for key, widget in input_dict.items():
            if isinstance(widget, ctk.CTkOptionMenu):
                widget.set("Válassz...")
            else:
                widget.delete(0, tk.END)

            col_id = ""
            if key == "Kod":
                col_id = "kod"
            elif key == "Szemely":
                col_id = "szemely"
            elif key == "Nem":
                col_id = "nem"
            elif key == "Megnevezes":
                col_id = "nev"
            elif key == "Szin":
                col_id = "szin"
            elif key == "Meret":
                col_id = "meret"
            elif key == "Tajegyseg":
                col_id = "tajegyseg"
            elif key == "Egyeb":
                col_id = "egyeb"

            if col_id in columns:
                idx = columns.index(col_id)
                val = str(values[idx]) if idx < len(values) else ""

                if key == "Nem":
                    if val == "F":
                        widget.set("Férfi")
                    elif val == "N":
                        widget.set("Nő")
                    else:
                        widget.set("Válassz...")
                elif key == "Tajegyseg":
                    if val in self.tajegysegek:
                        widget.set(val)
                    else:
                        widget.set("Válassz...")
                else:
                    if isinstance(widget, ctk.CTkEntry):
                        widget.insert(0, val)

    def raktar_kivalasztas_kezelo(self):
        self.mutat_reszletek(self.tree, self.detail_text_r)
        if self.mode_var.get() == "Szerkesztés":
            self.betolt_adatok_mezokbe(self.tree, self.entries)

    def kiadott_kivalasztas_kezelo(self):
        self.mutat_reszletek(self.tree_kiadott, self.detail_text_k)
        if self.mode_var_k.get() == "Szerkesztés":
            self.betolt_adatok_mezokbe(self.tree_kiadott, self.entries_k)

    # --- ADATBÁZIS MŰVELETEK ---
    def hozzaad_db(self):
        if not self.is_admin: return
        adat = {}
        for key, conf in self.COL_CONFIG.items():
            if key in self.entries:
                val = self.entries[key].get().strip()
                if val == "Válassz...": val = ""
                if key == "Nem":
                    if val == "Férfi":
                        val = "F"
                    elif val == "Nő":
                        val = "N"
                adat[conf["db_key"]] = val

        if not adat.get("nev"): return messagebox.showwarning("Hiba", "Név megadása kötelező!")

        try:
            raktar_col.insert_one(adat)
            self.frissit_mindent()
            self.torol_input_mezok()
            messagebox.showinfo("Siker", "Ruha rögzítve!")
        except Exception as e:
            messagebox.showerror("Hiba", f"Adatbázis hiba: {e}")

    def mentes_modositas(self, tree, input_dict, collection):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Figyelem", "Nincs kijelölve elem a módosításhoz!")
            return

        _id_str = tree.item(sel[0])['values'][0]

        adat = {}
        for key, widget in input_dict.items():
            val = widget.get().strip()
            if val == "Válassz...": val = ""

            db_key = ""
            if key == "Kod":
                db_key = "kod"
            elif key == "Szemely":
                db_key = "szemely"
            elif key == "Nem":
                db_key = "nem"
                if val == "Férfi":
                    val = "F"
                elif val == "Nő":
                    val = "N"
            elif key == "Megnevezes":
                db_key = "nev"
            elif key == "Szin":
                db_key = "szin"
            elif key == "Meret":
                db_key = "meret"
            elif key == "Tajegyseg":
                db_key = "tajegyseg"
            elif key == "Egyeb":
                db_key = "egyeb"

            if db_key:
                adat[db_key] = val

        if not adat.get("nev"):
            messagebox.showwarning("Hiba", "A név nem lehet üres!")
            return

        try:
            collection.update_one({"_id": ObjectId(_id_str)}, {"$set": adat})
            self.frissit_mindent()
            messagebox.showinfo("Siker", "Módosítások mentve!")
        except Exception as e:
            messagebox.showerror("Hiba", f"Mentési hiba: {e}")

    def mentes_raktar(self):
        self.mentes_modositas(self.tree, self.entries, raktar_col)
        self.raktar_kivalasztas_kezelo()

    def mentes_kiadott(self):
        self.mentes_modositas(self.tree_kiadott, self.entries_k, kiadott_col)
        self.kiadott_kivalasztas_kezelo()

    # --- KERESÉS ÉS LISTÁZÁS ---
    def get_query_from_widgets(self, widget_dict):
        q = {}
        for k, w in widget_dict.items():
            raw_val = w.get().strip()
            if not raw_val or raw_val == "Válassz...":
                continue

            db_key = self.COL_CONFIG[k]["db_key"]

            if k == "Nem":
                if raw_val == "Férfi":
                    search_val = "F"
                elif raw_val == "Nő":
                    search_val = "N"
                else:
                    search_val = raw_val
                q[db_key] = search_val
            else:
                q[db_key] = {"$regex": raw_val, "$options": "i"}
        return q

    def alkalmaz_szures_raktar(self):
        try:
            q = self.get_query_from_widgets(self.r_filters)
            self.listaz_adatokat(self.tree, raktar_col, self.count_label_r, q)
        except Exception as e:
            print(f"Szűrési hiba: {e}")

    def alkalmaz_szures_kiadott(self):
        try:
            q = self.get_query_from_widgets(self.k_filters)
            self.listaz_adatokat(self.tree_kiadott, kiadott_col, self.count_label_k, q, True)
        except Exception as e:
            print(f"Szűrési hiba: {e}")

    def listaz_adatokat(self, tree, col_db, lbl, query={}, is_kiadott=False):
        selected_id = None
        sel = tree.selection()
        if sel:
            selected_id = tree.item(sel[0])['values'][0]

        for i in tree.get_children(): tree.delete(i)
        try:
            docs = list(col_db.find(query))
            for doc in docs:
                vals = [str(doc['_id'])]
                current_cols = self.tree_kiadott["columns"] if is_kiadott else self.tree["columns"]
                for cid in current_cols:
                    if cid != "id": vals.append(doc.get(cid, ""))

                item_id = tree.insert('', 'end', values=vals)

                if str(doc['_id']) == selected_id:
                    tree.selection_set(item_id)
                    tree.focus(item_id)

            lbl.configure(text=f"📊 Találat: {len(docs)} | Összes: {col_db.count_documents({})}")
        except Exception as e:
            lbl.configure(text="Adatbázis hiba")
            print(e)

    def frissit_mindent(self):
        for d in [self.r_filters, self.k_filters]:
            for w in d.values():
                if isinstance(w, ctk.CTkOptionMenu):
                    w.set("Válassz...")
                else:
                    w.delete(0, tk.END)
        self.listaz_adatokat(self.tree, raktar_col, self.count_label_r)
        self.listaz_adatokat(self.tree_kiadott, kiadott_col, self.count_label_k, is_kiadott=True)

    def mutat_reszletek(self, tree, txt):
        sel = tree.selection()
        txt.delete("1.0", tk.END)
        if sel: txt.insert("1.0", str(tree.item(sel[0])['values'][-1]))

    def tree_sort(self, tree, col, reverse):
        l = [(tree.set(k, col), k) for k in tree.get_children('')]
        l.sort(reverse=reverse)
        for index, (val, k) in enumerate(l): tree.move(k, '', index)
        tree.heading(col, command=lambda: self.tree_sort(tree, col, not reverse))

    def torol_db(self):
        if not self.is_admin: return
        sel = self.tree.selection()
        if sel and messagebox.askyesno("Törlés", f"Törölsz {len(sel)} elemet?"):
            for i in sel: raktar_col.delete_one({"_id": ObjectId(self.tree.item(i)['values'][0])})
            self.frissit_mindent()

    def kiad_ablak(self):
        if not self.is_admin: return
        sel = self.tree.selection()
        if not sel: return
        top = ctk.CTkToplevel(self.root);
        top.geometry("300x200");
        top.transient(self.root);
        top.grab_set()
        ctk.CTkLabel(top, text="Ki kapja meg?").pack(pady=10)
        e = ctk.CTkEntry(top);
        e.pack(pady=5, padx=20, fill="x")

        def ok():
            if not e.get().strip(): return
            for i in sel:
                doc = raktar_col.find_one_and_delete({"_id": ObjectId(self.tree.item(i)['values'][0])})
                if doc: doc["szemely"] = e.get().strip(); del doc["_id"]; kiadott_col.insert_one(doc)
            self.frissit_mindent();
            top.destroy()

        ctk.CTkButton(top, text="KIADÁS", command=ok, fg_color="#1A8F63").pack(pady=20)

    def visszavesz_db(self):
        if not self.is_admin: return
        sel = self.tree_kiadott.selection()
        if sel:
            for i in sel:
                doc = kiadott_col.find_one_and_delete({"_id": ObjectId(self.tree_kiadott.item(i)['values'][0])})
                if doc: del doc["_id"], doc["szemely"]; raktar_col.insert_one(doc)
            self.frissit_mindent()

    # --- TÁJEGYSÉG KEZELÉS ---
    def tajegyseg_kezeles_ablak(self):
        if not self.is_admin: return

        top = ctk.CTkToplevel(self.root)
        top.geometry("350x600")
        top.title("Tájegységek kezelése")
        top.transient(self.root)
        top.grab_set()

        ctk.CTkLabel(top, text="Új tájegység:", font=("Arial", 12, "bold")).pack(pady=5)
        ent = ctk.CTkEntry(top)
        ent.pack(pady=5, padx=10, fill="x")

        search_ent = ctk.CTkEntry(top, placeholder_text="Keresés...")
        search_ent.pack(pady=5, padx=10, fill="x")

        fr = ctk.CTkFrame(top)
        fr.pack(fill="both", expand=True, padx=10, pady=10)

        lb = tk.Listbox(fr, bg="#2b2b2b", fg="white", borderwidth=0, highlightthickness=0)
        lb.pack(side="left", fill="both", expand=True)

        sb = ctk.CTkScrollbar(fr, command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)

        def update_listbox(e=None):
            lb.delete(0, tk.END)
            filter_txt = search_ent.get().lower()
            for t in self.tajegysegek[1:]:
                if filter_txt in t.lower():
                    lb.insert(tk.END, t)

        def add():
            txt = ent.get().strip()
            if txt and txt not in self.tajegysegek:
                try:
                    tajegysegek_col.insert_one({"nev": txt})
                    self.frissit_tajegyseg_listat()
                    self.frissit_mindent()
                    self.frissit_comboboxokat()
                    ent.delete(0, tk.END)
                    update_listbox()
                except Exception as ex:
                    messagebox.showerror("Hiba", str(ex))

        def dele():
            sel = lb.curselection()
            if not sel: return
            val = lb.get(sel[0])
            if messagebox.askyesno("Törlés", f"Biztosan törlöd: {val}?"):
                try:
                    tajegysegek_col.delete_one({"nev": val})
                    self.frissit_tajegyseg_listat()
                    self.frissit_mindent()
                    self.frissit_comboboxokat()
                    update_listbox()
                except Exception as ex:
                    messagebox.showerror("Hiba", str(ex))

        ctk.CTkButton(top, text="Hozzáad", command=add, fg_color="#1A8F63").pack(pady=5, after=ent)
        ctk.CTkButton(top, text="Törlés", fg_color="red", command=dele).pack(pady=10)

        search_ent.bind("<KeyRelease>", update_listbox)
        update_listbox()

    def frissit_comboboxokat(self):
        targets = [self.entries["Tajegyseg"], self.r_filters["Tajegyseg"], self.k_filters["Tajegyseg"],
                   self.entries_k.get("Tajegyseg")]
        for c in targets:
            if c:
                c.configure(values=self.tajegysegek)
                c.set("Válassz...")


if __name__ == "__main__":
    LoginApp()