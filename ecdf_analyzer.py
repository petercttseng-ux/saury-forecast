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

    PARAMETERS = {
        'sst': {'column': 'SST', 'label': '海面水溫 SST', 'unit': '°C'},
        'chla': {'column': 'Chla', 'label': '葉綠素 a', 'unit': 'mg m⁻³'},
        'ssha': {'column': 'SSHA', 'label': '海面高度異常 SSHA', 'unit': 'cm'},
        'eke': {'column': 'EKE', 'label': '渦動動能 EKE', 'unit': 'cm² s⁻²'},
        'npp': {'column': 'NPP', 'label': '淨初級生產力 NPP', 'unit': 'mg C m⁻² d⁻¹'},
        'mld': {'column': 'MLD', 'label': '混合層深度 MLD', 'unit': 'm'},
        '100m_temp': {'column': '100mT', 'label': '100 m 水溫', 'unit': '°C'},
    }
        
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
            
            # 轉為數值並移除無法用於 CPUE 加權 ECDF 的紀錄。
            numeric_cols = ['Year', 'Month', 'Lat', 'Long', 'CPUE'] + [
                p['column'] for p in self.PARAMETERS.values()
            ]
            for col in numeric_cols:
                if col in self.data.columns:
                    self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
            self.data = self.data.dropna(subset=['CPUE'])
            self.data = self.data[self.data['CPUE'] > 0].copy()
            
            print(f"成功載入 {len(self.data)} 筆秋刀魚漁獲資料")
            return True
            
        except Exception as e:
            print(f"載入資料失敗: {e}")
            return False
    
    def compute_ecdf(self, data: np.ndarray,
                     weights: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        計算經驗累積分布函數（ECDF）
        
        Args:
            data: 一維數據陣列
            
        Returns:
            (排序後的數據值, 累積機率)
        """
        data = np.asarray(data, dtype=float)
        valid = np.isfinite(data)
        if weights is not None:
            weights = np.asarray(weights, dtype=float)
            valid &= np.isfinite(weights) & (weights > 0)
        data = data[valid]
        if data.size == 0:
            return np.array([], dtype=float), np.array([], dtype=float)

        order = np.argsort(data, kind='mergesort')
        sorted_data = data[order]
        if weights is None:
            cumulative_prob = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
        else:
            sorted_weights = weights[valid][order]
            cumulative_prob = np.cumsum(sorted_weights) / sorted_weights.sum()
        
        return sorted_data, cumulative_prob
    
    @staticmethod
    def _weighted_quantiles(sorted_values: np.ndarray,
                            weighted_cdf: np.ndarray,
                            quantiles: List[float]) -> Dict[float, float]:
        """由排序值與 CPUE 加權 ECDF 線性內插指定分位數。"""
        return {
            q: float(np.interp(q, weighted_cdf, sorted_values))
            for q in quantiles
        }

    def analyze_parameter(self, key: str) -> Dict:
        """計算環境參數的一般 ECDF、CPUE 加權 ECDF 與兩者差異。"""
        if self.data is None or key not in self.PARAMETERS:
            return {}

        meta = self.PARAMETERS[key]
        if meta['column'] not in self.data.columns:
            return {}
        subset = self.data[[meta['column'], 'CPUE']].dropna()
        subset = subset[np.isfinite(subset[meta['column']]) &
                        np.isfinite(subset['CPUE']) & (subset['CPUE'] > 0)]
        values = subset[meta['column']].to_numpy(dtype=float)
        weights = subset['CPUE'].to_numpy(dtype=float)
        if values.size == 0:
            return {}

        order = np.argsort(values, kind='mergesort')
        ordered_values = values[order]
        ordered_weights = weights[order]
        sorted_values, starts, counts = np.unique(
            ordered_values, return_index=True, return_counts=True
        )
        weight_by_value = np.add.reduceat(ordered_weights, starts)
        cdf = np.cumsum(counts) / counts.sum()
        weighted_cdf = np.cumsum(weight_by_value) / weight_by_value.sum()

        quantile_levels = sorted(set(config.ECDF_PERCENTILES.values()))
        weighted_q = self._weighted_quantiles(sorted_values, weighted_cdf,
                                              quantile_levels)
        unweighted_q = {q: float(np.quantile(values, q)) for q in quantile_levels}
        percentile_values = {
            name: weighted_q[level]
            for name, level in config.ECDF_PERCENTILES.items()
        }
        unweighted_percentiles = {
            name: unweighted_q[level]
            for name, level in config.ECDF_PERCENTILES.items()
        }

        # F(x)-Gcpue(x) 為作業觀測 ECDF 與 CPUE 加權 ECDF 的差。
        # 絕對差最大處是環境與高 CPUE 關聯最強的 ECDF 指標點。
        delta = cdf - weighted_cdf
        d_idx = int(np.argmax(np.abs(delta)))
        weighted_mean = float(np.average(values, weights=weights))
        weighted_var = float(np.average((values - weighted_mean) ** 2, weights=weights))

        result = {
            'key': key,
            'column': meta['column'],
            'label': meta['label'],
            'unit': meta['unit'],
            'sorted_values': sorted_values,
            'cdf': cdf,
            'weighted_cdf': weighted_cdf,
            'delta': delta,
            'percentiles': percentile_values,
            'unweighted_percentiles': unweighted_percentiles,
            'd_max_value': float(sorted_values[d_idx]),
            'd_max': float(delta[d_idx]),
            'd_max_abs': float(abs(delta[d_idx])),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'mean': weighted_mean,
            'std': float(np.sqrt(weighted_var)),
            'n': int(values.size),
            'weight_sum': float(weights.sum()),
        }
        self.ecdf_results[key] = result
        return result

    def analyze_all(self) -> Dict:
        """分析檔案中所有可用海洋環境參數。"""
        for key in self.PARAMETERS:
            self.analyze_parameter(key)
        return self.ecdf_results

    def get_curve_data(self, max_points: int = 160) -> Dict:
        """輸出前端繪圖用的精簡一般／CPUE 加權 ECDF 曲線。"""
        self.analyze_all()
        curves = {}
        for key, result in self.ecdf_results.items():
            values = result['sorted_values']
            count = min(max_points, len(values))
            idx = np.linspace(0, len(values) - 1, count).astype(int)
            p = result['percentiles']
            curves[key] = {
                'v': [round(float(x), 3) for x in values[idx]],
                'cdf': [round(float(x), 4) for x in result['cdf'][idx]],
                'weightedCdf': [round(float(x), 4)
                                for x in result['weighted_cdf'][idx]],
                'min': round(float(result['min']), 2),
                'max': round(float(result['max']), 2),
                'mean': round(float(result['mean']), 2),
                'p10': round(float(p['very_low']), 2),
                'p25': round(float(p['low']), 2),
                'p50': round(float(p['moderate']), 2),
                'p75': round(float(p['high']), 2),
                'p90': round(float(p['very_high']), 2),
                'dMaxValue': round(float(result['d_max_value']), 2),
                'dMaxAbs': round(float(result['d_max_abs']), 4),
            }
        return curves

    def analyze_sst(self) -> Dict:
        """
        分析海面水溫（SST）與秋刀魚漁獲的ECDF關係
        
        Returns:
            分析結果字典
        """
        return self.analyze_parameter('sst')
    
    def analyze_100m_temp(self) -> Dict:
        """
        分析100m次表層水溫（100mT）與秋刀魚漁獲的ECDF關係
        
        Returns:
            分析結果字典
        """
        return self.analyze_parameter('100m_temp')
    
    def get_optimal_ranges(self) -> Dict:
        """
        獲取秋刀魚最適漁獲的環境參數範圍
        
        基於 ECDF 分析，定義不同適合度等級的範圍
        
        Returns:
            {
                'sst': {'very_high': (min, max), 'high': (min, max), ...},
                '100m_temp': {'very_high': (min, max), 'high': (min, max), ...}
            }
        """
        self.analyze_all()
        
        result = {}
        
        for param in ['sst', '100m_temp']:
            if param not in self.ecdf_results:
                continue
                
            ecdf = self.ecdf_results[param]
            percentiles = ecdf['percentiles']
            
            # 分位數均來自 CPUE 加權 ECDF。
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
        計算每個網格點的秋刀魚相對棲地適合度
        
        基於 SST 和 100m 水溫的 CPUE 加權 ECDF，計算相對棲地適合度。
        
        Args:
            sst_grid: 海面水溫網格資料
            temp_100m_grid: 100m水溫網格資料
            
        Returns:
            相對棲地適合度網格（0-1；不是校準後的出現機率）
        """
        if 'sst' not in self.ecdf_results or '100m_temp' not in self.ecdf_results:
            self.analyze_sst()
            self.analyze_100m_temp()
        
        sst_ecdf = self.ecdf_results['sst']
        temp_ecdf = self.ecdf_results['100m_temp']
        
        # 計算 SST 適合度得分
        sst_prob = self._calculate_prob_score(
            sst_grid,
            sst_ecdf['sorted_values'],
            sst_ecdf['weighted_cdf']
        )
        
        # 計算 100 m 水溫適合度得分
        temp_prob = self._calculate_prob_score(
            temp_100m_grid,
            temp_ecdf['sorted_values'],
            temp_ecdf['weighted_cdf']
        )
        
        # 幾何平均要求兩個因子均具適合度，且維持 0–1 尺度。
        combined_prob = np.sqrt(sst_prob * temp_prob)
        
        return combined_prob
    
    def _calculate_prob_score(self, values: np.ndarray, 
                              sorted_vals: np.ndarray, 
                              cdf: np.ndarray) -> np.ndarray:
        """
        計算給定數值的適合度得分
        
        使用梯形適合度函數：核心範圍（P25–P75）為 1，
        並在 P10/P90 降至 0。
        """
        # 由 CPUE 加權 ECDF 取得 P10/P25/P75/P90。
        core_min = float(np.interp(0.25, cdf, sorted_vals))
        core_max = float(np.interp(0.75, cdf, sorted_vals))
        outer_min = float(np.interp(0.10, cdf, sorted_vals))
        outer_max = float(np.interp(0.90, cdf, sorted_vals))

        # 核心環境窗內適合度為 1；外側在 P10/P90 線性降至 0。
        prob_scores = np.zeros_like(values, dtype=float)
        in_core = (values >= core_min) & (values <= core_max)
        prob_scores[in_core] = 1.0

        low_slope = (values > outer_min) & (values < core_min)
        if core_min > outer_min:
            prob_scores[low_slope] = (
                (values[low_slope] - outer_min) / (core_min - outer_min)
            )
        high_slope = (values > core_max) & (values < outer_max)
        if outer_max > core_max:
            prob_scores[high_slope] = (
                (outer_max - values[high_slope]) / (outer_max - core_max)
            )

        # NaN 值的適合度為 0
        prob_scores[np.isnan(values)] = np.nan

        return prob_scores
    
    def get_summary(self) -> Dict:
        """
        獲取分析摘要
        
        Returns:
            分析摘要字典
        """
        self.analyze_all()
        
        summary = {
            'data_count': len(self.data) if self.data is not None else 0,
            'catch_count': len(self.data[self.data['CPUE'] > 0]) if self.data is not None else 0,
            'year_range': [int(self.data['Year'].min()), int(self.data['Year'].max())]
                if self.data is not None and 'Year' in self.data else [],
            'months': sorted(int(v) for v in self.data['Month'].dropna().unique())
                if self.data is not None and 'Month' in self.data else [],
            'duplicate_spacetime_rows': int(
                self.data.duplicated(['Year', 'Month', 'Lat', 'Long']).sum()
            ) if self.data is not None else 0,
        }
        
        parameter_summary = {}
        for param, meta in self.PARAMETERS.items():
            if param in self.ecdf_results:
                ecdf = self.ecdf_results[param]
                digits = 2 if param in ('chla', 'ssha') else 1
                unit = meta['unit']
                core = [ecdf['percentiles']['low'], ecdf['percentiles']['high']]
                probable = [ecdf['percentiles']['very_low'],
                            ecdf['percentiles']['very_high']]
                parameter_summary[param] = {
                    'column': meta['column'],
                    'label': meta['label'],
                    'unit': unit,
                    'core': [round(float(v), digits) for v in core],
                    'probable': [round(float(v), digits) for v in probable],
                    'weighted_mean': round(float(ecdf['mean']), digits),
                    'd_max_value': round(float(ecdf['d_max_value']), digits),
                    'd_max_abs': round(float(ecdf['d_max_abs']), 4),
                    'observed': [round(float(ecdf['min']), digits),
                                 round(float(ecdf['max']), digits)],
                    'n': ecdf['n'],
                }

        summary['parameters'] = parameter_summary
        summary['method'] = (
            'CPUE 加權 ECDF；核心環境窗為加權 P25–P75，可能環境窗為加權 P10–P90。'
        )
        summary['score_note'] = '0–1 為相對棲地適合度指數，不是校準後的出現機率。'

        # 保留既有 API 欄位，避免舊前端或外部呼叫中斷。
        for param, label in [('sst', 'SST'), ('100m_temp', '100mT')]:
            if param in parameter_summary:
                p = parameter_summary[param]
                summary[f'{label}_range'] = (
                    f"{p['observed'][0]:g} - {p['observed'][1]:g}{p['unit']}"
                )
                summary[f'{label}_optimal'] = (
                    f"{p['core'][0]:g} - {p['core'][1]:g}{p['unit']}"
                )
                summary[f'{label}_mean'] = f"{p['weighted_mean']:g}{p['unit']}"

        return summary


class HabitatPredictor:
    """秋刀魚棲息地預測器"""
    
    def __init__(self, analyzer: SauryECDFAnalyzer):
        self.analyzer = analyzer
    
    def predict(self, sst_data: Dict, nprsubt_data: Optional[Dict] = None,
                max_subsurface_lag_days: int = 3) -> Optional[Dict]:
        """
        預測秋刀魚棲息地分布
        
        Args:
            sst_data: HIMSST資料（包含sst, lats, lons）
            nprsubt_data: NPRSUBT資料（包含temp_100m, lats, lons）
            
        Returns:
            預測結果字典，包含相對 HSI 網格和相關資訊
        """
        if sst_data is None:
            return None
        
        # 取得SST和100m水溫
        sst = sst_data['sst']
        sst_lats = sst_data['lats']
        sst_lons = sst_data['lons']
        
        sst_ecdf = self.analyzer.ecdf_results.get('sst') or self.analyzer.analyze_sst()
        suitability = self.analyzer._calculate_prob_score(
            sst, sst_ecdf['sorted_values'], sst_ecdf['weighted_cdf']
        )
        variables = ['SST']
        sub_lag_days = None

        if nprsubt_data is not None:
            sst_date = sst_data.get('date')
            sub_date = nprsubt_data.get('date')
            if sst_date is not None and sub_date is not None:
                sub_lag_days = abs((sst_date.date() - sub_date.date()).days)
            use_subsurface = sub_lag_days is None or sub_lag_days <= max_subsurface_lag_days
            if use_subsurface:
                temp_100m_interp = self._interpolate_to_grid(
                    nprsubt_data['temp_100m'], nprsubt_data['lats'], nprsubt_data['lons'],
                    sst_lats, sst_lons
                )
                temp_ecdf = (self.analyzer.ecdf_results.get('100m_temp') or
                             self.analyzer.analyze_100m_temp())
                temp_score = self.analyzer._calculate_prob_score(
                    temp_100m_interp, temp_ecdf['sorted_values'], temp_ecdf['weighted_cdf']
                )
                suitability = np.sqrt(suitability * temp_score)
                variables.append('100mT')
        
        return {
            'probability': suitability,
            'lats': sst_lats,
            'lons': sst_lons,
            'sst_date': sst_data.get('date'),
            'subtemp_date': nprsubt_data.get('date') if nprsubt_data else None,
            'subtemp_lag_days': sub_lag_days,
            'variables': variables,
            'model_label': 'SST + 100mT' if len(variables) == 2 else 'SST（次表層資料過舊或缺少）',
            'score_note': '相對棲地適合度，不是校準後的出現機率',
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
