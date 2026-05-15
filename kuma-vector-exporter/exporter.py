import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# ==========================================
# 設定（固定値）
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GEOJSON = os.path.join(BASE_DIR, 'aomori_boundaries.json')
ROADS_GEOJSON = os.path.join(BASE_DIR, 'aomori_roads.json')
RAILWAYS_GEOJSON = os.path.join(BASE_DIR, 'aomori_railways.json')
RIVERS_GEOJSON = os.path.join(BASE_DIR, 'aomori_rivers.json')

# 出力サイズ (px)
WIDTH, HEIGHT = 1200, 1200
MARGIN = 50

# 動物ごとの基本形
SHAPES = {
    "ツキノワグマ": "circle",
    "ニホンジカ": "rect",
    "イノシシ": "polygon"
}

# カテゴリごとの色
COLORS = {
    "人身": "#ff0000", # 赤
    "食害": "#ff9900", # オレンジ
    "目撃": "#0066ff"  # 青
}

class Projection:
    """緯度経度をSVG座標に変換するクラス"""
    def __init__(self, lat_min: float, lat_max: float, lng_min: float, lng_max: float):
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.lng_min = lng_min
        self.lng_max = lng_max
        
        # アスペクト比の調整
        self.scale_x = (WIDTH - 2 * MARGIN) / (lng_max - lng_min)
        self.scale_y = (HEIGHT - 2 * MARGIN) / (lat_max - lat_min)
        # 緯度による歪みを補正 (40.5度付近)
        self.aspect_correction = 1.0 / 0.76 
        self.scale_x /= self.aspect_correction

    def project(self, lat: float, lng: float) -> Tuple[float, float]:
        """緯度経度を座標 (x, y) に投影する"""
        x = MARGIN + (lng - self.lng_min) * self.aspect_correction * self.scale_x
        y = HEIGHT - MARGIN - (lat - self.lat_min) * self.scale_y
        return x, y

def get_fiscal_year(dt_str: str) -> str:
    """日付文字列から年度を取得する (4月始まり)"""
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return f"{dt.year}年度" if dt.month >= 4 else f"{dt.year - 1}年度"
    except Exception:
        return "不明年度"

def get_category(status: str) -> str:
    """出没状況からカテゴリ（人身、食害、目撃）を判定する"""
    if status == "人身被害": return "人身"
    if status in ["痕跡(食害)", "食害"]: return "食害"
    return "目撃"

def select_input_file() -> Optional[str]:
    """入力用JSONファイルを選択するダイアログを表示する"""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="入力データ（JSON）を選択してください",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        initialdir=os.getcwd()
    )
    root.destroy()
    return file_path if file_path else None

def select_output_file() -> Optional[str]:
    """出力用SVGファイルの保存先を選択するダイアログを表示する"""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.asksaveasfilename(
        title="出力するSVGファイルの保存先を指定してください",
        defaultextension=".svg",
        filetypes=[("SVG files", "*.svg")],
        initialfile="kuma_map_layers.svg",
        initialdir=os.getcwd()
    )
    root.destroy()
    return file_path if file_path else None

class YearSelectionDialog:
    """年度を選択するためのカスタムダイアログ"""
    def __init__(self, years: List[str]):
        self.selected_years: List[str] = []
        self.years = years
        
        self.root = tk.Tk()
        self.root.title("出力年度の選択")
        self.root.geometry("300x400")
        
        # ラベル
        label = tk.Label(self.root, text="出力したい年度にチェックを入れてください", pady=10)
        label.pack()
        
        # チェックボックス用フレーム
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=20)
        
        self.vars = {}
        for fy in self.years:
            var = tk.BooleanVar(value=True)
            self.vars[fy] = var
            cb = tk.Checkbutton(frame, text=fy, variable=var, anchor="w")
            cb.pack(fill="x")
        
        # ボタン
        btn_frame = tk.Frame(self.root, pady=20)
        btn_frame.pack()
        
        ok_button = tk.Button(btn_frame, text="OK (出力開始)", command=self.on_ok, width=15)
        ok_button.pack(side="left", padx=5)
        
        cancel_button = tk.Button(btn_frame, text="キャンセル", command=self.root.destroy, width=10)
        cancel_button.pack(side="left", padx=5)
        
        self.root.mainloop()

    def on_ok(self):
        self.selected_years = [fy for fy, var in self.vars.items() if var.get()]
        if not self.selected_years:
            messagebox.showwarning("警告", "少なくとも1つの年度を選択してください。")
            return
        self.root.destroy()

def select_years(available_fys: List[str]) -> List[str]:
    """ダイアログを表示して年度を選択させる"""
    dialog = YearSelectionDialog(available_fys)
    return dialog.selected_years

class AreaSelectionDialog:
    """出力エリア、ズーム倍率、解像度を選択するためのダイアログ"""
    def __init__(self, municipalities: List[str]):
        self.selected_area: str = "青森県全体"
        self.zoom_factor: float = 1.0
        self.canvas_size: int = 1200
        self.municipalities = ["青森県全体"] + sorted(municipalities)
        
        self.root = tk.Tk()
        self.root.title("出力設定の選択")
        self.root.geometry("380x350")
        
        # エリア選択
        tk.Label(self.root, text="出力したいエリアを選択:", pady=5).pack()
        self.combo = ttk.Combobox(self.root, values=self.municipalities, state="readonly", width=30)
        self.combo.set("青森県全体")
        self.combo.pack(pady=5)
        
        # ズーム倍率
        tk.Label(self.root, text="ズーム倍率 (市町村選択時のみ有効):", pady=5).pack()
        self.zoom_combo = ttk.Combobox(self.root, values=["等倍 (100%)", "2倍 (200%)", "4倍 (400%)", "8倍 (800%)"], state="readonly", width=30)
        self.zoom_combo.set("等倍 (100%)")
        self.zoom_combo.pack(pady=5)

        # 解像度
        tk.Label(self.root, text="出力サイズ (解像度):", pady=5).pack()
        self.size_combo = ttk.Combobox(self.root, values=["標準 (1200px)", "高画質 (2400px)", "超高画質 (3600px)"], state="readonly", width=30)
        self.size_combo.set("標準 (1200px)")
        self.size_combo.pack(pady=5)
        
        btn_frame = tk.Frame(self.root, pady=20)
        btn_frame.pack()
        
        ok_button = tk.Button(btn_frame, text="決定", command=self.on_ok, width=15)
        ok_button.pack(side="left", padx=5)
        
        self.root.mainloop()

    def on_ok(self):
        self.selected_area = self.combo.get()
        
        # ズーム倍率の取得
        zoom_text = self.zoom_combo.get()
        if "2倍" in zoom_text: self.zoom_factor = 2.0
        elif "4倍" in zoom_text: self.zoom_factor = 4.0
        elif "8倍" in zoom_text: self.zoom_factor = 8.0
        else: self.zoom_factor = 1.0
        
        # 解像度の取得
        size_text = self.size_combo.get()
        if "2400px" in size_text: self.canvas_size = 2400
        elif "3600px" in size_text: self.canvas_size = 3600
        else: self.canvas_size = 1200
            
        self.root.destroy()

def select_output_settings(municipalities: List[str]) -> Tuple[str, float, int]:
    """エリア、ズーム倍率、サイズを選択させる"""
    dialog = AreaSelectionDialog(municipalities)
    return dialog.selected_area, dialog.zoom_factor, dialog.canvas_size

def main():
    """メイン処理：完全にダイアログで操作する"""
    # 1. ファイル選択
    input_json = select_input_file()
    if not input_json:
        return

    output_svg = select_output_file()
    if not output_svg:
        return

    if not os.path.exists(DEFAULT_GEOJSON):
        messagebox.showerror("エラー", f"境界データが見つかりません:\n{DEFAULT_GEOJSON}")
        return

    # 2. データ読み込み
    try:
        with open(input_json, 'r', encoding='utf-8') as f:
            sightings = json.load(f)
        with open(DEFAULT_GEOJSON, 'r', encoding='utf-8') as f:
            boundaries = json.load(f)
    except Exception as e:
        messagebox.showerror("エラー", f"ファイルの読み込みに失敗しました:\n{e}")
        return

    # 追加地形データの読み込み（任意）
    def load_extra_geojson(path):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
        return None

    roads = load_extra_geojson(ROADS_GEOJSON)
    railways = load_extra_geojson(RAILWAYS_GEOJSON)
    rivers = load_extra_geojson(RIVERS_GEOJSON)

    # 3. エリア選択と範囲の計算
    try:
        # 市町村名のリストを作成
        m_names = list(set([f['properties'].get('N03_004') for f in boundaries['features'] if f['properties'].get('N03_004')]))
        target_area, zoom_mag, c_size = select_output_settings(m_names)
        
        # キャンバスサイズを動的に設定
        width, height = c_size, c_size
        margin = 50 * (c_size / 1200) # 解像度に合わせてマージンも調整
        
        # 範囲計算の対象となる地物を選定
        if target_area == "青森県全体":
            focus_features = boundaries['features']
            zoom_mag = 1.0 # 全県の場合はズーム無効
        else:
            focus_features = [f for f in boundaries['features'] if f['properties'].get('N03_004') == target_area]

        all_lats = []
        all_lngs = []
        for feature in focus_features:
            coords = feature['geometry']['coordinates']
            def extract_coords(c):
                if isinstance(c[0], list):
                    for sub in c: extract_coords(sub)
                else:
                    all_lngs.append(c[0])
                    all_lats.append(c[1])
            extract_coords(coords)
        
        if not all_lats or not all_lngs:
            messagebox.showerror("エラー", "指定されたエリアの座標データが見つかりません。")
            return

        lat_min, lat_max = min(all_lats), max(all_lats)
        lng_min, lng_max = min(all_lngs), max(all_lngs)
        
        # ズーム倍率の適用
        if zoom_mag > 1.0:
            lat_mid = (lat_min + lat_max) / 2
            lng_mid = (lng_min + lng_max) / 2
            lat_half = (lat_max - lat_min) / (2 * zoom_mag)
            lng_half = (lng_max - lng_min) / (2 * zoom_mag)
            lat_min, lat_max = lat_mid - lat_half, lat_mid + lat_half
            lng_min, lng_max = lng_mid - lng_half, lng_mid + lng_half

        # 解像度に応じた Projection クラスのインスタンス化 (WIDTH/HEIGHT/MARGINを動的に)
        class DynamicProjection(Projection):
            def __init__(self, lat_min, lat_max, lng_min, lng_max, w, h, m):
                self.lat_min = lat_min
                self.lat_max = lat_max
                self.lng_min = lng_min
                self.lng_max = lng_max
                self.w, self.h, self.m = w, h, m
                self.scale_x = (w - 2 * m) / (lng_max - lng_min)
                self.scale_y = (h - 2 * m) / (lat_max - lat_min)
                self.aspect_correction = 1.0 / 0.76 
                self.scale_x /= self.aspect_correction
            def project(self, lat: float, lng: float) -> Tuple[float, float]:
                x = self.m + (lng - self.lng_min) * self.aspect_correction * self.scale_x
                y = self.h - self.m - (lat - self.lat_min) * self.scale_y
                return x, y

        proj = DynamicProjection(lat_min, lat_max, lng_min, lng_max, width, height, margin)
    except Exception as e:
        messagebox.showerror("エラー", f"エリア設定または範囲計算に失敗しました:\n{e}")
        return

    # 4. データを分類
    tree = {}
    for item in sightings:
        fy = get_fiscal_year(item.get("datetime", ""))
        species = item.get("species") or "クマ"
        category = get_category(item.get("status", ""))
        if fy not in tree: tree[fy] = {}
        if species not in tree[fy]: tree[fy][species] = {}
        if category not in tree[fy][species]: tree[fy][species][category] = []
        tree[fy][species][category].append(item)

    # 5. 年度選択（ダイアログ）
    available_fys = sorted(list(tree.keys()), reverse=True)
    target_fys = select_years(available_fys)
    
    if not target_fys:
        return

    # 6. SVG生成
    svg_lines = [
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">',
        f'<rect width="100%" height="100%" fill="white" />'
    ]

    # レイヤー: 市町村境界
    svg_lines.append('<g id="Aomori_Boundaries" inkscape:label="青森県市町村境界" inkscape:groupmode="layer">')
    for feature in boundaries['features']:
        name = feature['properties'].get('N03_004', '不明')
        svg_lines.append(f'  <g id="Boundary_{name}" inkscape:label="{name}">')
        
        geom = feature['geometry']
        polygons = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
        
        for poly in polygons:
            paths = []
            for ring in poly:
                pts = [proj.project(p[1], p[0]) for p in ring]
                path_str = "M " + " L ".join([f"{x:.2f} {y:.2f}" for x, y in pts]) + " Z"
                paths.append(path_str)
            svg_lines.append(f'    <path d="{" ".join(paths)}" fill="#f8f9fa" stroke="#adb5bd" stroke-width="0.5" />')
        svg_lines.append('  </g>')
    svg_lines.append('</g>')

    # レイヤー: 河川
    if rivers:
        svg_lines.append('<g id="Aomori_Rivers" inkscape:label="河川" inkscape:groupmode="layer">')
        for feature in rivers['features']:
            if feature['geometry']['type'] == 'LineString':
                pts = [proj.project(p[1], p[0]) for p in feature['geometry']['coordinates']]
                path_str = "M " + " L ".join([f"{x:.2f} {y:.2f}" for x, y in pts])
                svg_lines.append(f'  <path d="{path_str}" fill="none" stroke="#a5d8ff" stroke-width="1.0" />')
        svg_lines.append('</g>')

    # レイヤー: 鉄道
    if railways:
        svg_lines.append('<g id="Aomori_Railways" inkscape:label="鉄道" inkscape:groupmode="layer">')
        for feature in railways['features']:
            if feature['geometry']['type'] == 'LineString':
                pts = [proj.project(p[1], p[0]) for p in feature['geometry']['coordinates']]
                path_str = "M " + " L ".join([f"{x:.2f} {y:.2f}" for x, y in pts])
                svg_lines.append(f'  <path d="{path_str}" fill="none" stroke="#495057" stroke-width="0.8" stroke-dasharray="2,2" />')
        svg_lines.append('</g>')

    # レイヤー: 道路
    if roads:
        svg_lines.append('<g id="Aomori_Roads" inkscape:label="主要道路" inkscape:groupmode="layer">')
        for feature in roads['features']:
            if feature['geometry']['type'] == 'LineString':
                pts = [proj.project(p[1], p[0]) for p in feature['geometry']['coordinates']]
                path_str = "M " + " L ".join([f"{x:.2f} {y:.2f}" for x, y in pts])
                # 道路種別によって太さを変える
                highway = feature['properties'].get('highway', '')
                if highway in ['motorway', 'trunk']:
                    width, color = 1.5, "#ff922b" # オレンジ
                elif highway == 'primary':
                    width, color = 1.0, "#fab005" # 黄色
                else:
                    width, color = 0.5, "#adb5bd" # グレー
                svg_lines.append(f'  <path d="{path_str}" fill="none" stroke="{color}" stroke-width="{width}" />')
        svg_lines.append('</g>')

    # レイヤー: 出没地点
    for fy in target_fys:
        svg_lines.append(f'<g id="FY_{fy}" inkscape:label="{fy}" inkscape:groupmode="layer">')
        for species in sorted(tree[fy].keys()):
            safe_species = species.replace(" ", "_")
            svg_lines.append(f'  <g id="{fy}_{safe_species}" inkscape:label="{species}">')
            for category in ["人身", "食害", "目撃"]:
                if category not in tree[fy][species]: continue
                color = COLORS.get(category, "#000")
                svg_lines.append(f'    <g id="{fy}_{safe_species}_{category}" inkscape:label="{category}" fill="{color}">')
                for p in tree[fy][species][category]:
                    x, y = proj.project(p["lat"], p["lng"])
                    shape = SHAPES.get(species, "circle")
                    m_id = str(p.get("id", p.get("management_number", "")))
                    
                    # 確認ステータスの取得
                    is_verified = p.get("verified", False)
                    v_status = "(確認済)" if is_verified else "(未確認)"
                    full_label = f"{m_id} {v_status}"
                    
                    # 解像度に合わせて記号サイズを調整
                    base_r = 2 * (c_size / 1200)
                    
                    if shape == "circle":
                        svg_lines.append(f'      <circle id="point_{m_id}" inkscape:label="{full_label}" cx="{x:.2f}" cy="{y:.2f}" r="{base_r:.2f}" />')
                    elif shape == "rect":
                        svg_lines.append(f'      <rect id="point_{m_id}" inkscape:label="{full_label}" x="{x-base_r*0.75:.2f}" y="{y-base_r*0.75:.2f}" width="{base_r*1.5:.2f}" height="{base_r*1.5:.2f}" />')
                    else:
                        svg_lines.append(f'      <path id="point_{m_id}" inkscape:label="{full_label}" d="M {x:.2f} {y-base_r:.2f} L {x-base_r:.2f} {y+base_r:.2f} L {x+base_r:.2f} {y+base_r:.2f} Z" />')
                svg_lines.append('    </g>')
            svg_lines.append('  </g>')
        svg_lines.append('</g>')

    svg_lines.append('</svg>')

    try:
        with open(output_svg, 'w', encoding='utf-8') as f:
            f.write('\n'.join(svg_lines))
        messagebox.showinfo("成功", f"SVGファイルを保存しました:\n{output_svg}")
    except Exception as e:
        messagebox.showerror("エラー", f"ファイルの保存に失敗しました:\n{e}")

if __name__ == "__main__":
    main()


