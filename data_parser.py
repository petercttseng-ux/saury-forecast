# -*- coding: utf-8 -*-
"""
JMA海洋氣象資料桌面GUI系統 - 資料解析模組
Data Parser Module for JMA Ocean Weather Desktop GUI System
"""

import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple, List
import re
import config


class HIMSSTParser:
    """HIMSST（海面水溫）資料解析器"""
    
    def __init__(self):
        # 建立經緯度網格
        self.lats = np.linspace(config.HIMSST_LAT_START, 
                                config.HIMSST_LAT_END, 
                                config.HIMSST_ROWS)
        self.lons = np.linspace(config.HIMSST_LON_START, 
                                config.HIMSST_LON_END, 
                                config.HIMSST_COLS)
    
    def parse_file(self, filepath: Path) -> Optional[Dict]:
        """
        解析HIMSST資料檔案
        
        資料格式：
        - 601筆記錄：1筆header + 600筆data
        - Header: YYYYMMDD（年月日各4位數）
        - 每筆data：800個3位數值（0.1°C單位）
        - 由北向南、由西向東排列
        - 888=海冰, 999=陸地/無效值
        
        Returns:
            {
                'date': datetime,
                'sst': numpy array (600x800),
                'lats': numpy array,
                'lons': numpy array
            }
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if len(lines) < 601:
                print(f"資料檔案行數不足: {filepath}")
                return None
            
            # 解析header
            header = lines[0].strip()
            year = int(header[:4])
            month = int(header[4:8])
            day = int(header[8:12])
            date = datetime(year, month, day)
            
            # 解析SST資料
            sst = np.full((config.HIMSST_ROWS, config.HIMSST_COLS), np.nan)
            
            for i, line in enumerate(lines[1:config.HIMSST_ROWS + 1]):
                line = line.strip()
                if len(line) < config.HIMSST_COLS * 3:
                    continue
                    
                for j in range(config.HIMSST_COLS):
                    try:
                        val_str = line[j*3:(j+1)*3]
                        val = int(val_str)
                        
                        if val == config.HIMSST_MISSING_VALUE:
                            sst[i, j] = np.nan  # 陸地/無效
                        elif val == config.HIMSST_ICE_VALUE:
                            sst[i, j] = -2.0  # 海冰標記為-2
                        else:
                            sst[i, j] = val * config.HIMSST_UNIT_FACTOR
                    except:
                        sst[i, j] = np.nan
            
            return {
                'date': date,
                'sst': sst,
                'lats': self.lats,
                'lons': self.lons
            }
            
        except Exception as e:
            print(f"解析HIMSST檔案失敗: {filepath}, 錯誤: {e}")
            return None
    
    @staticmethod
    def extract_date_from_filename(filename: str) -> Optional[datetime]:
        """從檔名提取日期"""
        match = re.search(r'D(\d{8})', filename)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, '%Y%m%d')
        return None


class NPRSUBTParser:
    """NPRSUBT（次表層水溫）資料解析器"""
    
    def __init__(self):
        # 建立經緯度網格
        self.lats = np.linspace(config.NPRSUBT_LAT_START, 
                                config.NPRSUBT_LAT_END, 
                                config.NPRSUBT_ROWS)
        self.lons = np.linspace(config.NPRSUBT_LON_START, 
                                config.NPRSUBT_LON_END, 
                                config.NPRSUBT_COLS)
    
    def parse_file(self, filepath: Path) -> Optional[Dict]:
        """
        解析NPRSUBT資料檔案
        
        資料格式：
        - 1585筆記錄：1筆header + 4個396筆記錄區塊
        - 深度：50m, 100m, 200m, 400m
        - 每個區塊：第1行為深度資訊，後395行為資料
        - 每筆data：550個4位數值（0.01°C單位）
        - 由北向南、由西向東排列
        - 9999=無效值
        
        Returns:
            {
                'date': datetime,
                'temp_50m': numpy array,
                'temp_100m': numpy array,
                'temp_200m': numpy array,
                'temp_400m': numpy array,
                'lats': numpy array,
                'lons': numpy array
            }
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if len(lines) < 1585:
                print(f"資料檔案行數不足: {filepath}")
                return None
            
            # 解析header
            header = lines[0].strip()
            year = int(header[:4])
            month = int(header[4:8])
            day = int(header[8:12])
            date = datetime(year, month, day)
            
            result = {
                'date': date,
                'lats': self.lats,
                'lons': self.lons
            }
            
            # 解析各深度的溫度資料
            depth_names = ['temp_50m', 'temp_100m', 'temp_200m', 'temp_400m']
            block_starts = [2, 398, 794, 1190]  # 各區塊起始行（0-indexed，跳過深度行）
            
            for depth_idx, (name, start) in enumerate(zip(depth_names, block_starts)):
                temp = np.full((config.NPRSUBT_ROWS, config.NPRSUBT_COLS), np.nan)
                
                for i in range(config.NPRSUBT_ROWS):
                    line_idx = start + i
                    if line_idx >= len(lines):
                        break
                        
                    line = lines[line_idx].strip()
                    if len(line) < config.NPRSUBT_COLS * 4:
                        continue
                    
                    for j in range(config.NPRSUBT_COLS):
                        try:
                            val_str = line[j*4:(j+1)*4]
                            val = int(val_str)
                            
                            if val == config.NPRSUBT_MISSING_VALUE:
                                temp[i, j] = np.nan
                            else:
                                temp[i, j] = val * config.NPRSUBT_UNIT_FACTOR
                        except:
                            temp[i, j] = np.nan
                
                result[name] = temp
            
            return result
            
        except Exception as e:
            print(f"解析NPRSUBT檔案失敗: {filepath}, 錯誤: {e}")
            return None
    
    @staticmethod
    def extract_date_from_filename(filename: str) -> Optional[datetime]:
        """從檔名提取日期"""
        match = re.search(r'D(\d{8})', filename)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, '%Y%m%d')
        return None


class NPRSUBCParser:
    """NPRSUBC（表面海流）資料解析器"""
    
    def __init__(self):
        # 建立經緯度網格
        self.lats = np.linspace(config.NPRSUBC_LAT_START, 
                                config.NPRSUBC_LAT_END, 
                                config.NPRSUBC_ROWS)
        self.lons = np.linspace(config.NPRSUBC_LON_START, 
                                config.NPRSUBC_LON_END, 
                                config.NPRSUBC_COLS)
    
    def parse_file(self, filepath: Path) -> Optional[Dict]:
        """
        解析NPRSUBC資料檔案
        
        資料格式：
        - 795筆記錄：1筆header + 2個397筆記錄區塊
        - 第1區塊：東向分量（Eastward）
        - 第2區塊：北向分量（Northward）
        - 每個區塊：第1行為方向資訊，後396行為資料
        - 每筆data：551個4位數值（1 cm/sec單位）
        - 9999=無效值
        
        Returns:
            {
                'date': datetime,
                'u': numpy array (東向分量, m/s),
                'v': numpy array (北向分量, m/s),
                'speed': numpy array (流速, m/s),
                'lats': numpy array,
                'lons': numpy array
            }
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if len(lines) < 795:
                print(f"資料檔案行數不足: {filepath}")
                return None
            
            # 解析header
            header = lines[0].strip()
            year = int(header[:4])
            month = int(header[4:8])
            day = int(header[8:12])
            date = datetime(year, month, day)
            
            # 解析東向分量（u）- 區塊1，從第2行開始（index 1），跳過方向資訊行
            u = np.full((config.NPRSUBC_ROWS, config.NPRSUBC_COLS), np.nan)
            for i in range(config.NPRSUBC_ROWS):
                line_idx = 2 + i  # 跳過header和方向資訊行
                if line_idx >= len(lines):
                    break
                
                line = lines[line_idx].strip()
                if len(line) < config.NPRSUBC_COLS * 4:
                    continue
                
                for j in range(config.NPRSUBC_COLS):
                    try:
                        val_str = line[j*4:(j+1)*4]
                        val = int(val_str)
                        
                        if val == config.NPRSUBC_MISSING_VALUE:
                            u[i, j] = np.nan
                        else:
                            u[i, j] = val * config.NPRSUBC_UNIT_FACTOR  # cm/s -> m/s
                    except:
                        u[i, j] = np.nan
            
            # 解析北向分量（v）- 區塊2，從第399行開始（index 398）
            v = np.full((config.NPRSUBC_ROWS, config.NPRSUBC_COLS), np.nan)
            for i in range(config.NPRSUBC_ROWS):
                line_idx = 399 + i  # 跳過方向資訊行
                if line_idx >= len(lines):
                    break
                
                line = lines[line_idx].strip()
                if len(line) < config.NPRSUBC_COLS * 4:
                    continue
                
                for j in range(config.NPRSUBC_COLS):
                    try:
                        val_str = line[j*4:(j+1)*4]
                        val = int(val_str)
                        
                        if val == config.NPRSUBC_MISSING_VALUE:
                            v[i, j] = np.nan
                        else:
                            v[i, j] = val * config.NPRSUBC_UNIT_FACTOR
                    except:
                        v[i, j] = np.nan
            
            # 計算流速
            speed = np.sqrt(u**2 + v**2)
            
            return {
                'date': date,
                'u': u,
                'v': v,
                'speed': speed,
                'lats': self.lats,
                'lons': self.lons
            }
            
        except Exception as e:
            print(f"解析NPRSUBC檔案失敗: {filepath}, 錯誤: {e}")
            return None
    
    @staticmethod
    def extract_date_from_filename(filename: str) -> Optional[datetime]:
        """從檔名提取日期"""
        match = re.search(r'D(\d{8})', filename)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, '%Y%m%d')
        return None


class DataManager:
    """資料管理器 - 統一管理所有資料的載入和存取"""
    
    def __init__(self):
        self.himsst_parser = HIMSSTParser()
        self.nprsubt_parser = NPRSUBTParser()
        self.nprsubc_parser = NPRSUBCParser()
        
        # 快取已載入的資料
        self.himsst_cache: Dict[str, Dict] = {}
        self.nprsubt_cache: Dict[str, Dict] = {}
        self.nprsubc_cache: Dict[str, Dict] = {}
    
    def load_himsst_files(self) -> List[str]:
        """載入所有HIMSST檔案，返回可用日期列表"""
        dates = []
        for filepath in sorted(config.HIMSST_DIR.glob("*.txt"), reverse=True):
            date = HIMSSTParser.extract_date_from_filename(filepath.name)
            if date:
                date_str = date.strftime('%Y-%m-%d')
                data = self.himsst_parser.parse_file(filepath)
                if data:
                    self.himsst_cache[date_str] = data
                    dates.append(date_str)
        return dates
    
    def load_nprsubt_files(self) -> List[str]:
        """載入所有NPRSUBT檔案，返回可用日期列表"""
        dates = []
        for filepath in sorted(config.NPRSUBT_DIR.glob("*.txt"), reverse=True):
            date = NPRSUBTParser.extract_date_from_filename(filepath.name)
            if date:
                date_str = date.strftime('%Y-%m-%d')
                data = self.nprsubt_parser.parse_file(filepath)
                if data:
                    self.nprsubt_cache[date_str] = data
                    dates.append(date_str)
        return dates
    
    def load_nprsubc_files(self) -> List[str]:
        """載入所有NPRSUBC檔案，返回可用日期列表"""
        dates = []
        for filepath in sorted(config.NPRSUBC_DIR.glob("*.txt"), reverse=True):
            date = NPRSUBCParser.extract_date_from_filename(filepath.name)
            if date:
                date_str = date.strftime('%Y-%m-%d')
                data = self.nprsubc_parser.parse_file(filepath)
                if data:
                    self.nprsubc_cache[date_str] = data
                    dates.append(date_str)
        return dates
    
    def get_himsst(self, date_str: str) -> Optional[Dict]:
        """取得指定日期的HIMSST資料"""
        return self.himsst_cache.get(date_str)
    
    def get_nprsubt(self, date_str: str) -> Optional[Dict]:
        """取得指定日期的NPRSUBT資料"""
        return self.nprsubt_cache.get(date_str)
    
    def get_nprsubc(self, date_str: str) -> Optional[Dict]:
        """取得指定日期的NPRSUBC資料"""
        return self.nprsubc_cache.get(date_str)
    
    def get_available_dates(self) -> Dict[str, List[str]]:
        """取得所有資料類型的可用日期"""
        return {
            'himsst': list(self.himsst_cache.keys()),
            'nprsubt': list(self.nprsubt_cache.keys()),
            'nprsubc': list(self.nprsubc_cache.keys())
        }


if __name__ == "__main__":
    # 測試解析功能
    manager = DataManager()
    
    himsst_dates = manager.load_himsst_files()
    print(f"HIMSST可用日期: {himsst_dates}")
    
    nprsubt_dates = manager.load_nprsubt_files()
    print(f"NPRSUBT可用日期: {nprsubt_dates}")
    
    nprsubc_dates = manager.load_nprsubc_files()
    print(f"NPRSUBC可用日期: {nprsubc_dates}")
