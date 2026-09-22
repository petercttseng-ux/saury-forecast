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
import grid_io


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
        解析HIMSST資料檔案（向量化）

        資料格式：
        - 601筆記錄：1筆header + 600筆data
        - Header: YYYYMMDD（年月日各4位數）
        - 每筆data：800個3位數值（0.1°C單位）
        - 由北向南、由西向東排列
        - 888=海冰, 999=陸地/無效值
        """
        try:
            lines = grid_io.read_records(filepath, config.HIMSST_ROWS + 1)
            if lines is None:
                print(f"資料檔案行數不足: {filepath}")
                return None

            date = grid_io.parse_header_date(lines[0])
            sst = grid_io.decode_fixed_width(
                lines[1:config.HIMSST_ROWS + 1],
                config.HIMSST_COLS, 3,
                missing=config.HIMSST_MISSING_VALUE,
                factor=config.HIMSST_UNIT_FACTOR,
                special={config.HIMSST_ICE_VALUE: -2.0},
            )

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
        解析NPRSUBT資料檔案（向量化）

        - 1585筆記錄：1筆header + 4個396筆記錄區塊（50/100/200/400 m）
        - 每個區塊：第1行為深度資訊，後395行為資料
        - 每筆data：550個4位數值（0.01°C單位）；9999=無效值
        """
        try:
            lines = grid_io.read_records(filepath, 1 + 4 * config.NPRSUBT_BLOCK_SIZE - 1)
            if lines is None:
                print(f"資料檔案行數不足: {filepath}")
                return None

            date = grid_io.parse_header_date(lines[0])
            result = {'date': date, 'lats': self.lats, 'lons': self.lons}

            depth_names = ['temp_50m', 'temp_100m', 'temp_200m', 'temp_400m']
            block_starts = [2, 398, 794, 1190]

            for name, start in zip(depth_names, block_starts):
                block = lines[start:start + config.NPRSUBT_ROWS]
                if len(block) < config.NPRSUBT_ROWS:
                    block = block + [''] * (config.NPRSUBT_ROWS - len(block))
                result[name] = grid_io.decode_fixed_width(
                    block, config.NPRSUBT_COLS, 4,
                    missing=config.NPRSUBT_MISSING_VALUE,
                    factor=config.NPRSUBT_UNIT_FACTOR,
                )

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
        解析NPRSUBC資料檔案（向量化）

        - 795筆記錄：1筆header + 2個397筆記錄區塊（東向/北向分量）
        - 每個區塊：第1行為方向資訊，後396行為資料
        - 每筆data：551個4位數值（1 cm/s 單位）；9999=無效值
        """
        try:
            lines = grid_io.read_records(filepath, 1 + 2 * config.NPRSUBC_BLOCK_SIZE - 1)
            if lines is None:
                print(f"資料檔案行數不足: {filepath}")
                return None

            date = grid_io.parse_header_date(lines[0])

            def block(start):
                b = lines[start:start + config.NPRSUBC_ROWS]
                if len(b) < config.NPRSUBC_ROWS:
                    b = b + [''] * (config.NPRSUBC_ROWS - len(b))
                return grid_io.decode_fixed_width(
                    b, config.NPRSUBC_COLS, 4,
                    missing=config.NPRSUBC_MISSING_VALUE,
                    factor=config.NPRSUBC_UNIT_FACTOR,
                )

            u = block(2)     # Eastward_Component
            v = block(399)   # Northward_Component
            speed = np.sqrt(u ** 2 + v ** 2)

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



class MGDSSTParser:
    """MGDSST（全球每日海面水溫）資料解析器 — HIMSST 遲到或破洞時的備援來源"""

    def __init__(self):
        self.lats = np.linspace(config.MGDSST_LAT_START,
                                config.MGDSST_LAT_END,
                                config.MGDSST_ROWS)
        self.lons = np.linspace(config.MGDSST_LON_START,
                                config.MGDSST_LON_END,
                                config.MGDSST_COLS)

    def parse_file(self, filepath: Path) -> Optional[Dict]:
        """
        解析MGDSST資料檔案

        - 721筆記錄：1筆header + 720筆data（由北向南）
        - 每筆data：1440個3位數值（0.1°C單位）；888=海冰, 999=陸地/無效
        """
        try:
            lines = grid_io.read_records(filepath, config.MGDSST_ROWS + 1)
            if lines is None:
                print(f"資料檔案行數不足: {filepath}")
                return None

            date = grid_io.parse_header_date(lines[0])
            body = lines[1:config.MGDSST_ROWS + 1]

            # 欄寬由實際列長推得，避免 JMA 日後調整位數時靜默解錯
            width = max(3, len(body[0].rstrip()) // config.MGDSST_COLS)
            sst = grid_io.decode_fixed_width(
                body, config.MGDSST_COLS, width,
                missing=config.MGDSST_MISSING_VALUE if width == 3 else 9999,
                factor=config.MGDSST_UNIT_FACTOR,
                special={config.MGDSST_ICE_VALUE: -2.0} if width == 3 else None,
            )

            return {
                'date': date,
                'sst': sst,
                'lats': self.lats,
                'lons': self.lons
            }

        except Exception as e:
            print(f"解析MGDSST檔案失敗: {filepath}, 錯誤: {e}")
            return None

    @staticmethod
    def extract_date_from_filename(filename: str) -> Optional[datetime]:
        match = re.search(r'D(\d{8})', filename)
        if match:
            return datetime.strptime(match.group(1), '%Y%m%d')
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
