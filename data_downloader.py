# -*- coding: utf-8 -*-
"""
JMA海洋氣象資料桌面GUI系統 - 資料下載模組
Data Downloader Module for JMA Ocean Weather Desktop GUI System
"""

import requests
from bs4 import BeautifulSoup
from pathlib import Path
import gzip
import io
import re
from datetime import datetime
from typing import List, Tuple, Optional
import config

class JMADataDownloader:
    """JMA資料下載器 - 處理HIMSST、NPRSUBT、NPRSUBC三種資料的下載"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def parse_directory(self, url: str, file_pattern: str) -> List[Tuple[str, str]]:
        """
        解析JMA目錄頁面，取得符合模式的檔案列表
        
        Args:
            url: 目錄URL
            file_pattern: 檔案名稱模式（正規表達式）
            
        Returns:
            List of (filename, full_url) tuples, 按日期降序排列
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            files = []
            pattern = re.compile(file_pattern)
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if pattern.match(href):
                    full_url = url.rstrip('/') + '/' + href
                    files.append((href, full_url))
            
            # 按檔名日期降序排列
            files.sort(key=lambda x: x[0], reverse=True)
            return files
            
        except Exception as e:
            print(f"解析目錄失敗: {url}, 錯誤: {e}")
            return []
    
    def get_available_years_months(self, base_url: str) -> List[Tuple[str, str]]:
        """
        取得可用的年份/月份目錄
        
        Returns:
            List of (year, month) tuples
        """
        try:
            response = self.session.get(base_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            years = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').strip('/')
                if href.isdigit() and len(href) == 4:
                    years.append(href)
            
            years.sort(reverse=True)
            
            # 取得最新年份的月份
            result = []
            for year in years[:2]:  # 檢查最近兩年
                year_url = f"{base_url}/{year}/"
                try:
                    response = self.session.get(year_url, timeout=30)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '').strip('/')
                        if href.isdigit() and len(href) == 2:
                            result.append((year, href))
                except:
                    pass
            
            result.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return result
            
        except Exception as e:
            print(f"取得年/月目錄失敗: {e}")
            return []
    
    def _find_latest_himsst_files(self, count: int,
                                   pattern: str) -> List[Tuple[str, str]]:
        """動態搜尋最新 HIMSST 年份目錄"""
        current_year = datetime.now().year
        collected: List[Tuple[str, str]] = []

        for year in range(current_year, current_year - 3, -1):
            url = f"{config.HIMSST_BASE_URL}/{year}"
            files = self.parse_directory(url, pattern)
            for f in files:
                if len(collected) < count:
                    collected.append(f)
            if len(collected) >= count:
                break

        return collected

    def download_himsst(self, count: int = 10,
                        progress_callback=None) -> List[Path]:
        """
        下載HIMSST（海面水溫）資料

        Args:
            count: 下載筆數
            progress_callback: 進度回調函數 (current, total, message)

        Returns:
            已下載的檔案路徑列表
        """
        downloaded = []
        total_needed = count

        if progress_callback:
            progress_callback(0, total_needed, "正在搜尋HIMSST資料...")

        pattern = r"him_sst_pac_D\d{8}\.txt$"
        files = self._find_latest_himsst_files(count, pattern)
        
        for i, (filename, url) in enumerate(files[:count]):
            if progress_callback:
                progress_callback(i, total_needed, f"下載 {filename}...")
            
            try:
                local_path = config.HIMSST_DIR / filename
                if local_path.exists():
                    downloaded.append(local_path)
                    continue
                    
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                downloaded.append(local_path)
                print(f"已下載: {filename}")
                
            except Exception as e:
                print(f"下載失敗: {filename}, 錯誤: {e}")
        
        if progress_callback:
            progress_callback(total_needed, total_needed, "HIMSST下載完成")
        
        return downloaded
    
    def download_nprsubt(self, count: int = 10, 
                         progress_callback=None) -> List[Path]:
        """
        下載NPRSUBT（次表層水溫）資料
        
        Args:
            count: 下載筆數
            progress_callback: 進度回調函數
            
        Returns:
            已下載的檔案路徑列表
        """
        downloaded = []
        total_needed = count
        
        if progress_callback:
            progress_callback(0, total_needed, "正在搜尋NPRSUBT資料...")
        
        # NPRSUBT 資料在年/月目錄下
        year_months = self.get_available_years_months(config.NPRSUBT_BASE_URL)
        
        collected_files = []
        for year, month in year_months:
            if len(collected_files) >= count:
                break
                
            dir_url = f"{config.NPRSUBT_BASE_URL}/{year}/{month}/"
            pattern = r"npr_subt_jpn_D\d{8}\.txt\.gz$"
            
            files = self.parse_directory(dir_url, pattern)
            for f in files:
                if len(collected_files) < count:
                    collected_files.append(f)
        
        for i, (filename, url) in enumerate(collected_files[:count]):
            if progress_callback:
                progress_callback(i, total_needed, f"下載 {filename}...")
            
            try:
                # 壓縮檔解壓後的本地名稱
                local_name = filename.replace('.gz', '')
                local_path = config.NPRSUBT_DIR / local_name
                
                if local_path.exists():
                    downloaded.append(local_path)
                    continue
                
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                
                # 解壓縮gz檔案
                compressed = io.BytesIO(response.content)
                with gzip.GzipFile(fileobj=compressed) as gz:
                    data = gz.read().decode('utf-8')
                
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(data)
                
                downloaded.append(local_path)
                print(f"已下載並解壓: {local_name}")
                
            except Exception as e:
                print(f"下載失敗: {filename}, 錯誤: {e}")
        
        if progress_callback:
            progress_callback(total_needed, total_needed, "NPRSUBT下載完成")
        
        return downloaded
    
    def download_nprsubc(self, count: int = 10, 
                         progress_callback=None) -> List[Path]:
        """
        下載NPRSUBC（表面海流）資料
        
        Args:
            count: 下載筆數
            progress_callback: 進度回調函數
            
        Returns:
            已下載的檔案路徑列表
        """
        downloaded = []
        total_needed = count
        
        if progress_callback:
            progress_callback(0, total_needed, "正在搜尋NPRSUBC資料...")
        
        # NPRSUBC 資料在年/月目錄下
        year_months = self.get_available_years_months(config.NPRSUBC_BASE_URL)
        
        collected_files = []
        for year, month in year_months:
            if len(collected_files) >= count:
                break
                
            dir_url = f"{config.NPRSUBC_BASE_URL}/{year}/{month}/"
            pattern = r"npr_subc_jpn_D\d{8}\.txt\.gz$"
            
            files = self.parse_directory(dir_url, pattern)
            for f in files:
                if len(collected_files) < count:
                    collected_files.append(f)
        
        for i, (filename, url) in enumerate(collected_files[:count]):
            if progress_callback:
                progress_callback(i, total_needed, f"下載 {filename}...")
            
            try:
                local_name = filename.replace('.gz', '')
                local_path = config.NPRSUBC_DIR / local_name
                
                if local_path.exists():
                    downloaded.append(local_path)
                    continue
                
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                
                # 解壓縮gz檔案
                compressed = io.BytesIO(response.content)
                with gzip.GzipFile(fileobj=compressed) as gz:
                    data = gz.read().decode('utf-8')
                
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(data)
                
                downloaded.append(local_path)
                print(f"已下載並解壓: {local_name}")
                
            except Exception as e:
                print(f"下載失敗: {filename}, 錯誤: {e}")
        
        if progress_callback:
            progress_callback(total_needed, total_needed, "NPRSUBC下載完成")
        
        return downloaded
    
    def download_all(self, count: int = 10, 
                     progress_callback=None) -> dict:
        """
        下載所有類型的資料
        
        Returns:
            包含各類型已下載檔案路徑的字典
        """
        results = {
            'himsst': [],
            'nprsubt': [],
            'nprsubc': []
        }
        
        def combined_callback(current, total, msg):
            if progress_callback:
                progress_callback(current, total, msg)
        
        results['himsst'] = self.download_himsst(count, combined_callback)
        results['nprsubt'] = self.download_nprsubt(count, combined_callback)
        results['nprsubc'] = self.download_nprsubc(count, combined_callback)
        
        return results


if __name__ == "__main__":
    # 測試下載功能
    downloader = JMADataDownloader()
    
    def show_progress(current, total, msg):
        print(f"[{current}/{total}] {msg}")
    
    results = downloader.download_all(count=3, progress_callback=show_progress)
    
    print("\n下載結果:")
    for data_type, files in results.items():
        print(f"  {data_type}: {len(files)} 筆")
