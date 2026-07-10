# -*- coding: utf-8 -*-
"""
JMA海洋氣象資料桌面GUI系統 - 秋刀魚棲息地ECDF分析模組
Saury Habitat ECDF Analysis Module
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import config


class SauryECDFAnalyzer:
    """
    秋刀魚棲息地經驗累積分布函數（ECDF）分析器
    
    使用Saury-csv.txt資料，分析秋刀魚最適棲息海域的海洋環境參數範圍，
    並預測可能的秋刀魚分布海域。
    """
    
    def __init__(self):
        self.data: Optional[pd.DataFrame] = None
        self.ecdf_results: Dict = {}
        self.optimal_ranges: Dict = {}
        
    def load_data(self, filepath: Path = None) -> bool:
        """
        載入秋刀魚資料檔案
        
        Args:
            filepath: 資料檔案路徑，預設使用config中的設定
            
        Returns:
            是否成功載入
        """
        if filepath is None:
            filepath = config.SAURY_DATA_FILE
            
        try:
            # 讀取Tab分隔的資料檔案
            self.data = pd.read_csv(filepath, sep='\t', encoding='utf-16-le')
            
            # 清理欄位名稱
            self.data.columns = self.data.columns.str.strip()
            
            # 確保必要的欄位存在
            required_cols = ['SST', '100mT', 'CPUE', 'Lat', 'Long']
            missing_cols = [col for col in required_cols if col not in self.data.columns]
            if missing_cols:
                print(f"缺少必要欄位: {missing_cols}")
                print(f"可用欄位: {list(self.data.columns)}")
                return False
            
            # 移除無效資料
            self.data = self.data.dropna(subset=['SST', '100mT', 'CPUE'])
            
            print(f"成功載入 {len(self.data)} 筆秋刀魚漁獲資料")
            return True
            
        except Exception as e:
            print(f"載入資料失敗: {e}")
            return False
    
    def compute_ecdf(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        計算經驗累積分布函數（ECDF）
        
        Args:
            data: 一維數據陣列
            
        Returns:
            (排序後的數據值, 累積機率)
        """
        data = np.array(data)
        data = data[~np.isnan(data)]
        n = len(data)
        
        sorted_data = np.sort(data)
        cumulative_prob = np.arange(1, n + 1) / n
        
        return sorted_data, cumulative_prob
    
    def analyze_sst(self) -> Dict:
        """
        分析海面水溫（SST）與秋刀魚漁獲的ECDF關係
        
        Returns:
            分析結果字典
        """
        if self.data is None:
            return {}
        
        # 過濾有漁獲的記錄（CPUE > 0）
        catch_data = self.data[self.data['CPUE'] > 0]['SST'].values
        
        sorted_vals, cdf = self.compute_ecdf(catch_data)
        
        # 計算各百分位數對應的溫度值
        percentile_values = {}
        for name, percentile in config.ECDF_PERCENTILES.items():
            idx = np.searchsorted(cdf, percentile)
            if idx >= len(sorted_vals):
                idx = len(sorted_vals) - 1
            percentile_values[name] = sorted_vals[idx]
        
        result = {
            'sorted_values': sorted_vals,
            'cdf': cdf,
            'percentiles': percentile_values,
            'min': np.min(catch_data),
            'max': np.max(catch_data),
            'mean': np.mean(catch_data),
            'std': np.std(catch_data)
        }
        
        self.ecdf_results['sst'] = result
        return result
    
    def analyze_100m_temp(self) -> Dict:
        """
        分析100m次表層水溫（100mT）與秋刀魚漁獲的ECDF關係
        
        Returns:
            分析結果字典
        """
        if self.data is None:
            return {}
        
        # 過濾有漁獲的記錄
        catch_data = self.data[self.data['CPUE'] > 0]['100mT'].values
        
        sorted_vals, cdf = self.compute_ecdf(catch_data)
        
        # 計算各百分位數對應的溫度值
        percentile_values = {}
        for name, percentile in config.ECDF_PERCENTILES.items():
            idx = np.searchsorted(cdf, percentile)
            if idx >= len(sorted_vals):
                idx = len(sorted_vals) - 1
            percentile_values[name] = sorted_vals[idx]
        
        result = {
            'sorted_values': sorted_vals,
            'cdf': cdf,
            'percentiles': percentile_values,
            'min': np.min(catch_data),
            'max': np.max(catch_data),
            'mean': np.mean(catch_data),
            'std': np.std(catch_data)
        }
        
        self.ecdf_results['100m_temp'] = result
        return result
    
    def get_optimal_ranges(self) -> Dict:
        """
        獲取秋刀魚最適漁獲的環境參數範圍
        
        基於ECDF分析，定義不同機率等級的範圍
        
        Returns:
            {
                'sst': {'very_high': (min, max), 'high': (min, max), ...},
                '100m_temp': {'very_high': (min, max), 'high': (min, max), ...}
            }
        """
        if not self.ecdf_results:
            self.analyze_sst()
            self.analyze_100m_temp()
        
        result = {}
        
        for param in ['sst', '100m_temp']:
            if param not in self.ecdf_results:
                continue
                
            ecdf = self.ecdf_results[param]
            percentiles = ecdf['percentiles']
            
            # 定義各機率等級的範圍
            # very_high: 25-75百分位（核心範圍）
            # high: 10-90百分位
            # moderate: 5-95百分位（使用min/max近似）
            
            result[param] = {
                'very_high': (percentiles['low'], percentiles['high']),
                'high': (percentiles['very_low'], percentiles['very_high']),
                'moderate': (ecdf['min'], ecdf['max'])
            }
        
        self.optimal_ranges = result
        return result
    
    def calculate_habitat_probability(self, sst_grid: np.ndarray, 
                                      temp_100m_grid: np.ndarray) -> np.ndarray:
        """
        計算每個網格點的秋刀魚棲息機率
        
        基於SST和100m水溫的ECDF分析，結合兩個參數計算聯合機率。
        
        Args:
            sst_grid: 海面水溫網格資料
            temp_100m_grid: 100m水溫網格資料
            
        Returns:
            棲息機率網格（0-1之間）
        """
        if 'sst' not in self.ecdf_results or '100m_temp' not in self.ecdf_results:
            self.analyze_sst()
            self.analyze_100m_temp()
        
        sst_ecdf = self.ecdf_results['sst']
        temp_ecdf = self.ecdf_results['100m_temp']
        
        # 計算SST的機率得分
        sst_prob = self._calculate_prob_score(
            sst_grid,
            sst_ecdf['sorted_values'],
            sst_ecdf['cdf']
        )
        
        # 計算100m水溫的機率得分
        temp_prob = self._calculate_prob_score(
            temp_100m_grid,
            temp_ecdf['sorted_values'],
            temp_ecdf['cdf']
        )
        
        # 計算聯合機率（取兩者的幾何平均或乘積）
        # 使用距離核心範圍的距離作為機率評估
        combined_prob = np.sqrt(sst_prob * temp_prob)
        
        return combined_prob
    
    def _calculate_prob_score(self, values: np.ndarray, 
                              sorted_vals: np.ndarray, 
                              cdf: np.ndarray) -> np.ndarray:
        """
        計算給定數值的機率得分
        
        使用三角形機率分布，核心範圍（25-75百分位）得分最高
        """
        # 取得核心範圍
        idx_25 = np.searchsorted(cdf, 0.25)
        idx_75 = np.searchsorted(cdf, 0.75)
        
        if idx_25 >= len(sorted_vals):
            idx_25 = len(sorted_vals) - 1
        if idx_75 >= len(sorted_vals):
            idx_75 = len(sorted_vals) - 1
            
        core_min = sorted_vals[idx_25]
        core_max = sorted_vals[idx_75]
        core_center = (core_min + core_max) / 2
        
        # 計算每個值與核心範圍的距離
        prob_scores = np.zeros_like(values, dtype=float)
        
        # 核心範圍內：高機率
        in_core = (values >= core_min) & (values <= core_max)
        prob_scores[in_core] = 1.0
        
        # 核心範圍外：根據距離遞減
        total_range = sorted_vals[-1] - sorted_vals[0]
        if total_range == 0:
            total_range = 1
        
        # 低於核心範圍
        below_core = values < core_min
        if np.any(below_core):
            dist = (core_min - values[below_core]) / total_range
            prob_scores[below_core] = np.maximum(0, 1 - 2 * dist)
        
        # 高於核心範圍
        above_core = values > core_max
        if np.any(above_core):
            dist = (values[above_core] - core_max) / total_range
            prob_scores[above_core] = np.maximum(0, 1 - 2 * dist)
        
        # NaN值機率為0
        prob_scores[np.isnan(values)] = np.nan
        
        return prob_scores
    
    def get_summary(self) -> Dict:
        """
        獲取分析摘要
        
        Returns:
            分析摘要字典
        """
        if not self.ecdf_results:
            self.analyze_sst()
            self.analyze_100m_temp()
        
        summary = {
            'data_count': len(self.data) if self.data is not None else 0,
            'catch_count': len(self.data[self.data['CPUE'] > 0]) if self.data is not None else 0
        }
        
        for param, label in [('sst', 'SST'), ('100m_temp', '100mT')]:
            if param in self.ecdf_results:
                ecdf = self.ecdf_results[param]
                summary[f'{label}_range'] = f"{ecdf['min']:.1f} - {ecdf['max']:.1f}°C"
                summary[f'{label}_optimal'] = (
                    f"{ecdf['percentiles']['low']:.1f} - "
                    f"{ecdf['percentiles']['high']:.1f}°C"
                )
                summary[f'{label}_mean'] = f"{ecdf['mean']:.1f}°C"
        
        return summary


class HabitatPredictor:
    """秋刀魚棲息地預測器"""
    
    def __init__(self, analyzer: SauryECDFAnalyzer):
        self.analyzer = analyzer
    
    def predict(self, sst_data: Dict, nprsubt_data: Dict) -> Optional[Dict]:
        """
        預測秋刀魚棲息地分布
        
        Args:
            sst_data: HIMSST資料（包含sst, lats, lons）
            nprsubt_data: NPRSUBT資料（包含temp_100m, lats, lons）
            
        Returns:
            預測結果字典，包含機率網格和相關資訊
        """
        if sst_data is None or nprsubt_data is None:
            return None
        
        # 取得SST和100m水溫
        sst = sst_data['sst']
        sst_lats = sst_data['lats']
        sst_lons = sst_data['lons']
        
        temp_100m = nprsubt_data['temp_100m']
        sub_lats = nprsubt_data['lats']
        sub_lons = nprsubt_data['lons']
        
        # 將100m水溫內插到SST網格
        temp_100m_interp = self._interpolate_to_grid(
            temp_100m, sub_lats, sub_lons,
            sst_lats, sst_lons
        )
        
        # 計算棲息機率
        probability = self.analyzer.calculate_habitat_probability(sst, temp_100m_interp)
        
        return {
            'probability': probability,
            'lats': sst_lats,
            'lons': sst_lons,
            'sst_date': sst_data.get('date'),
            'subtemp_date': nprsubt_data.get('date')
        }
    
    def _interpolate_to_grid(self, data: np.ndarray, 
                             src_lats: np.ndarray, src_lons: np.ndarray,
                             dst_lats: np.ndarray, dst_lons: np.ndarray) -> np.ndarray:
        """
        將資料內插到目標網格
        
        使用最近鄰內插法
        """
        from scipy import interpolate
        
        # 建立原始資料的座標網格
        src_lon_grid, src_lat_grid = np.meshgrid(src_lons, src_lats)
        
        # 建立目標資料的座標網格
        dst_lon_grid, dst_lat_grid = np.meshgrid(dst_lons, dst_lats)
        
        # 使用線性內插
        # 先將原始資料展平
        points = np.column_stack([src_lat_grid.ravel(), src_lon_grid.ravel()])
        values = data.ravel()
        
        # 移除NaN值
        valid = ~np.isnan(values)
        if not np.any(valid):
            return np.full((len(dst_lats), len(dst_lons)), np.nan)
        
        points = points[valid]
        values = values[valid]
        
        # 內插到目標網格
        dst_points = np.column_stack([dst_lat_grid.ravel(), dst_lon_grid.ravel()])
        interpolated = interpolate.griddata(
            points, values, dst_points,
            method='nearest'
        )
        
        return interpolated.reshape(len(dst_lats), len(dst_lons))


if __name__ == "__main__":
    # 測試ECDF分析
    analyzer = SauryECDFAnalyzer()
    
    if analyzer.load_data():
        sst_result = analyzer.analyze_sst()
        print("\nSST ECDF分析結果:")
        print(f"  最小值: {sst_result['min']:.2f}°C")
        print(f"  最大值: {sst_result['max']:.2f}°C")
        print(f"  平均值: {sst_result['mean']:.2f}°C")
        print(f"  最適範圍: {sst_result['percentiles']['low']:.2f} - {sst_result['percentiles']['high']:.2f}°C")
        
        temp_result = analyzer.analyze_100m_temp()
        print("\n100m水溫 ECDF分析結果:")
        print(f"  最小值: {temp_result['min']:.2f}°C")
        print(f"  最大值: {temp_result['max']:.2f}°C")
        print(f"  平均值: {temp_result['mean']:.2f}°C")
        print(f"  最適範圍: {temp_result['percentiles']['low']:.2f} - {temp_result['percentiles']['high']:.2f}°C")
        
        summary = analyzer.get_summary()
        print("\n分析摘要:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
