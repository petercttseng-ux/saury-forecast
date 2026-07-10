# -*- coding: utf-8 -*-
"""
西北太平洋秋刀魚漁場資訊服務系統 - 主程式
農業部水產試驗所 漁海況研究小組
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector
import cartopy.crs as ccrs
import numpy as np
from threading import Thread
from typing import Optional, Dict
import config

plt.rcParams['font.sans-serif'] = [
    'Microsoft JhengHei', 'Microsoft YaHei', 'SimHei',
    'Arial Unicode MS', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False


# ============================================================
# 樣式常數
# ============================================================
class Style:
    PRIMARY       = '#1a73e8'
    PRIMARY_DARK  = '#1557b0'
    PRIMARY_LIGHT = '#4285f4'
    BG_MAIN       = '#f0f4f8'
    BG_PANEL      = '#ffffff'
    BG_HEADER     = '#1a73e8'
    BG_DARK       = '#263238'
    TEXT_PRIMARY  = '#202124'
    TEXT_LIGHT    = '#ffffff'
    FONT          = 'Microsoft JhengHei'
    FONT_MONO     = 'Consolas'
    SZ_NORMAL     = 10
    SZ_SMALL      = 9


# ============================================================
# 狀態列
# ============================================================
class StatusBar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, relief='sunken', borderwidth=1)

        self._status = tk.StringVar(value='就緒')
        self._coords = tk.StringVar(value='經度: ---  緯度: ---  溫度: ---')

        # 進度條（平時隱藏）
        self._progress = ttk.Progressbar(
            self, mode='indeterminate', length=120)

        ttk.Label(self, textvariable=self._status,
                  anchor='w', padding=(8, 3)).pack(side='left', fill='x', expand=True)

        ttk.Separator(self, orient='vertical').pack(side='left', fill='y', padx=2)

        ttk.Label(self, textvariable=self._coords,
                  anchor='e', padding=(8, 3),
                  foreground=Style.PRIMARY,
                  font=(Style.FONT_MONO, Style.SZ_SMALL)).pack(side='right')

    def set_status(self, text: str, busy: bool = False):
        self._status.set(text)
        if busy:
            self._progress.pack(side='left', padx=(0, 8))
            self._progress.start(15)
        else:
            self._progress.stop()
            self._progress.pack_forget()

    def set_coordinates(self, lon=None, lat=None, value=None):
        if lon is None:
            self._coords.set('經度: ---  緯度: ---  溫度: ---')
        else:
            v = f'{value:.2f}C' if (value is not None and not np.isnan(value)) else '---'
            self._coords.set(f'E{lon:.3f}  N{lat:.3f}  T:{v}')


# ============================================================
# ECDF 圖表視窗
# ============================================================
class ECDFChartWindow(tk.Toplevel):
    def __init__(self, parent, ecdf_analyzer):
        super().__init__(parent)
        self.title('ECDF 分析圖表 - 秋刀魚棲息環境')
        self.geometry('920x530')
        self._build(ecdf_analyzer)

    def _build(self, analyzer):
        fig = Figure(figsize=(10, 5.2), dpi=96, facecolor='#f8f9fa')
        fig.suptitle('秋刀魚漁獲海洋環境 ECDF 分析',
                     fontsize=13, fontweight='bold', y=0.98)

        params = [
            ('sst',      'SST',  '海面水溫 (C)', '#1a73e8'),
            ('100m_temp','100mT','100m 次表層水溫 (C)', '#e53935'),
        ]

        for idx, (key, label, xlabel, color) in enumerate(params):
            ax = fig.add_subplot(1, 2, idx + 1)

            if key not in analyzer.ecdf_results:
                ax.text(0.5, 0.5, '無資料', ha='center', va='center',
                        transform=ax.transAxes)
                continue

            res = analyzer.ecdf_results[key]
            sv, cdf = res['sorted_values'], res['cdf']
            p = res['percentiles']

            ax.plot(sv, cdf, color=color, lw=2.2, label='漁獲記錄 ECDF')

            p25 = p.get('low', sv[0])
            p75 = p.get('high', sv[-1])
            ax.axvspan(p25, p75, alpha=0.15, color=color,
                       label=f'最適範圍 {p25:.1f}-{p75:.1f}C')

            for pname, pval, ls in [
                ('very_low', 0.10, ':'),
                ('low',      0.25, '--'),
                ('moderate', 0.50, '-'),
                ('high',     0.75, '--'),
                ('very_high',0.90, ':'),
            ]:
                tv = p.get(pname)
                if tv is not None:
                    ax.axvline(tv, color='gray', lw=0.8, ls=ls, alpha=0.7)
                    ax.text(tv, pval + 0.03, f'{tv:.1f}',
                            fontsize=7, ha='center', color='dimgray')

            mean_val = res['mean']
            ax.axvline(mean_val, color='darkorange', lw=1.5, ls='-.',
                       label=f'平均 {mean_val:.1f}C')

            ax.set_xlabel(xlabel, fontsize=10)
            ax.set_ylabel('累積機率', fontsize=10)
            ax.set_title(f'{label} ECDF  (n={len(sv)})',
                         fontsize=11, fontweight='bold')
            ax.set_ylim(0, 1.05)
            ax.grid(True, alpha=0.3, lw=0.5)
            ax.legend(fontsize=8, loc='upper left')

        fig.tight_layout(rect=[0, 0, 1, 0.95])

        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        NavigationToolbar2Tk(canvas, self).update()


# ============================================================
# 控制面板
# ============================================================
class ControlPanel(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(10, 8))
        self.app = app
        self._build()

    def _build(self):
        row = 0

        # ── 標題 banner ──
        banner = tk.Frame(self, bg=Style.BG_HEADER, height=56)
        banner.grid(row=row, column=0, sticky='ew', pady=(0, 8))
        banner.grid_propagate(False)
        tk.Label(
            banner, text='漁場資訊服務系統',
            bg=Style.BG_HEADER, fg='white',
            font=(Style.FONT, 12, 'bold')
        ).place(relx=0.5, rely=0.5, anchor='center')
        row += 1

        # ── 資料類型 ──
        f = self._lf('資料類型', row); row += 1
        self.data_type_var = tk.StringVar(value='sst')
        for txt, val in [
            ('海面水溫 (SST)',        'sst'),
            ('次表層水溫',             'subtemp'),
            ('組合圖 (SST+海流)',      'combined'),
            ('秋刀魚棲息地預測',       'habitat'),
        ]:
            ttk.Radiobutton(
                f, text=txt, value=val,
                variable=self.data_type_var,
                command=self._on_type_change
            ).pack(anchor='w', padx=6, pady=1)

        # ── 日期選擇 ──
        f2 = self._lf('選擇日期', row); row += 1
        self.date_combo = ttk.Combobox(f2, state='readonly', width=16)
        self.date_combo.pack(fill='x', padx=4, pady=4)
        self.date_combo.bind('<<ComboboxSelected>>', lambda _: self.app.redraw())

        # ── 深度選擇 ──
        self.depth_frame = self._lf('深度選擇', row); row += 1
        self.depth_var = tk.StringVar(value='100m')
        inner = ttk.Frame(self.depth_frame)
        inner.pack(fill='x')
        for d in ['50m', '100m', '200m', '400m']:
            ttk.Radiobutton(inner, text=d, value=d,
                            variable=self.depth_var).pack(side='left', expand=True)

        # ── 顯示選項 ──
        f3 = self._lf('顯示選項', row); row += 1
        self.show_isotherms_var = tk.BooleanVar(value=True)
        self.show_values_var    = tk.BooleanVar(value=True)
        self.show_currents_var  = tk.BooleanVar(value=True)
        ttk.Checkbutton(f3, text='顯示等溫線',
                        variable=self.show_isotherms_var).pack(anchor='w', padx=6)
        ttk.Checkbutton(f3, text='等溫線標示數值',
                        variable=self.show_values_var).pack(anchor='w', padx=6)
        ttk.Checkbutton(f3, text='顯示表面海流',
                        variable=self.show_currents_var).pack(anchor='w', padx=6)
        row_inner = ttk.Frame(f3)
        row_inner.pack(fill='x', padx=6, pady=(4, 0))
        ttk.Label(row_inner, text='等溫線間隔:').pack(side='left')
        self.iso_interval_var = tk.StringVar(value='2')
        ttk.Combobox(row_inner, textvariable=self.iso_interval_var,
                     values=['1', '2', '3', '4', '5'],
                     state='readonly', width=4).pack(side='left', padx=4)

        # ── ECDF 分析結果 ──
        f4 = self._lf('ECDF 分析結果', row); row += 1
        self.ecdf_text = tk.Text(
            f4, height=9, width=28,
            font=(Style.FONT_MONO, Style.SZ_SMALL),
            state='disabled', wrap='word',
            bg='#f8f9fa', relief='flat', bd=0
        )
        self.ecdf_text.pack(fill='both', padx=4, pady=4)

        # ── 操作按鈕 ──
        bf = ttk.Frame(self, padding=(0, 4))
        bf.grid(row=row, column=0, sticky='ew'); row += 1
        for txt, cmd in [
            ('重新繪製',    self.app.redraw),
            ('重置視野',    self.app.reset_view),
            ('ECDF 圖表',  self.app.show_ecdf_chart),
            ('儲存圖片',   self.app.save_figure),
            ('重新下載',   self.app.re_download),
        ]:
            ttk.Button(bf, text=txt, command=cmd).pack(fill='x', pady=2)

        # ── 機構標示 ──
        org = ttk.Frame(self)
        org.grid(row=row, column=0, sticky='sew', pady=(10, 0)); row += 1
        ttk.Separator(org).pack(fill='x', pady=(0, 6))
        tk.Label(
            org, text=config.ORGANIZATION_LABEL,
            font=(Style.FONT, 10, 'bold'),
            fg=Style.PRIMARY, bg=Style.BG_PANEL,
            wraplength=240, justify='center'
        ).pack()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(row, weight=1)
        self._on_type_change()

    def _lf(self, text, row):
        f = ttk.LabelFrame(self, text=f'  {text}  ', padding=(6, 4))
        f.grid(row=row, column=0, sticky='ew', pady=(0, 6))
        return f

    def _on_type_change(self):
        dt = self.data_type_var.get()
        if dt in ('subtemp', 'combined', 'habitat'):
            self.depth_frame.grid()
        else:
            self.depth_frame.grid_remove()
        self.app.update_date_list()

    def update_ecdf_info(self, info: Dict):
        self.ecdf_text.config(state='normal')
        self.ecdf_text.delete('1.0', 'end')
        lines = [
            '秋刀魚漁獲環境分析',
            '-' * 22,
            f"資料筆數: {info.get('data_count', '---')}",
            f"有漁獲筆數: {info.get('catch_count', '---')}",
            '',
            '【SST 最適範圍 (25-75%)】',
            f"  {info.get('SST_optimal', '---')}",
            f"  平均: {info.get('SST_mean', '---')}",
            '',
            '【100mT 最適範圍 (25-75%)】',
            f"  {info.get('100mT_optimal', '---')}",
            f"  平均: {info.get('100mT_mean', '---')}",
        ]
        self.ecdf_text.insert('1.0', '\n'.join(lines))
        self.ecdf_text.config(state='disabled')

    def get_settings(self) -> Dict:
        return {
            'data_type':         self.data_type_var.get(),
            'date':              self.date_combo.get(),
            'depth':             self.depth_var.get(),
            'show_isotherms':    self.show_isotherms_var.get(),
            'show_values':       self.show_values_var.get(),
            'isotherm_interval': int(self.iso_interval_var.get()),
            'show_currents':     self.show_currents_var.get(),
        }


# ============================================================
# 地圖畫布
# ============================================================
class MapCanvas(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_data: Optional[Dict] = None
        self.current_sst_data: Optional[Dict] = None
        self._rect_selector = None
        self._zoom_mode = False
        self._build()

    def _build(self):
        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(side='top', fill='x')

        self.figure = Figure(figsize=(12, 9), dpi=config.DPI, facecolor='white')
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()

        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

        # 框選放大按鈕
        self.zoom_btn = tk.Button(
            toolbar_frame, text='框選放大',
            relief='flat', bg='#e8f0fe', fg=Style.PRIMARY,
            font=(Style.FONT, Style.SZ_SMALL), cursor='hand2',
            command=self.toggle_zoom_mode
        )
        self.zoom_btn.pack(side='left', padx=6)

        self.canvas.get_tk_widget().pack(side='top', fill='both', expand=True)
        self.canvas.mpl_connect('motion_notify_event', self._on_hover)
        self.canvas.mpl_connect('scroll_event', self._on_scroll)

    # ── 框選放大 ──
    def toggle_zoom_mode(self):
        self._zoom_mode = not self._zoom_mode
        if self._zoom_mode:
            self.zoom_btn.config(bg=Style.PRIMARY, fg='white', text='框選放大 [啟動]')
            self._activate_rect()
        else:
            self.zoom_btn.config(bg='#e8f0fe', fg=Style.PRIMARY, text='框選放大')
            self._deactivate_rect()

    def _activate_rect(self):
        ax = self._get_ax()
        if ax is None:
            return
        self._rect_selector = RectangleSelector(
            ax, self._on_rect_select,
            useblit=True, button=[1],
            minspanx=0.5, minspany=0.5,
            spancoords='data', interactive=False,
            props=dict(facecolor='none', edgecolor='red',
                       linewidth=1.5, linestyle='--')
        )

    def _deactivate_rect(self):
        if self._rect_selector is not None:
            self._rect_selector.set_active(False)
            self._rect_selector = None

    def _on_rect_select(self, eclick, erelease):
        ax = self._get_ax()
        if ax is None:
            return
        x0, x1 = sorted([eclick.xdata, erelease.xdata])
        y0, y1 = sorted([eclick.ydata, erelease.ydata])
        if (x1 - x0) > 0.1 and (y1 - y0) > 0.1:
            try:
                ax.set_extent([x0, x1, y0, y1], crs=ccrs.PlateCarree())
                self.canvas.draw_idle()
            except Exception:
                pass
        self.toggle_zoom_mode()

    # ── 滾輪縮放（Cartopy 正確 API）──
    def _on_scroll(self, event):
        ax = self._get_ax()
        if ax is None or event.inaxes is None:
            return
        if event.xdata is None or event.ydata is None:
            return
        try:
            x_min, x_max, y_min, y_max = ax.get_extent(crs=ccrs.PlateCarree())
        except Exception:
            return
        scale = 0.80 if event.button == 'up' else 1.25
        cx, cy = event.xdata, event.ydata
        dx = (x_max - x_min) * scale / 2
        dy = (y_max - y_min) * scale / 2
        try:
            ax.set_extent([cx - dx, cx + dx, cy - dy, cy + dy],
                          crs=ccrs.PlateCarree())
            self.canvas.draw_idle()
        except Exception:
            pass

    # ── 懸停顯示 ──
    def _on_hover(self, event):
        if event.inaxes is None or event.xdata is None:
            self.app.status_bar.set_coordinates()
            return
        lon, lat = event.xdata, event.ydata
        value = self._get_value(lon, lat)
        self.app.status_bar.set_coordinates(lon, lat, value)

    def _get_value(self, lon, lat):
        for data, keys in [
            (self.current_data,
             ['sst', 'temp_50m', 'temp_100m', 'temp_200m', 'temp_400m', 'probability']),
            (self.current_sst_data, ['sst']),
        ]:
            if data is None:
                continue
            for k in keys:
                if k in data and data[k] is not None:
                    arr  = data[k]
                    lats = data['lats']
                    lons = data['lons']
                    li = int(np.argmin(np.abs(lats - lat)))
                    lj = int(np.argmin(np.abs(lons - lon)))
                    if 0 <= li < arr.shape[0] and 0 <= lj < arr.shape[1]:
                        v = arr[li, lj]
                        return float(v) if not np.isnan(v) else None
        return None

    def _get_ax(self):
        for ax in self.figure.get_axes():
            if hasattr(ax, 'set_extent'):
                return ax
        return None

    def set_current_data(self, data, sst_data=None):
        self.current_data     = data
        self.current_sst_data = sst_data

    def refresh_rect_selector(self):
        if self._zoom_mode:
            self._deactivate_rect()
            self._activate_rect()


# ============================================================
# 主應用程式
# ============================================================
class JMAWeatherGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(f'{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}')
        self.root.minsize(1200, 800)

        self.data_manager      = None
        self.visualizer        = None
        self.ecdf_analyzer     = None
        self.habitat_predictor = None

        self._apply_theme()
        self._build_ui()

        # 主視窗完全顯示後才啟動背景初始化
        self.root.after(300, self._start_init)

    # ── 主題 ──
    def _apply_theme(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('TFrame',         background=Style.BG_MAIN)
        s.configure('TLabel',         background=Style.BG_MAIN,
                    foreground=Style.TEXT_PRIMARY,
                    font=(Style.FONT, Style.SZ_NORMAL))
        s.configure('TLabelframe',    background=Style.BG_PANEL,
                    font=(Style.FONT, Style.SZ_NORMAL, 'bold'))
        s.configure('TLabelframe.Label',
                    background=Style.BG_PANEL,
                    foreground=Style.PRIMARY,
                    font=(Style.FONT, Style.SZ_NORMAL, 'bold'))
        s.configure('TButton',        font=(Style.FONT, Style.SZ_NORMAL), padding=6)
        s.map('TButton',
              background=[('active', Style.PRIMARY_LIGHT)],
              foreground=[('active', Style.TEXT_LIGHT)])
        s.configure('TCheckbutton',   background=Style.BG_PANEL,
                    font=(Style.FONT, Style.SZ_NORMAL))
        s.configure('TRadiobutton',   background=Style.BG_PANEL,
                    font=(Style.FONT, Style.SZ_NORMAL))

    # ── UI 佈局 ──
    def _build_ui(self):
        # 頂部標題列
        header = tk.Frame(self.root, bg=Style.BG_DARK, height=44)
        header.pack(side='top', fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f'  {config.WINDOW_TITLE}',
                 bg=Style.BG_DARK, fg='white',
                 font=(Style.FONT, 13, 'bold')).pack(side='left', padx=10)
        tk.Label(header, text=config.ORGANIZATION_LABEL,
                 bg=Style.BG_DARK, fg='#90caf9',
                 font=(Style.FONT, Style.SZ_NORMAL)).pack(side='right', padx=16)

        # 主內容
        main = ttk.Frame(self.root)
        main.pack(fill='both', expand=True, padx=4, pady=4)

        paned = ttk.PanedWindow(main, orient='horizontal')
        paned.pack(fill='both', expand=True)

        left = tk.Frame(paned, width=268, bg=Style.BG_PANEL)
        self.control_panel = ControlPanel(left, self)
        self.control_panel.pack(fill='both', expand=True)
        paned.add(left, weight=0)

        right = ttk.Frame(paned)
        self.map_canvas = MapCanvas(right, self)
        self.map_canvas.pack(fill='both', expand=True)
        paned.add(right, weight=1)

        # 狀態列
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side='bottom', fill='x')

    # ── 背景初始化（分三階段，主視窗不被阻塞）──
    def _start_init(self):
        """
        第一階段：先載入已有的本地資料並立刻顯示地圖，
        第二階段：再於背景下載最新資料。
        """
        self.status_bar.set_status('載入本地資料中...', busy=True)

        def phase1():
            try:
                from data_parser import DataManager
                from visualizer import OceanVisualizer
                from ecdf_analyzer import SauryECDFAnalyzer, HabitatPredictor

                self.data_manager = DataManager()
                self.data_manager.load_himsst_files()
                self.data_manager.load_nprsubt_files()
                self.data_manager.load_nprsubc_files()

                self.visualizer = OceanVisualizer(
                    self.map_canvas.figure, self.map_canvas.canvas)

                self.ecdf_analyzer = SauryECDFAnalyzer()
                if self.ecdf_analyzer.load_data():
                    self.ecdf_analyzer.analyze_sst()
                    self.ecdf_analyzer.analyze_100m_temp()
                    summary = self.ecdf_analyzer.get_summary()
                    self.root.after(0, lambda s=summary:
                                    self.control_panel.update_ecdf_info(s))
                    self.habitat_predictor = HabitatPredictor(self.ecdf_analyzer)

                # 本地資料就緒 → 立刻更新 UI
                self.root.after(0, self._on_local_loaded)

                # 第二階段：背景下載新資料
                self.root.after(0, self._download_new_data)

            except Exception as e:
                self.root.after(0, lambda err=str(e):
                                self.status_bar.set_status(f'載入失敗: {err}'))

        Thread(target=phase1, daemon=True).start()

    def _on_local_loaded(self):
        self.status_bar.set_status('本地資料已就緒，正在下載最新資料...', busy=True)
        self.update_date_list()
        self.redraw()

    def _download_new_data(self):
        def phase2():
            try:
                from data_downloader import JMADataDownloader
                dl = JMADataDownloader()

                for dtype, label in [
                    ('himsst',  'HIMSST'),
                    ('nprsubt', 'NPRSUBT'),
                    ('nprsubc', 'NPRSUBC'),
                ]:
                    self.root.after(0, lambda l=label:
                                    self.status_bar.set_status(
                                        f'下載 {l} 最新資料...', busy=True))
                    if dtype == 'himsst':
                        dl.download_himsst(count=config.DOWNLOAD_COUNT)
                    elif dtype == 'nprsubt':
                        dl.download_nprsubt(count=config.DOWNLOAD_COUNT)
                    elif dtype == 'nprsubc':
                        dl.download_nprsubc(count=config.DOWNLOAD_COUNT)

                # 下載完成後重新載入並刷新
                self.root.after(0, self._reload_after_download)

            except Exception as e:
                self.root.after(0, lambda err=str(e):
                                self.status_bar.set_status(f'下載警告: {err}'))

        Thread(target=phase2, daemon=True).start()

    def _reload_after_download(self):
        def reload():
            try:
                self.data_manager.load_himsst_files()
                self.data_manager.load_nprsubt_files()
                self.data_manager.load_nprsubc_files()
                self.root.after(0, self._on_reload_done)
            except Exception as e:
                self.root.after(0, lambda err=str(e):
                                self.status_bar.set_status(f'重載失敗: {err}'))

        Thread(target=reload, daemon=True).start()

    def _on_reload_done(self):
        self.status_bar.set_status('資料更新完成', busy=False)
        self.update_date_list()

    # ── 更新日期列表 ──
    def update_date_list(self):
        if self.data_manager is None:
            return
        dt    = self.control_panel.data_type_var.get()
        avail = self.data_manager.get_available_dates()

        if dt == 'sst':
            dates = sorted(avail.get('himsst', []), reverse=True)
        elif dt == 'subtemp':
            dates = sorted(avail.get('nprsubt', []), reverse=True)
        elif dt == 'combined':
            dates = sorted(
                set(avail.get('himsst', [])) &
                set(avail.get('nprsubt', [])) &
                set(avail.get('nprsubc', [])),
                reverse=True
            )
        elif dt == 'habitat':
            dates = sorted(
                set(avail.get('himsst', [])) &
                set(avail.get('nprsubt', [])),
                reverse=True
            )
        else:
            dates = []

        combo = self.control_panel.date_combo
        combo['values'] = dates
        if dates and combo.get() not in dates:
            combo.set(dates[0])

    # ── 重新繪製 ──
    def redraw(self):
        if self.visualizer is None or self.data_manager is None:
            return
        cfg  = self.control_panel.get_settings()
        date = cfg['date']
        if not date:
            self.status_bar.set_status('請選擇日期')
            return

        self.visualizer.clear()
        self.visualizer.setup_map()
        dt = cfg['data_type']

        try:
            if dt == 'sst':
                data = self.data_manager.get_himsst(date)
                if data:
                    self.visualizer.plot_sst(
                        data,
                        show_isotherms=cfg['show_isotherms'],
                        isotherm_interval=cfg['isotherm_interval'],
                        show_values=cfg['show_values'])
                    self.map_canvas.set_current_data(data)
                    self.status_bar.set_status(f'{date} 海面水溫圖')
                else:
                    self.status_bar.set_status(f'找不到 {date} SST 資料')

            elif dt == 'subtemp':
                data = self.data_manager.get_nprsubt(date)
                if data:
                    self.visualizer.plot_subtemp(
                        data, depth=cfg['depth'],
                        show_isotherms=cfg['show_isotherms'],
                        isotherm_interval=cfg['isotherm_interval'],
                        show_values=cfg['show_values'])
                    hd = dict(data)
                    hd['sst'] = data.get(f"temp_{cfg['depth']}")
                    self.map_canvas.set_current_data(hd)
                    self.status_bar.set_status(f'{date} {cfg["depth"]} 次表層水溫圖')
                else:
                    self.status_bar.set_status(f'找不到 {date} 次表層水溫資料')

            elif dt == 'combined':
                sst  = self.data_manager.get_himsst(date)
                subt = self.data_manager.get_nprsubt(date)
                subc = self.data_manager.get_nprsubc(date)
                if sst:
                    self.visualizer.plot_combined(
                        sst,
                        nprsubt_data=subt if cfg['show_isotherms'] else None,
                        nprsubc_data=subc if cfg['show_currents'] else None,
                        subtemp_depth=cfg['depth'],
                        show_isotherms=cfg['show_isotherms'],
                        show_currents=cfg['show_currents'])
                    self.map_canvas.set_current_data(sst)
                    self.status_bar.set_status(f'{date} 組合圖')
                else:
                    self.status_bar.set_status(f'找不到 {date} 資料')

            elif dt == 'habitat':
                if self.habitat_predictor is None:
                    self.status_bar.set_status('ECDF 分析器未就緒')
                    return
                sst  = self.data_manager.get_himsst(date)
                subt = self.data_manager.get_nprsubt(date)
                if sst and subt:
                    prob = self.habitat_predictor.predict(sst, subt)
                    if prob:
                        self.visualizer.plot_habitat_probability(
                            prob,
                            overlay_sst=cfg['show_isotherms'],
                            sst_data=sst)
                        self.map_canvas.set_current_data(prob, sst)
                        self.status_bar.set_status(f'{date} 秋刀魚棲息地預測圖')
                    else:
                        self.status_bar.set_status('棲息地預測運算失敗')
                else:
                    self.status_bar.set_status(f'找不到 {date} 完整資料')

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.set_status(f'繪圖錯誤: {e}')

        self.map_canvas.refresh_rect_selector()

    # ── 重置視野 ──
    def reset_view(self):
        ax = self.map_canvas._get_ax()
        if ax is not None:
            try:
                ax.set_extent(
                    [config.VIEW_LON_MIN, config.VIEW_LON_MAX,
                     config.VIEW_LAT_MIN, config.VIEW_LAT_MAX],
                    crs=ccrs.PlateCarree())
                self.map_canvas.canvas.draw_idle()
                self.status_bar.set_status('視野已重置')
            except Exception as e:
                self.status_bar.set_status(f'重置失敗: {e}')

    # ── ECDF 圖表 ──
    def show_ecdf_chart(self):
        if self.ecdf_analyzer is None or not self.ecdf_analyzer.ecdf_results:
            messagebox.showinfo('提示', 'ECDF 分析尚未完成，請稍後再試。')
            return
        ECDFChartWindow(self.root, self.ecdf_analyzer)

    # ── 儲存圖片 ──
    def save_figure(self):
        fn = filedialog.asksaveasfilename(
            defaultextension='.png',
            filetypes=[('PNG', '*.png'), ('PDF', '*.pdf'), ('SVG', '*.svg')],
            title='儲存地圖圖片')
        if fn:
            try:
                self.map_canvas.figure.savefig(
                    fn, dpi=180, bbox_inches='tight', facecolor='white')
                self.status_bar.set_status(f'已儲存: {fn}')
            except Exception as e:
                messagebox.showerror('儲存失敗', str(e))

    # ── 手動重新下載 ──
    def re_download(self):
        if messagebox.askyesno('重新下載',
                               '確定要重新下載最新 JMA 海洋資料？'):
            self._download_new_data()

    def run(self):
        self.root.mainloop()


# ============================================================
# 主程式進入點
# ============================================================
def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = JMAWeatherGUI(root)
    app.run()


if __name__ == '__main__':
    main()
