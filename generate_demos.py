# -*- coding: utf-8 -*-
"""
生成展示圖片的測試腳本
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from data_parser import DataManager
from visualizer import OceanVisualizer
from ecdf_analyzer import SauryECDFAnalyzer, HabitatPredictor

# 設定中文字型
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 載入資料
print("載入資料中...")
manager = DataManager()
manager.load_himsst_files()
manager.load_nprsubt_files()
manager.load_nprsubc_files()

print(f"HIMSST日期: {list(manager.himsst_cache.keys())}")
print(f"NPRSUBT日期: {list(manager.nprsubt_cache.keys())}")
print(f"NPRSUBC日期: {list(manager.nprsubc_cache.keys())}")

# 取得最新日期
date = list(manager.himsst_cache.keys())[0]
print(f"\n使用日期: {date}")

# 1. 生成SST圖
print("\n1. 生成海面水溫圖...")
fig = Figure(figsize=(14, 10), dpi=100, facecolor='white')
vis = OceanVisualizer(fig)
vis.setup_map()
sst_data = manager.get_himsst(date)
vis.plot_sst(sst_data, show_isotherms=True, isotherm_interval=2, show_values=True)
fig.savefig('demo_sst.png', dpi=150, bbox_inches='tight', facecolor='white')
print("已儲存: demo_sst.png")

# 2. 生成100m次表層水溫圖
print("\n2. 生成100m次表層水溫圖...")
fig2 = Figure(figsize=(14, 10), dpi=100, facecolor='white')
vis2 = OceanVisualizer(fig2)
vis2.setup_map()
nprsubt_data = manager.get_nprsubt(date)
if nprsubt_data:
    vis2.plot_subtemp(nprsubt_data, depth='100m', show_isotherms=True, isotherm_interval=2, show_values=True)
    fig2.savefig('demo_100m.png', dpi=150, bbox_inches='tight', facecolor='white')
    print("已儲存: demo_100m.png")

# 3. 生成組合圖（SST + 次表層等溫線 + 海流）
print("\n3. 生成組合圖...")
fig3 = Figure(figsize=(14, 10), dpi=100, facecolor='white')
vis3 = OceanVisualizer(fig3)
vis3.setup_map()
nprsubc_data = manager.get_nprsubc(date)
vis3.plot_combined(sst_data, nprsubt_data, nprsubc_data, subtemp_depth='100m', 
                   show_isotherms=True, show_currents=True)
fig3.savefig('demo_combined.png', dpi=150, bbox_inches='tight', facecolor='white')
print("已儲存: demo_combined.png")

# 4. 生成秋刀魚棲息地預測圖
print("\n4. 生成秋刀魚棲息地預測圖...")
analyzer = SauryECDFAnalyzer()
if analyzer.load_data():
    analyzer.analyze_sst()
    analyzer.analyze_100m_temp()
    
    predictor = HabitatPredictor(analyzer)
    prob_data = predictor.predict(sst_data, nprsubt_data)
    
    if prob_data:
        fig4 = Figure(figsize=(14, 10), dpi=100, facecolor='white')
        vis4 = OceanVisualizer(fig4)
        vis4.setup_map()
        vis4.plot_habitat_probability(prob_data, overlay_sst=True, sst_data=sst_data)
        fig4.savefig('demo_habitat.png', dpi=150, bbox_inches='tight', facecolor='white')
        print("已儲存: demo_habitat.png")
    
    # 顯示ECDF分析摘要
    summary = analyzer.get_summary()
    print("\n" + "="*50)
    print("ECDF分析摘要:")
    print("="*50)
    for key, value in summary.items():
        print(f"  {key}: {value}")

print("\n所有展示圖片已生成完成！")
