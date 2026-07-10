# -*- coding: utf-8 -*-
"""
JMA海洋氣象資料桌面GUI系統 - 視覺化模組
Visualization Module for JMA Ocean Weather Desktop GUI System
"""

import numpy as np
import matplotlib
# Backend must be set before importing pyplot; use the value already set by main_gui
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import LinearSegmentedColormap, Normalize, BoundaryNorm
import matplotlib.patheffects as pe
from mpl_toolkits.axes_grid1 import make_axes_locatable
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
from typing import Dict, Optional, Tuple, List
import config

# 設定中文字型
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class OceanVisualizer:
    """
    海洋資料視覺化器
    
    負責繪製海面水溫、次表層水溫、表面海流及秋刀魚棲息地分布圖
    """
    
    def __init__(self, figure: Figure = None, canvas = None):
        self.figure = figure
        self.canvas = canvas
        self.ax = None
        self.colorbar = None
        self.contour_lines = None
        self.current_quiver = None
        
        # 高解析度海岸線和陸地特徵
        self.land_feature = cfeature.NaturalEarthFeature(
            'physical', 'land', '50m',
            edgecolor='#333333',
            facecolor='#e8e8e8'
        )
        
        self.coastline_feature = cfeature.NaturalEarthFeature(
            'physical', 'coastline', '50m',
            edgecolor='#333333',
            facecolor='none'
        )
        
        # 建立自訂色彩映射
        self._create_colormaps()
    
    def _create_colormaps(self):
        """建立自訂色彩映射"""
        # SST色彩映射 - 從深藍到紅色
        sst_colors = [
            '#000080',  # 深藍
            '#0000ff',  # 藍
            '#00bfff',  # 淺藍
            '#00ff80',  # 青綠
            '#80ff00',  # 黃綠
            '#ffff00',  # 黃
            '#ff8000',  # 橙
            '#ff0000',  # 紅
            '#800000'   # 深紅
        ]
        self.sst_cmap = LinearSegmentedColormap.from_list('sst', sst_colors, N=256)
        
        # 棲息地機率色彩映射 - 從灰到綠
        habitat_colors = [
            '#808080',  # 灰色（低機率）
            '#ffff00',  # 黃色
            '#80ff00',  # 黃綠
            '#00ff00',  # 亮綠
            '#008800'   # 深綠（高機率）
        ]
        self.habitat_cmap = LinearSegmentedColormap.from_list('habitat', habitat_colors, N=256)
    
    def setup_map(self, extent: Tuple[float, float, float, float] = None):
        """
        設置地圖
        
        Args:
            extent: (lon_min, lon_max, lat_min, lat_max)
        """
        if self.figure is None:
            return
        
        self.figure.clear()
        
        # 建立地圖投影
        self.ax = self.figure.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        
        # 設定顯示範圍
        if extent is None:
            extent = (config.VIEW_LON_MIN, config.VIEW_LON_MAX,
                      config.VIEW_LAT_MIN, config.VIEW_LAT_MAX)
        
        self.ax.set_extent(extent, crs=ccrs.PlateCarree())
        
        # 添加地圖特徵
        self.ax.add_feature(self.land_feature, zorder=5)
        self.ax.add_feature(self.coastline_feature, linewidth=0.8, zorder=6)
        
        # 添加格線
        gl = self.ax.gridlines(
            draw_labels=True,
            linewidth=0.5,
            color='gray',
            alpha=0.5,
            linestyle='--'
        )
        gl.top_labels = False
        gl.right_labels = False
        gl.xformatter = LONGITUDE_FORMATTER
        gl.yformatter = LATITUDE_FORMATTER
        gl.xlabel_style = {'size': 9, 'color': '#333333'}
        gl.ylabel_style = {'size': 9, 'color': '#333333'}
        
        # 設定背景色
        self.ax.set_facecolor('#cce5ff')
        
        return self.ax
    
    def plot_sst(self, data: Dict, show_isotherms: bool = False,
                 isotherm_interval: int = 2, isotherm_levels: List[float] = None,
                 show_values: bool = False) -> bool:
        """
        繪製海面水溫分布圖
        
        Args:
            data: HIMSST資料字典
            show_isotherms: 是否顯示等溫線
            isotherm_interval: 等溫線間隔
            isotherm_levels: 自訂等溫線位置
            show_values: 是否在等溫線上顯示數值
            
        Returns:
            是否成功繪製
        """
        if data is None or self.ax is None:
            return False
        
        sst = data['sst']
        lons = data['lons']
        lats = data['lats']
        date = data.get('date')
        
        # 繪製SST填色圖
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        pcm = self.ax.pcolormesh(
            lon_grid, lat_grid, sst,
            cmap=self.sst_cmap,
            vmin=config.SST_VMIN,
            vmax=config.SST_VMAX,
            transform=ccrs.PlateCarree(),
            shading='auto',
            zorder=1
        )
        
        # 添加色彩條
        self._add_colorbar(pcm, label='海面水溫 SST (°C)')
        
        # 繪製等溫線
        if show_isotherms:
            if isotherm_levels is None:
                isotherm_levels = np.arange(
                    config.SST_VMIN, 
                    config.SST_VMAX + 1, 
                    isotherm_interval
                )
            
            self.contour_lines = self.ax.contour(
                lon_grid, lat_grid, sst,
                levels=isotherm_levels,
                colors='black',
                linewidths=0.8,
                transform=ccrs.PlateCarree(),
                zorder=3
            )
            
            if show_values:
                labels = self.ax.clabel(
                    self.contour_lines,
                    inline=True,
                    fontsize=8,
                    fmt='%.0f'
                )
                for label in labels:
                    label.set_path_effects([
                        pe.withStroke(linewidth=2, foreground='white')
                    ])
        
        # 設定標題
        title = '海面水溫 (HIMSST) 分布圖'
        if date:
            title += f' - {date.strftime("%Y/%m/%d")}'
        self.ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
        
        # 添加機構標示
        self._add_watermark()
        
        if self.canvas:
            self.canvas.draw()
        
        return True
    
    def plot_subtemp(self, data: Dict, depth: str = '100m',
                     show_isotherms: bool = False, isotherm_interval: int = 2,
                     show_values: bool = False) -> bool:
        """
        繪製次表層水溫分布圖
        
        Args:
            data: NPRSUBT資料字典
            depth: 深度（'50m', '100m', '200m', '400m'）
            show_isotherms: 是否顯示等溫線
            isotherm_interval: 等溫線間隔
            show_values: 是否顯示等溫線數值
            
        Returns:
            是否成功繪製
        """
        if data is None or self.ax is None:
            return False
        
        depth_key = f'temp_{depth}'
        if depth_key not in data:
            print(f"找不到深度資料: {depth_key}")
            return False
        
        temp = data[depth_key]
        lons = data['lons']
        lats = data['lats']
        date = data.get('date')
        
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        # 繪製水溫填色圖
        pcm = self.ax.pcolormesh(
            lon_grid, lat_grid, temp,
            cmap=self.sst_cmap,
            vmin=config.SUBTEMP_VMIN,
            vmax=config.SUBTEMP_VMAX,
            transform=ccrs.PlateCarree(),
            shading='auto',
            zorder=1
        )
        
        self._add_colorbar(pcm, label=f'{depth}水溫 (°C)')
        
        # 繪製等溫線
        if show_isotherms:
            levels = np.arange(config.SUBTEMP_VMIN, config.SUBTEMP_VMAX + 1, isotherm_interval)
            
            self.contour_lines = self.ax.contour(
                lon_grid, lat_grid, temp,
                levels=levels,
                colors='black',
                linewidths=0.8,
                transform=ccrs.PlateCarree(),
                zorder=3
            )
            
            if show_values:
                labels = self.ax.clabel(
                    self.contour_lines,
                    inline=True,
                    fontsize=8,
                    fmt='%.0f'
                )
                for label in labels:
                    label.set_path_effects([
                        pe.withStroke(linewidth=2, foreground='white')
                    ])
        
        # 設定標題
        title = f'{depth}次表層水溫 (NPRSUBT) 分布圖'
        if date:
            title += f' - {date.strftime("%Y/%m/%d")}'
        self.ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
        
        self._add_watermark()
        
        if self.canvas:
            self.canvas.draw()
        
        return True
    
    def overlay_currents(self, data: Dict, skip: int = None) -> bool:
        """
        疊加表面海流向量圖
        
        Args:
            data: NPRSUBC資料字典
            skip: 向量箭頭間隔
            
        Returns:
            是否成功繪製
        """
        if data is None or self.ax is None:
            return False
        
        u = data['u']
        v = data['v']
        lons = data['lons']
        lats = data['lats']
        
        if skip is None:
            skip = config.CURRENT_ARROW_SKIP
        
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        # 縮減箭頭密度
        lon_skip = lon_grid[::skip, ::skip]
        lat_skip = lat_grid[::skip, ::skip]
        u_skip = u[::skip, ::skip]
        v_skip = v[::skip, ::skip]
        
        # 計算流速用於著色
        speed_skip = np.sqrt(u_skip**2 + v_skip**2)
        
        # 繪製向量箭頭
        self.current_quiver = self.ax.quiver(
            lon_skip, lat_skip, u_skip, v_skip,
            speed_skip,
            cmap='plasma',
            scale=5,
            width=0.003,
            headwidth=3,
            headlength=4,
            transform=ccrs.PlateCarree(),
            zorder=4,
            alpha=0.8
        )
        
        # 添加圖例
        self.ax.quiverkey(
            self.current_quiver, 0.9, 0.02, 0.5,
            '0.5 m/s', labelpos='E',
            coordinates='axes',
            fontproperties={'size': 9}
        )
        
        if self.canvas:
            self.canvas.draw()
        
        return True
    
    def plot_habitat_probability(self, prob_data: Dict,
                                 overlay_sst: bool = True,
                                 sst_data: Dict = None) -> bool:
        """
        繪製秋刀魚棲息地機率分布圖
        
        Args:
            prob_data: 棲息機率資料字典
            overlay_sst: 是否疊加SST等溫線
            sst_data: SST資料（用於疊加等溫線）
            
        Returns:
            是否成功繪製
        """
        if prob_data is None or self.ax is None:
            return False
        
        probability = prob_data['probability']
        lons = prob_data['lons']
        lats = prob_data['lats']
        
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        # 繪製機率填色圖
        # 使用離散色階表示不同機率等級
        levels = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        colors = ['#cccccc', '#ffff00', '#80ff00', '#00cc00', '#006600']
        cmap = LinearSegmentedColormap.from_list('habitat', colors, N=len(colors))
        norm = BoundaryNorm(levels, cmap.N)
        
        pcm = self.ax.pcolormesh(
            lon_grid, lat_grid, probability,
            cmap=cmap,
            norm=norm,
            transform=ccrs.PlateCarree(),
            shading='auto',
            zorder=1,
            alpha=0.85
        )
        
        self._add_colorbar(pcm, label='棲息機率')
        
        # 疊加SST等溫線
        if overlay_sst and sst_data is not None:
            sst = sst_data['sst']
            sst_lons = sst_data['lons']
            sst_lats = sst_data['lats']
            sst_lon_grid, sst_lat_grid = np.meshgrid(sst_lons, sst_lats)
            
            contours = self.ax.contour(
                sst_lon_grid, sst_lat_grid, sst,
                levels=np.arange(10, 25, 2),
                colors='white',
                linewidths=0.8,
                transform=ccrs.PlateCarree(),
                zorder=3
            )
            self.ax.clabel(contours, inline=True, fontsize=8, fmt='%.0f')
        
        # 設定標題
        title = '秋刀魚潛在棲息海域預測圖'
        sst_date = prob_data.get('sst_date')
        if sst_date:
            title += f' - {sst_date.strftime("%Y/%m/%d")}'
        self.ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
        
        self._add_watermark()
        
        if self.canvas:
            self.canvas.draw()
        
        return True
    
    def plot_combined(self, sst_data: Dict, nprsubt_data: Dict = None,
                      nprsubc_data: Dict = None, subtemp_depth: str = '100m',
                      show_isotherms: bool = True, 
                      show_currents: bool = True) -> bool:
        """
        繪製組合圖（SST + 次表層等溫線 + 海流）
        
        Args:
            sst_data: HIMSST資料
            nprsubt_data: NPRSUBT資料
            nprsubc_data: NPRSUBC資料
            subtemp_depth: 次表層深度
            show_isotherms: 是否顯示等溫線
            show_currents: 是否顯示海流
        """
        if sst_data is None or self.ax is None:
            return False
        
        # 繪製SST底圖
        sst = sst_data['sst']
        lons = sst_data['lons']
        lats = sst_data['lats']
        
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        pcm = self.ax.pcolormesh(
            lon_grid, lat_grid, sst,
            cmap=self.sst_cmap,
            vmin=config.SST_VMIN,
            vmax=config.SST_VMAX,
            transform=ccrs.PlateCarree(),
            shading='auto',
            zorder=1
        )
        
        self._add_colorbar(pcm, label='海面水溫 (°C)')
        
        # 疊加次表層等溫線
        if show_isotherms and nprsubt_data is not None:
            depth_key = f'temp_{subtemp_depth}'
            if depth_key in nprsubt_data:
                temp = nprsubt_data[depth_key]
                sub_lons = nprsubt_data['lons']
                sub_lats = nprsubt_data['lats']
                sub_lon_grid, sub_lat_grid = np.meshgrid(sub_lons, sub_lats)
                
                contours = self.ax.contour(
                    sub_lon_grid, sub_lat_grid, temp,
                    levels=np.arange(2, 20, 2),
                    colors='white',
                    linewidths=1.0,
                    linestyles='dashed',
                    transform=ccrs.PlateCarree(),
                    zorder=3
                )
                labels = self.ax.clabel(contours, inline=True, fontsize=8, fmt='%.0f')
                for label in labels:
                    label.set_path_effects([
                        pe.withStroke(linewidth=2, foreground='black')
                    ])
        
        # 疊加海流
        if show_currents and nprsubc_data is not None:
            self.overlay_currents(nprsubc_data)
        
        # 設定標題
        title = 'SST'
        if show_isotherms and nprsubt_data is not None:
            title += f' + {subtemp_depth}等溫線'
        if show_currents and nprsubc_data is not None:
            title += ' + 表面海流'
        
        date = sst_data.get('date')
        if date:
            title += f' - {date.strftime("%Y/%m/%d")}'
        
        self.ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
        
        self._add_watermark()
        
        if self.canvas:
            self.canvas.draw()
        
        return True
    
    def _add_colorbar(self, mappable, label: str = ''):
        """添加色彩條"""
        if self.colorbar is not None:
            self.colorbar.remove()
        
        # 使用axes_grid1的make_axes_locatable來創建色彩條
        self.colorbar = self.figure.colorbar(
            mappable, ax=self.ax,
            orientation='vertical',
            shrink=0.8,
            pad=0.02,
            aspect=30
        )
        self.colorbar.set_label(label, fontsize=10)
        self.colorbar.ax.tick_params(labelsize=9)
    
    def _add_watermark(self):
        """添加機構標示（右上角，高對比度）"""
        self.ax.text(
            0.99, 0.99,
            config.ORGANIZATION_LABEL,
            transform=self.ax.transAxes,
            fontsize=10,
            fontweight='bold',
            color='#1a237e',
            alpha=0.95,
            ha='right', va='top',
            bbox=dict(
                boxstyle='round,pad=0.4',
                facecolor='white',
                edgecolor='#3f51b5',
                linewidth=1.2,
                alpha=0.90
            ),
            zorder=100
        )
    
    def clear(self):
        """清除畫布"""
        if self.figure:
            self.figure.clear()
            self.ax = None
            self.colorbar = None
            self.contour_lines = None
            self.current_quiver = None
            
            if self.canvas:
                self.canvas.draw()
    
    def get_extent(self) -> Optional[Tuple[float, float, float, float]]:
        """獲取當前顯示範圍"""
        if self.ax is not None:
            return self.ax.get_extent(crs=ccrs.PlateCarree())
        return None
    
    def set_extent(self, extent: Tuple[float, float, float, float]):
        """設定顯示範圍"""
        if self.ax is not None:
            self.ax.set_extent(extent, crs=ccrs.PlateCarree())
            if self.canvas:
                self.canvas.draw()
