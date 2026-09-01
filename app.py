import os
import sys
import sqlite3
import json
import shutil
from datetime import datetime, timedelta
import difflib
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageOps

# Configuración de apariencia
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# --- SOLUCIÓN DE GUARDADO PERMANENTE ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATOS_DIR = os.path.join(BASE_DIR, "datos")
PRODUCTOS_IMG_DIR = os.path.join(DATOS_DIR, "productos")
DINERO_IMG_DIR = os.path.join(DATOS_DIR, "dinero")
DB_PATH = os.path.join(DATOS_DIR, "ventas.db")
CONFIG_PATH = os.path.join(DATOS_DIR, "configuracion.json")

# Asegurar directorios
for d in [DATOS_DIR, PRODUCTOS_IMG_DIR, DINERO_IMG_DIR]:
    os.makedirs(d, exist_ok=True)

def procesar_imagen_fondo_negro(ruta, max_size):
    try:
        img = Image.open(ruta).convert("RGBA")
        fondo = Image.new("RGBA", img.size, (0, 0, 0, 255))
        fondo.paste(img, (0, 0), img)
        fondo = fondo.convert("RGB")
        return ImageOps.contain(fondo, max_size)
    except Exception:
        return None

class RegistroVentasApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Registro de Ventas")
        self.geometry("1100x720")
        self.minsize(1000, 600)
        
        self.init_db()
        self.load_config()
        
        self.venta_actual = [] 
        self.crear_interfaz()
        self.cargar_productos_ui()
        
    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nombre TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY, nombre TEXT, precio REAL, categoria TEXT, imagen TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, fecha TEXT, total REAL, recibido REAL, cambio REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS detalle_ventas (id INTEGER PRIMARY KEY, venta_id INTEGER, producto TEXT, cantidad INTEGER, precio REAL)''')
        conn.commit()
        conn.close()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {"negocio": "MI NEGOCIO", "billetes": {}}
            self.save_config()

    def save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def crear_interfaz(self):
        self.top_bar = ctk.CTkFrame(self, fg_color="#1a1a1a", height=50, corner_radius=0)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)
        
        self.btn_menu = ctk.CTkButton(self.top_bar, text="☰", width=40, font=("Arial", 24), fg_color="transparent", command=self.toggle_menu)
        self.btn_menu.pack(side="left", padx=10)
        
        self.lbl_negocio = ctk.CTkLabel(self.top_bar, text=self.config["negocio"], font=("Arial", 20, "bold"), text_color="white")
        self.lbl_negocio.pack(side="left", padx=10)

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        self.panel_central = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.panel_central.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.header_central = ctk.CTkFrame(self.panel_central, fg_color="transparent")
        self.header_central.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(self.header_central, text="NUEVA VENTA", font=("Arial", 24, "bold")).pack(side="left")
        
        self.var_busqueda = tk.StringVar()
        self.var_busqueda.trace_add("write", lambda *args: self.filtrar_productos())
        self.entry_busqueda = ctk.CTkEntry(self.header_central, textvariable=self.var_busqueda, placeholder_text="Buscar producto...", width=300, height=40, font=("Arial", 16))
        self.entry_busqueda.pack(side="right")

        self.scroll_productos = ctk.CTkScrollableFrame(self.panel_central)
        self.scroll_productos.pack(fill="both", expand=True)
        
        self.frame_billetes = ctk.CTkFrame(self.panel_central, height=180)
        self.frame_billetes.pack(fill="x", pady=(10, 0))
        self.cargar_billetes_ui()

        self.panel_derecho = ctk.CTkFrame(self.main_container, width=320)
        self.panel_derecho.pack(side="right", fill="y", padx=10, pady=10)
        self.panel_derecho.pack_propagate(False)

        ctk.CTkLabel(self.panel_derecho, text="Venta Actual", font=("Arial", 18, "bold")).pack(pady=10)
        
        self.lista_venta = tk.Listbox(self.panel_derecho, font=("Arial", 14))
        self.lista_venta.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkButton(self.panel_derecho, text="Eliminar seleccionado", fg_color="#d9534f", hover_color="#c9302c", font=("Arial", 14, "bold"), command=self.eliminar_item_venta).pack(pady=5, padx=10, fill="x")

        self.lbl_total = ctk.CTkLabel(self.panel_derecho, text="TOTAL: $0", font=("Arial", 22, "bold"))
        self.lbl_total.pack(pady=(15,5))

        frame_recibido = ctk.CTkFrame(self.panel_derecho, fg_color="transparent")
        frame_recibido.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(frame_recibido, text="Recibido:", font=("Arial", 14, "bold")).pack(side="left")
        
        self.var_recibido = tk.StringVar(value="")
        self.var_recibido.trace_add("write", self.formatear_entrada_dinero)
        self.entry_recibido = ctk.CTkEntry(frame_recibido, textvariable=self.var_recibido, width=150, font=("Arial", 18, "bold"), justify="right")
        self.entry_recibido.pack(side="right")

        self.lbl_cambio = ctk.CTkLabel(self.panel_derecho, text="CAMBIO: $0", font=("Arial", 22, "bold"), text_color="#28a745")
        self.lbl_cambio.pack(pady=15)

        ctk.CTkButton(self.panel_derecho, text="REGISTRAR VENTA", height=60, font=("Arial", 18, "bold"), fg_color="#28a745", hover_color="#218838", command=self.registrar_venta).pack(side="bottom", fill="x", padx=10, pady=10)

        self.menu_lateral = ctk.CTkFrame(self, width=220, fg_color="#2b2b2b", corner_radius=0)
        self.menu_visible = False
        
        opciones_menu = [
            ("Nueva venta", self.toggle_menu),
            ("Ventas de hoy", lambda: self.ver_ventas("hoy")),
            ("Ventas semana", lambda: self.ver_ventas("semana")),
            ("Ventas mes", lambda: self.ver_ventas("mes")),
            ("Gestión de Productos", self.abrir_gestion_productos),
            ("Gestión de Categorías", self.abrir_gestion_categorias),
            ("Configuración", self.abrir_configuracion)
        ]
        
        for texto, comando in opciones_menu:
            btn = ctk.CTkButton(self.menu_lateral, text=texto, font=("Arial", 14), fg_color="transparent", text_color="white", anchor="w", command=comando)
            btn.pack(fill="x", padx=15, pady=10)

    def toggle_menu(self):
        if self.menu_visible:
            self.menu_lateral.place_forget()
            self.menu_visible = False
        else:
            self.menu_lateral.place(x=0, y=50, relheight=1.0)
            self.menu_lateral.tkraise()
            self.menu_visible = True
    
    def formatear_numero(self, num):
        return f"{int(num):,}".replace(",", ".")

    def formatear_entrada_dinero(self, *args):
        texto = self.var_recibido.get().replace(".", "")
        if not texto.isdigit() and texto != "":
            texto = ''.join(filter(str.isdigit, texto))
            
        if texto == "":
            if self.var_recibido.get() != "":
                self.var_recibido.set("")
            self.calcular_cambio()
            return
            
        formateado = f"{int(texto):,}".replace(",", ".")
        if self.var_recibido.get() != formateado:
            self.var_recibido.set(formateado)
            self.entry_recibido.icursor(tk.END)
            
        self.calcular_cambio()

    def agregar_a_venta(self, producto):
        for p in self.venta_actual:
            if p['id'] == producto['id']:
                p['cantidad'] += 1
                self.actualizar_lista_venta()
                return
        self.venta_actual.append({'id': producto['id'], 'nombre': producto['nombre'], 'precio': producto['precio'], 'cantidad': 1})
        self.actualizar_lista_venta()

    def eliminar_item_venta(self):
        seleccion = self.lista_venta.curselection()
        if seleccion:
            idx = seleccion[0]
            del self.venta_actual[idx]
            self.actualizar_lista_venta()
        else:
            messagebox.showwarning("Selección", "Primero selecciona un producto de la venta actual para eliminarlo.")

    def actualizar_lista_venta(self):
        self.lista_venta.delete(0, tk.END)
        total = 0
        for p in self.venta_actual:
            sub = p['precio'] * p['cantidad']
            total += sub
            self.lista_venta.insert(tk.END, f"{p['cantidad']}x {p['nombre']} - ${self.formatear_numero(sub)}")
        self.lbl_total.configure(text=f"TOTAL: ${self.formatear_numero(total)}")
        self.calcular_cambio()

    def sumar_dinero(self, valor):
        actual_str = self.var_recibido.get().replace(".", "")
        actual = int(actual_str) if actual_str.isdigit() else 0
        nuevo_valor = actual + valor
        self.var_recibido.set(self.formatear_numero(nuevo_valor))
        self.entry_recibido.icursor(tk.END)

    def calcular_cambio(self):
        total = sum(p['precio'] * p['cantidad'] for p in self.venta_actual)
        recibido_str = self.var_recibido.get().replace(".", "")
        recibido = int(recibido_str) if recibido_str.isdigit() else 0
        
        cambio = recibido - total
        if cambio < 0 or total == 0:
            self.lbl_cambio.configure(text="CAMBIO: $0", text_color="gray")
        else:
            self.lbl_cambio.configure(text=f"CAMBIO: ${self.formatear_numero(cambio)}", text_color="#28a745")

    def registrar_venta(self):
        if not self.venta_actual:
            return
            
        total = sum(p['precio'] * p['cantidad'] for p in self.venta_actual)
        recibido_str = self.var_recibido.get().replace(".", "")
        recibido = int(recibido_str) if recibido_str.isdigit() else 0
        
        if recibido > 0 and recibido < total:
            messagebox.showwarning("Dinero insuficiente", "El dinero recibido es menor al total.")
            return

        cambio = recibido - total if recibido >= total else 0
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO ventas (fecha, total, recibido, cambio) VALUES (?, ?, ?, ?)", (fecha, total, recibido, cambio))
        venta_id = c.lastrowid
        
        for p in self.venta_actual:
            c.execute("INSERT INTO detalle_ventas (venta_id, producto, cantidad, precio) VALUES (?, ?, ?, ?)", 
                      (venta_id, p['nombre'], p['cantidad'], p['precio']))
        
        conn.commit()
        conn.close()

        # Limpia silenciosamente la venta sin mostrar ventanas emergentes
        self.venta_actual = []
        self.var_recibido.set("")
        self.actualizar_lista_venta()
    
    def cargar_productos_ui(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre, precio, imagen FROM productos")
        self.productos_db = c.fetchall()
        conn.close()
        self.filtrar_productos()

    def filtrar_productos(self):
        busqueda = self.var_busqueda.get().strip().lower()
        for widget in self.scroll_productos.winfo_children():
            widget.destroy()

        resultados = []
        mensaje_sugerencia = ""

        if not busqueda:
            resultados = self.productos_db
        else:
            nombres = [p[1] for p in self.productos_db]
            coincidencias_exactas = [p for p in self.productos_db if busqueda in p[1].lower()]
            
            if coincidencias_exactas:
                resultados = coincidencias_exactas
            else:
                sugerencias = difflib.get_close_matches(busqueda, nombres, n=1, cutoff=0.4)
                if sugerencias:
                    mejor_opcion = sugerencias[0]
                    mensaje_sugerencia = f"¿Intentaste buscar '{busqueda}'? Quizás quisiste decir '{mejor_opcion}'."
                    resultados = [p for p in self.productos_db if p[1] == mejor_opcion]
                else:
                    ctk.CTkLabel(self.scroll_productos, text=f"No encontramos ningún producto parecido a '{busqueda}'", font=("Arial", 16)).pack(pady=20)
                    return

        if mensaje_sugerencia:
            ctk.CTkLabel(self.scroll_productos, text=mensaje_sugerencia, font=("Arial", 16, "italic"), text_color="#d9534f").pack(pady=10)

        row, col = 0, 0
        frame_grid = ctk.CTkFrame(self.scroll_productos, fg_color="transparent")
        frame_grid.pack(fill="both", expand=True)

        for p in resultados:
            prod_id, nombre, precio, img_path = p
            tarjeta = ctk.CTkFrame(frame_grid, width=160, height=210, fg_color="white", corner_radius=10)
            tarjeta.grid(row=row, column=col, padx=10, pady=10)
            tarjeta.pack_propagate(False)

            if img_path and os.path.exists(img_path):
                img_pil = procesar_imagen_fondo_negro(img_path, (120, 120))
                if img_pil:
                    ctk_img = ctk.CTkImage(light_image=img_pil, size=(120, 120))
                    lbl_img = ctk.CTkLabel(tarjeta, image=ctk_img, text="")
                else:
                    lbl_img = ctk.CTkLabel(tarjeta, text="Error Imagen", width=120, height=120, fg_color="black", text_color="white")
            else:
                lbl_img = ctk.CTkLabel(tarjeta, text="Sin imagen", width=120, height=120, fg_color="black", text_color="white")
            
            lbl_img.pack(pady=5)
            ctk.CTkLabel(tarjeta, text=nombre, font=("Arial", 14, "bold")).pack()
            ctk.CTkLabel(tarjeta, text=f"${self.formatear_numero(precio)}", font=("Arial", 18, "bold"), text_color="#1e7e34").pack()
            
            producto_dict = {'id': prod_id, 'nombre': nombre, 'precio': precio}
            for w in [tarjeta, lbl_img]:
                w.bind("<Button-1>", lambda e, pd=producto_dict: self.agregar_a_venta(pd))
            
            col += 1
            if col > 4: 
                col = 0
                row += 1
    
    def cargar_billetes_ui(self):
        for w in self.frame_billetes.winfo_children():
            w.destroy()
            
        ctk.CTkLabel(self.frame_billetes, text="DINERO RÁPIDO:", font=("Arial", 14, "bold")).pack(side="top", pady=5)
        
        frame_btns = ctk.CTkFrame(self.frame_billetes, fg_color="transparent")
        frame_btns.pack(expand=True)

        denominaciones = [1000, 2000, 5000, 10000, 20000, 50000, 100000]
        for val in denominaciones:
            img_path = self.config["billetes"].get(str(val))
            if img_path and os.path.exists(img_path):
                img_pil = procesar_imagen_fondo_negro(img_path, (80, 50))
                ctk_img = ctk.CTkImage(light_image=img_pil, size=(80, 50))
                btn = ctk.CTkButton(frame_btns, image=ctk_img, text="", width=90, height=60, command=lambda v=val: self.sumar_dinero(v))
            else:
                btn = ctk.CTkButton(frame_btns, text=f"${self.formatear_numero(val)}", font=("Arial", 14, "bold"), width=90, height=60, command=lambda v=val: self.sumar_dinero(v))
            btn.pack(side="left", padx=5, pady=5)

    def abrir_configuracion(self):
        self.toggle_menu()
        win = ctk.CTkToplevel(self)
        win.title("Configuración")
        win.geometry("500x500")
        win.grab_set()
        
        ctk.CTkLabel(win, text="Nombre del Negocio:", font=("Arial", 14, "bold")).pack(pady=10)
        var_neg = tk.StringVar(value=self.config["negocio"])
        ctk.CTkEntry(win, textvariable=var_neg, width=250, font=("Arial", 14)).pack()
        
        ctk.CTkLabel(win, text="Imágenes de Billetes (Se guardan automáticamente):", font=("Arial", 14, "bold")).pack(pady=20)
        
        frame_billetes_conf = ctk.CTkScrollableFrame(win, width=400, height=200)
        frame_billetes_conf.pack(fill="both", expand=True, padx=20)

        def cambiar_img_billete(val, lbl_preview):
            ruta = filedialog.askopenfilename(filetypes=[("Imágenes", "*.png *.jpg *.jpeg")])
            if ruta:
                ext = os.path.splitext(ruta)[1]
                img_dest = os.path.join(DINERO_IMG_DIR, f"billete_{val}_{datetime.now().strftime('%S%f')}{ext}")
                shutil.copy(ruta, img_dest)
                self.config["billetes"][str(val)] = img_dest
                self.save_config()
                
                img_pil = procesar_imagen_fondo_negro(img_dest, (80, 50))
                ctk_img = ctk.CTkImage(light_image=img_pil, size=(80, 50))
                lbl_preview.configure(image=ctk_img, text="")
                self.cargar_billetes_ui()

        for val in [1000, 2000, 5000, 10000, 20000, 50000, 100000]:
            f_row = ctk.CTkFrame(frame_billetes_conf, fg_color="transparent")
            f_row.pack(fill="x", pady=5)
            ctk.CTkLabel(f_row, text=f"${self.formatear_numero(val)}:", width=80).pack(side="left")
            
            lbl_prev = ctk.CTkLabel(f_row, text="Sin img", width=80, height=50, fg_color="black", text_color="white")
            lbl_prev.pack(side="left", padx=10)
            
            img_path = self.config["billetes"].get(str(val))
            if img_path and os.path.exists(img_path):
                img_pil = procesar_imagen_fondo_negro(img_path, (80, 50))
                ctk_img = ctk.CTkImage(light_image=img_pil, size=(80, 50))
                lbl_prev.configure(image=ctk_img, text="")
                
            ctk.CTkButton(f_row, text="Elegir Imagen", command=lambda v=val, l=lbl_prev: cambiar_img_billete(v, l)).pack(side="right")
        
        def guardar_general():
            self.config["negocio"] = var_neg.get()
            self.save_config()
            self.lbl_negocio.configure(text=self.config["negocio"])
            win.destroy()
            
        ctk.CTkButton(win, text="Guardar Nombre del Negocio", command=guardar_general, fg_color="#28a745", hover_color="#218838").pack(pady=20)

    def abrir_gestion_categorias(self):
        self.toggle_menu()
        win = ctk.CTkToplevel(self)
        win.title("Categorías")
        win.geometry("400x400")
        win.grab_set()

        ctk.CTkLabel(win, text="Nueva Categoría:").pack(pady=10)
        entry_cat = ctk.CTkEntry(win, width=200)
        entry_cat.pack()

        lista_cat = tk.Listbox(win, font=("Arial", 12))
        
        def cargar_cats():
            lista_cat.delete(0, tk.END)
            conn = sqlite3.connect(DB_PATH)
            for row in conn.execute("SELECT id, nombre FROM categorias"):
                lista_cat.insert(tk.END, f"{row[0]} - {row[1]}")
            conn.close()

        def guardar_cat():
            nom = entry_cat.get().strip()
            if nom:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO categorias (nombre) VALUES (?)", (nom,))
                conn.commit()
                conn.close()
                entry_cat.delete(0, tk.END)
                cargar_cats()

        def eliminar_cat():
            seleccion = lista_cat.curselection()
            if seleccion:
                item = lista_cat.get(seleccion[0])
                cat_id = item.split(" - ")[0]
                if messagebox.askyesno("Confirmar", "¿Eliminar esta categoría?"):
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("DELETE FROM categorias WHERE id=?", (cat_id,))
                    conn.commit()
                    conn.close()
                    cargar_cats()

        ctk.CTkButton(win, text="Agregar Categoría", command=guardar_cat).pack(pady=10)
        lista_cat.pack(fill="both", expand=True, padx=20, pady=10)
        ctk.CTkButton(win, text="Eliminar Seleccionada", fg_color="#d9534f", command=eliminar_cat).pack(pady=10)
        cargar_cats()

    def abrir_gestion_productos(self):
        self.toggle_menu()
        win = ctk.CTkToplevel(self)
        win.title("Productos")
        win.geometry("800x600")
        win.grab_set()

        frame_izq = ctk.CTkFrame(win, width=300)
        frame_izq.pack(side="left", fill="y", padx=10, pady=10)
        frame_der = ctk.CTkFrame(win)
        frame_der.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.img_temporal_path = None
        lbl_preview = ctk.CTkLabel(frame_izq, text="Vista Previa", width=150, height=150, fg_color="black", text_color="white")
        lbl_preview.pack(pady=10)

        def seleccionar_img():
            ruta = filedialog.askopenfilename(filetypes=[("Imágenes", "*.png *.jpg *.jpeg")])
            if ruta:
                self.img_temporal_path = ruta
                img_pil = procesar_imagen_fondo_negro(ruta, (150, 150))
                ctk_img = ctk.CTkImage(light_image=img_pil, size=(img_pil.width, img_pil.height))
                lbl_preview.configure(image=ctk_img, text="")

        ctk.CTkButton(frame_izq, text="Seleccionar Imagen", command=seleccionar_img).pack(pady=5)

        ctk.CTkLabel(frame_izq, text="Nombre:").pack(pady=(10,0))
        entry_nom = ctk.CTkEntry(frame_izq)
        entry_nom.pack()

        ctk.CTkLabel(frame_izq, text="Precio (ej. 15000):").pack(pady=(10,0))
        entry_pre = ctk.CTkEntry(frame_izq)
        entry_pre.pack()

        conn = sqlite3.connect(DB_PATH)
        categorias = [row[0] for row in conn.execute("SELECT nombre FROM categorias")]
        conn.close()
        
        ctk.CTkLabel(frame_izq, text="Categoría:").pack(pady=(10,0))
        combo_cat = ctk.CTkComboBox(frame_izq, values=categorias if categorias else ["General"])
        combo_cat.pack()

        lista_prod = tk.Listbox(frame_der, font=("Arial", 12))
        
        def cargar_lista_prod():
            lista_prod.delete(0, tk.END)
            conn = sqlite3.connect(DB_PATH)
            for row in conn.execute("SELECT id, nombre, precio FROM productos"):
                lista_prod.insert(tk.END, f"{row[0]} | {row[1]} | ${self.formatear_numero(row[2])}")
            conn.close()

        def guardar_prod():
            nom = entry_nom.get()
            pre = entry_pre.get().replace(".", "")
            cat = combo_cat.get()
            if not nom or not pre.isdigit():
                messagebox.showerror("Error", "Revisa el nombre y el precio (solo números).")
                return
            
            img_dest = ""
            if self.img_temporal_path:
                ext = os.path.splitext(self.img_temporal_path)[1]
                img_dest = os.path.join(PRODUCTOS_IMG_DIR, f"prod_{datetime.now().strftime('%S%f')}{ext}")
                shutil.copy(self.img_temporal_path, img_dest)

            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO productos (nombre, precio, categoria, imagen) VALUES (?, ?, ?, ?)", (nom, float(pre), cat, img_dest))
            conn.commit()
            conn.close()
            
            entry_nom.delete(0, tk.END)
            entry_pre.delete(0, tk.END)
            lbl_preview.configure(image="", text="Vista Previa")
            self.img_temporal_path = None
            cargar_lista_prod()
            self.cargar_productos_ui()

        def eliminar_prod():
            seleccion = lista_prod.curselection()
            if seleccion:
                item = lista_prod.get(seleccion[0])
                prod_id = item.split(" | ")[0]
                if messagebox.askyesno("Confirmar", "¿Eliminar este producto?"):
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("DELETE FROM productos WHERE id=?", (prod_id,))
                    conn.commit()
                    conn.close()
                    cargar_lista_prod()
                    self.cargar_productos_ui()

        ctk.CTkButton(frame_izq, text="Guardar Producto", command=guardar_prod, fg_color="#28a745").pack(pady=20)
        
        ctk.CTkLabel(frame_der, text="Lista de Productos Registrados", font=("Arial", 14, "bold")).pack()
        lista_prod.pack(fill="both", expand=True, pady=10)
        ctk.CTkButton(frame_der, text="Eliminar Seleccionado", fg_color="#d9534f", command=eliminar_prod).pack(pady=10)
        
        cargar_lista_prod()

    def ver_ventas(self, periodo):
        self.toggle_menu()
        win = ctk.CTkToplevel(self)
        win.title(f"Ventas - {periodo.capitalize()}")
        win.geometry("900x500")
        
        conn = sqlite3.connect(DB_PATH)
        ventas_db = conn.execute("SELECT id, fecha, total FROM ventas").fetchall()
        
        ventas_filtradas = []
        hoy = datetime.now()
        
        for v in ventas_db:
            try:
                fecha_v = datetime.strptime(v[1], "%Y-%m-%d %H:%M:%S")
                if periodo == "hoy":
                    if fecha_v.date() == hoy.date():
                        ventas_filtradas.append(v)
                elif periodo == "mes":
                    if fecha_v.year == hoy.year and fecha_v.month == hoy.month:
                        ventas_filtradas.append(v)
                elif periodo == "semana":
                    if fecha_v.isocalendar()[1] == hoy.isocalendar()[1] and fecha_v.year == hoy.year:
                        ventas_filtradas.append(v)
            except:
                pass
        
        lista = tk.Listbox(win, font=("Arial", 14))
        lista.pack(fill="both", expand=True, padx=20, pady=20)
        
        total_acumulado = 0
        for v in ventas_filtradas:
            venta_id, fecha, total = v
            # Buscar los productos específicos de esta venta
            detalles = conn.execute("SELECT cantidad, producto FROM detalle_ventas WHERE venta_id = ?", (venta_id,)).fetchall()
            productos_str = ", ".join([f"{d[0]}x {d[1]}" for d in detalles])
            
            lista.insert(tk.END, f"{fecha} | {productos_str} | Total: ${self.formatear_numero(total)}")
            total_acumulado += total
            
        conn.close()
            
        ctk.CTkLabel(win, text=f"TOTAL RECAUDADO ({periodo.upper()}): ${self.formatear_numero(total_acumulado)}", font=("Arial", 18, "bold"), text_color="#28a745").pack(pady=10)

if __name__ == "__main__":
    app = RegistroVentasApp()
    app.mainloop()
