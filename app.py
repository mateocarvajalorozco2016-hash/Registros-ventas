import os
import sqlite3
import json
import shutil
from datetime import datetime
import difflib
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageOps

# Configuración básica de la ventana
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

DATOS_DIR = "datos"
PRODUCTOS_IMG_DIR = os.path.join(DATOS_DIR, "productos")
DINERO_IMG_DIR = os.path.join(DATOS_DIR, "dinero")
DB_PATH = os.path.join(DATOS_DIR, "ventas.db")
CONFIG_PATH = os.path.join(DATOS_DIR, "configuracion.json")

# Asegurar directorios
for d in [DATOS_DIR, PRODUCTOS_IMG_DIR, DINERO_IMG_DIR]:
    os.makedirs(d, exist_ok=True)

class RegistroVentasApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Registro de Ventas")
        self.geometry("1024x720")
        self.minsize(900, 600)
        
        self.init_db()
        self.load_config()
        
        self.venta_actual = [] # [{'id', 'nombre', 'precio', 'cantidad'}]
        self.dinero_recibido = 0
        
        self.crear_interfaz()
        self.cargar_productos_ui()
        
    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nombre TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY, nombre TEXT, precio REAL, categoria_id INTEGER, imagen TEXT)''')
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
        # Barra superior negra
        self.top_bar = ctk.CTkFrame(self, fg_color="#1a1a1a", height=50, corner_radius=0)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)
        
        self.btn_menu = ctk.CTkButton(self.top_bar, text="☰", width=40, font=("Arial", 24), fg_color="transparent", command=self.toggle_menu)
        self.btn_menu.pack(side="left", padx=10)
        
        self.lbl_negocio = ctk.CTkLabel(self.top_bar, text=self.config["negocio"], font=("Arial", 20, "bold"), text_color="white")
        self.lbl_negocio.pack(side="left", padx=10)

        # Contenedor principal (Layout dividido en Izquierda y Derecha)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # --- PANEL CENTRAL (Productos y Billetes) ---
        self.panel_central = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.panel_central.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Header del panel central (Nueva Venta a la izq, Buscador a la der)
        self.header_central = ctk.CTkFrame(self.panel_central, fg_color="transparent")
        self.header_central.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(self.header_central, text="Nueva Venta", font=("Arial", 24, "bold")).pack(side="left")
        
        self.var_busqueda = tk.StringVar()
        self.var_busqueda.trace_add("write", lambda *args: self.filtrar_productos())
        self.entry_busqueda = ctk.CTkEntry(self.header_central, textvariable=self.var_busqueda, placeholder_text="Buscar producto...", width=250)
        self.entry_busqueda.pack(side="right")

        # Scroll de Productos
        self.scroll_productos = ctk.CTkScrollableFrame(self.panel_central)
        self.scroll_productos.pack(fill="both", expand=True)
        
        # Zona de Billetes (Parte inferior central)
        self.frame_billetes = ctk.CTkFrame(self.panel_central, height=120)
        self.frame_billetes.pack(fill="x", pady=(10, 0))
        self.cargar_billetes_ui()

        # --- PANEL DERECHO (Venta Actual) ---
        self.panel_derecho = ctk.CTkFrame(self.main_container, width=300)
        self.panel_derecho.pack(side="right", fill="y", padx=10, pady=10)
        self.panel_derecho.pack_propagate(False)

        ctk.CTkLabel(self.panel_derecho, text="Venta Actual", font=("Arial", 18, "bold")).pack(pady=10)
        
        self.lista_venta = tk.Listbox(self.panel_derecho, font=("Arial", 12))
        self.lista_venta.pack(fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkButton(self.panel_derecho, text="Eliminar seleccionado", fg_color="#d9534f", hover_color="#c9302c", command=self.eliminar_item_venta).pack(pady=5, padx=10, fill="x")

        # Totales
        self.lbl_total = ctk.CTkLabel(self.panel_derecho, text="TOTAL: $0", font=("Arial", 20, "bold"))
        self.lbl_total.pack(pady=(10,0))

        # Input Valor Recibido Personalizado con corrección de cursor
        frame_recibido = ctk.CTkFrame(self.panel_derecho, fg_color="transparent")
        frame_recibido.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(frame_recibido, text="Valor Recibido:").pack(side="left")
        
        self.var_recibido = tk.StringVar(value="0")
        self.var_recibido.trace_add("write", self.formatear_moneda_dinamico)
        self.entry_recibido = ctk.CTkEntry(frame_recibido, textvariable=self.var_recibido, width=120)
        self.entry_recibido.pack(side="right")

        self.lbl_cambio = ctk.CTkLabel(self.panel_derecho, text="CAMBIO: $0", font=("Arial", 18, "bold"), text_color="green")
        self.lbl_cambio.pack(pady=5)

        ctk.CTkButton(self.panel_derecho, text="REGISTRAR VENTA", height=50, font=("Arial", 16, "bold"), fg_color="#5cb85c", hover_color="#4cae4c", command=self.registrar_venta).pack(side="bottom", fill="x", padx=10, pady=10)

        # --- MENÚ LATERAL DESLIZANTE ---
        self.menu_lateral = ctk.CTkFrame(self, width=250, fg_color="#2b2b2b", corner_radius=0)
        self.menu_visible = False
        
        opciones_menu = [
            ("Nueva venta", self.toggle_menu),
            ("Ventas de hoy", lambda: self.ver_ventas("hoy")),
            ("Ventas semana", lambda: self.ver_ventas("semana")),
            ("Ventas mes", lambda: self.ver_ventas("mes")),
            ("Productos y Categorías", self.abrir_gestion_productos),
            ("Configuración", self.abrir_configuracion)
        ]
        
        for texto, comando in opciones_menu:
            btn = ctk.CTkButton(self.menu_lateral, text=texto, font=("Arial", 14), fg_color="transparent", text_color="white", anchor="w", command=comando)
            btn.pack(fill="x", padx=20, pady=15)

    def toggle_menu(self):
        if self.menu_visible:
            self.menu_lateral.place_forget()
            self.menu_visible = False
        else:
            self.menu_lateral.place(x=0, y=50, relheight=1.0)
            self.menu_lateral.tkraise()
            self.menu_visible = True

    # ================= FUNCIONES CORE =================
    
    def formatear_moneda_dinamico(self, var_name, index, mode):
        """Corrige el salto del cursor al escribir formatos de miles."""
        widget = self.focus_get()
        if not isinstance(widget, (tk.Entry, ttk.Entry, ctk.CTkEntry)):
            # Si se actualiza programáticamente sin foco, solo formateamos
            val_crudo = self.var_recibido.get().replace(".", "").replace("$", "")
            if val_crudo.isdigit():
                self.var_recibido.set(f"{int(val_crudo):,}".replace(",", "."))
                self.calcular_cambio()
            return

        texto = self.var_recibido.get()
        if not texto:
            self.calcular_cambio()
            return

        cursor_pos = widget.index(tk.INSERT)
        texto_limpio = texto.replace(".", "")
        if not texto_limpio.isdigit():
            # Deshacer letras
            texto_filtrado = ''.join([c for c in texto if c.isdigit()])
            if texto_filtrado:
                self.var_recibido.set(f"{int(texto_filtrado):,}".replace(",", "."))
            else:
                self.var_recibido.set("0")
            return

        # Calcular cuántos dígitos hay a la derecha del cursor
        texto_derecha = texto[cursor_pos:]
        digitos_derecha = len(texto_derecha.replace(".", ""))

        formateado = f"{int(texto_limpio):,}".replace(",", ".")
        self.var_recibido.set(formateado)

        # Reposicionar el cursor desde la derecha
        nueva_pos_cursor = len(formateado)
        for i in range(len(formateado) - 1, -1, -1):
            if digitos_derecha == 0:
                nueva_pos_cursor = i + 1
                break
            if formateado[i].isdigit():
                digitos_derecha -= 1

        widget.icursor(nueva_pos_cursor)
        self.calcular_cambio()

    def formatear_numero(self, num):
        return f"{int(num):,}".replace(",", ".")

    def agregar_a_venta(self, producto):
        # Busca si ya está
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
        # El callback de trace actualiza el cambio

    def calcular_cambio(self):
        total = sum(p['precio'] * p['cantidad'] for p in self.venta_actual)
        recibido_str = self.var_recibido.get().replace(".", "")
        recibido = int(recibido_str) if recibido_str.isdigit() else 0
        
        cambio = recibido - total
        if cambio < 0 or total == 0:
            self.lbl_cambio.configure(text="CAMBIO: $0", text_color="gray")
        else:
            self.lbl_cambio.configure(text=f"CAMBIO: ${self.formatear_numero(cambio)}", text_color="green")

    def registrar_venta(self):
        if not self.venta_actual:
            messagebox.showwarning("Venta vacía", "No hay productos en la venta actual.")
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

        # Limpiar
        self.venta_actual = []
        self.var_recibido.set("0")
        self.actualizar_lista_venta()
        messagebox.showinfo("Éxito", "Venta registrada correctamente.")

    # ================= PRODUCTOS Y BUSCADOR =================
    
    def cargar_productos_ui(self):
        for widget in self.scroll_productos.winfo_children():
            widget.destroy()
            
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
        if not busqueda:
            resultados = self.productos_db
        else:
            nombres = [p[1] for p in self.productos_db]
            coincidencias = difflib.get_close_matches(busqueda, nombres, n=10, cutoff=0.5)
            
            # Buscar también coincidencias parciales directas
            for p in self.productos_db:
                if busqueda in p[1].lower() and p[1] not in coincidencias:
                    coincidencias.append(p[1])
                    
            resultados = [p for p in self.productos_db if p[1] in coincidencias]

        if not resultados:
            ctk.CTkLabel(self.scroll_productos, text=f"No encontramos '{busqueda}'", font=("Arial", 16)).pack(pady=20)
            return

        # Layout en cuadrícula adaptativa (Aumentamos el tamaño de la tarjeta)
        row, col = 0, 0
        for p in resultados:
            prod_id, nombre, precio, img_path = p
            frame = ctk.CTkFrame(self.scroll_productos, width=140, height=160)
            frame.grid(row=row, column=col, padx=10, pady=10)
            frame.pack_propagate(False)

            if img_path and os.path.exists(img_path):
                img = Image.open(img_path)
                ctk_img = ctk.CTkImage(light_image=img, size=(90, 90))
                lbl_img = ctk.CTkLabel(frame, image=ctk_img, text="")
            else:
                lbl_img = ctk.CTkLabel(frame, text="Sin imagen", width=90, height=90, fg_color="gray")
            
            lbl_img.pack(pady=5)
            ctk.CTkLabel(frame, text=nombre, font=("Arial", 12, "bold")).pack()
            ctk.CTkLabel(frame, text=f"${self.formatear_numero(precio)}", font=("Arial", 12)).pack()
            
            # Bind click
            producto_dict = {'id': prod_id, 'nombre': nombre, 'precio': precio}
            for w in [frame, lbl_img]:
                w.bind("<Button-1>", lambda e, pd=producto_dict: self.agregar_a_venta(pd))
            
            col += 1
            if col > 4: # Depende del ancho de pantalla
                col = 0
                row += 1

    # ================= BILLETES UI =================
    
    def cargar_billetes_ui(self):
        for w in self.frame_billetes.winfo_children():
            w.destroy()
            
        ctk.CTkLabel(self.frame_billetes, text="Dinero Rápido:", font=("Arial", 12, "bold")).pack(side="left", padx=10)
        
        denominaciones = [1000, 2000, 5000, 10000, 20000, 50000, 100000]
        for val in denominaciones:
            img_path = self.config["billetes"].get(str(val))
            if img_path and os.path.exists(img_path):
                img = Image.open(img_path)
                ctk_img = ctk.CTkImage(light_image=img, size=(60, 30))
                btn = ctk.CTkButton(self.frame_billetes, image=ctk_img, text="", width=60, command=lambda v=val: self.sumar_dinero(v))
            else:
                btn = ctk.CTkButton(self.frame_billetes, text=f"${self.formatear_numero(val)}", width=60, command=lambda v=val: self.sumar_dinero(v))
            btn.pack(side="left", padx=5, pady=10)

    # ================= GESTIÓN (Ventanas Secundarias simplificadas) =================
    # Para cumplir con la concisión, estas funciones se integran directamente creando Toplevels
    
    def abrir_configuracion(self):
        self.toggle_menu()
        win = ctk.CTkToplevel(self)
        win.title("Configuración")
        win.geometry("400x300")
        win.grab_set()
        
        ctk.CTkLabel(win, text="Nombre del Negocio:").pack(pady=10)
        var_neg = tk.StringVar(value=self.config["negocio"])
        ctk.CTkEntry(win, textvariable=var_neg, width=200).pack()
        
        def guardar():
            self.config["negocio"] = var_neg.get()
            self.save_config()
            self.lbl_negocio.configure(text=self.config["negocio"])
            win.destroy()
            
        ctk.CTkButton(win, text="Guardar", command=guardar).pack(pady=20)

    def abrir_gestion_productos(self):
        self.toggle_menu()
        win = ctk.CTkToplevel(self)
        win.title("Gestión de Productos")
        win.geometry("600x500")
        win.grab_set()

        # Vista Previa Grande
        self.img_temporal_path = None
        lbl_preview = ctk.CTkLabel(win, text="[Vista Previa]", width=150, height=150, fg_color="#e0e0e0")
        lbl_preview.pack(pady=10)

        def seleccionar_img():
            ruta = filedialog.askopenfilename(filetypes=[("Imágenes", "*.png *.jpg *.jpeg")])
            if ruta:
                self.img_temporal_path = ruta
                # Usar ImageOps.contain para no deformar y verla completa
                img = Image.open(ruta)
                img = ImageOps.contain(img, (150, 150))
                ctk_img = ctk.CTkImage(light_image=img, size=(img.width, img.height))
                lbl_preview.configure(image=ctk_img, text="")

        frame_form = ctk.CTkFrame(win, fg_color="transparent")
        frame_form.pack(pady=10)

        ctk.CTkLabel(frame_form, text="Nombre:").grid(row=0, column=0, padx=5, pady=5)
        entry_nom = ctk.CTkEntry(frame_form)
        entry_nom.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(frame_form, text="Precio:").grid(row=1, column=0, padx=5, pady=5)
        entry_pre = ctk.CTkEntry(frame_form)
        entry_pre.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkButton(frame_form, text="Seleccionar Imagen", command=seleccionar_img).grid(row=2, column=0, columnspan=2, pady=10)

        def guardar_prod():
            nom = entry_nom.get()
            pre = entry_pre.get().replace(".", "")
            if not nom or not pre.isdigit():
                messagebox.showerror("Error", "Datos inválidos")
                return
            
            img_dest = ""
            if self.img_temporal_path:
                ext = os.path.splitext(self.img_temporal_path)[1]
                img_dest = os.path.join(PRODUCTOS_IMG_DIR, f"{nom}_{datetime.now().strftime('%S%f')}{ext}")
                shutil.copy(self.img_temporal_path, img_dest)

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO productos (nombre, precio, imagen) VALUES (?, ?, ?)", (nom, float(pre), img_dest))
            conn.commit()
            conn.close()
            
            self.cargar_productos_ui()
            win.destroy()

        ctk.CTkButton(win, text="Guardar Producto", command=guardar_prod).pack(pady=10)

    def ver_ventas(self, periodo):
        self.toggle_menu()
        win = ctk.CTkToplevel(self)
        win.title(f"Ventas - {periodo.capitalize()}")
        win.geometry("600x400")
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        hoy = datetime.now()
        if periodo == "hoy":
            fecha_str = hoy.strftime("%Y-%m-%d")
            c.execute("SELECT id, fecha, total, recibido FROM ventas WHERE fecha LIKE ?", (f"{fecha_str}%",))
        elif periodo == "mes":
            fecha_str = hoy.strftime("%Y-%m")
            c.execute("SELECT id, fecha, total, recibido FROM ventas WHERE fecha LIKE ?", (f"{fecha_str}%",))
        else:
            # Semana (Simplificado para el ejemplo)
            c.execute("SELECT id, fecha, total, recibido FROM ventas") 
            
        ventas = c.fetchall()
        conn.close()
        
        lista = tk.Listbox(win, font=("Arial", 12))
        lista.pack(fill="both", expand=True, padx=20, pady=20)
        
        total_acumulado = 0
        for v in ventas:
            lista.insert(tk.END, f"Venta #{v[0]} - {v[1]} | Total: ${self.formatear_numero(v[2])}")
            total_acumulado += v[2]
            
        ctk.CTkLabel(win, text=f"TOTAL ACUMULADO: ${self.formatear_numero(total_acumulado)}", font=("Arial", 16, "bold")).pack(pady=10)

if __name__ == "__main__":
    app = RegistroVentasApp()
    app.mainloop()
