import requests
import urllib.parse
from typing import List, Dict, Optional
import logging
import imageio_ffmpeg as ffmpeg
import subprocess
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QThread, pyqtSignal, QRunnable, QThreadPool, QObject
from PyQt6.QtGui import QFont
import os
import sys
import re
from PyQt6 import QtCore

# 設定 logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 常數
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
GQL_HEADERS = {
    "Client-ID": GQL_CLIENT_ID,
    "Content-Type": "application/json"
}

# 清理檔案名稱的函數
def sanitize_filename(filename: str) -> str:
    """移除或替換檔案名稱中的無效字元並限制長度"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    filename = re.sub(r'[^\w\s\[\]\(\)-]', '_', filename)
    return filename[:100].strip()

# 下載任務的工作類別（QRunnable）
class DownloadWorker(QRunnable):
    def __init__(self, video_info, base_headers, down_path, signals):
        super().__init__()
        self.video_info = video_info
        self.base_headers = base_headers
        self.down_path = down_path
        self.signals = signals
        self._is_running = True

    def stop(self):
        """中止下載"""
        self._is_running = False

    def run(self):
        """執行下載任務"""
        if not self._is_running:
            return  # 如果已經中止，直接退出

        sanitized_title = sanitize_filename(self.video_info['title'])
        output_file = os.path.join(self.down_path, f"{sanitized_title}.mp4")
        if os.path.exists(output_file):
            self.signals.progress.emit(f"{self.video_info['title']}: 檔案已存在，跳過")
            self.signals.finished.emit(True, "skipped")  # 跳過視為完成
            return

        if not self._is_running:
            return  # 再次檢查中止狀態

        vod_id = self.video_info["videoID"]
        m3u8_url = get_twitch_vod_m3u8(vod_id)
        if m3u8_url and self._is_running:
            self.signals.progress.emit(f"{self.video_info['title']}: 開始下載")
            success = download_twitch_vod(m3u8_url, output_file[:-4])
            if self._is_running:
                if success:
                    self.signals.progress.emit(f"{self.video_info['title']}: 下載完成")
                    self.signals.finished.emit(True, "completed")  # 下載成功
                else:
                    self.signals.progress.emit(f"{self.video_info['title']}: 下載失敗")
                    self.signals.finished.emit(False, "failed")  # 下載失敗
            else:
                self.signals.finished.emit(False, "aborted")  # 中止
        else:
            if self._is_running:
                self.signals.progress.emit(f"{self.video_info['title']}: 無法獲取串流連結")
                self.signals.finished.emit(False, "failed")  # 無法獲取連結視為失敗
            else:
                self.signals.finished.emit(False, "aborted")  # 中止

# 信號類別
class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # bool 表示是否成功，str 表示狀態

def get_highlights_rest(base_headers: dict, user_id: str, max_videos: int = 50) -> List[Dict]:
    """獲取 Twitch 使用者的精華片段"""
    base_url = "https://api.twitch.tv/helix/videos"
    params = {"user_id": user_id, "type": "highlight", "first": min(100, max_videos)}
    highlights = []

    try:
        while len(highlights) < max_videos:
            response = requests.get(base_url, headers=base_headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                break

            for video in data["data"]:
                highlights.append({
                    "title": video["title"],
                    "videoID": video["id"],
                    "duration(seconds)": video["duration"],
                    "release_time": video["created_at"],
                    "url": f"https://www.twitch.tv/videos/{video['id']}"
                })
                if len(highlights) >= max_videos:
                    break

            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break
            params["after"] = cursor

        return highlights

    except requests.RequestException as e:
        logger.error(f"獲取精彩片段失敗: {str(e)}")
        return []

def get_user_id(token: str) -> Optional[str]:
    """根據 ACCESS TOKEN 獲取使用者 ID"""
    url = f"https://twitchtokengenerator.com/api/forgot/{token}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["data"]["userid"] if "data" in data and data["data"] else None
    except requests.RequestException as e:
        logger.error(f"獲取使用者 ID 失敗: {str(e)}")
        return None

def get_twitch_vod_m3u8(vod_id: str) -> Optional[str]:
    """獲取 Twitch VOD 的 m3u8 串流 URL"""
    url = "https://gql.twitch.tv/gql"
    query = {
        "query": """
        query($id: ID!) {
            video(id: $id) {
                id
                title
                playbackAccessToken(params: {platform: "web", playerBackend: "mediaplayer", playerType: "site"}) {
                    signature
                    value
                }
            }
        }
        """,
        "variables": {"id": vod_id}
    }

    try:
        response = requests.post(url, headers=GQL_HEADERS, json=query, timeout=10)
        response.raise_for_status()
        data = response.json()

        video_data = data.get("data", {}).get("video")
        if not video_data:
            logger.warning(f"無法找到 VOD: {vod_id}")
            return None

        token = video_data["playbackAccessToken"]["value"]
        sig = video_data["playbackAccessToken"]["signature"]
        encoded_token = urllib.parse.quote(token, safe="")
        m3u8_url = f"https://usher.ttvnw.net/vod/{vod_id}.m3u8?allow_source=true&player=twitchweb&sig={sig}&token={encoded_token}"
        return m3u8_url

    except requests.RequestException as e:
        logger.error(f"獲取 M3U8 URL 失敗: {str(e)}")
        return None

def download_twitch_vod(m3u8_url: str, output_filename: str, file_format: str = "mp4") -> bool:
    """使用 ffmpeg 下載 Twitch VOD，確保路徑有效"""
    try:
        output_dir = os.path.dirname(output_filename)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        ffmpeg_path = ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_path, "-i", m3u8_url, "-c", "copy", "-bsf:a", "aac_adtstoasc",
            f"{output_filename}.{file_format}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=False, check=True)
        logger.info(f"下載完成: {output_filename}.{file_format}")
        return True
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode('utf-8', errors='replace') if e.stderr else "未知錯誤"
        logger.error(f"ffmpeg 下載失敗: {error_output}")
        return False
    except OSError as e:
        logger.error(f"檔案路徑錯誤: {str(e)}")
        return False

class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Twitch精華下載')
        self.resize(800, 600)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(3)
        self.workers = []
        self.total_videos = 0
        self.processed_videos = 0
        self.completed_videos = 0  # 已下載數
        self.skipped_videos = 0   # 已跳過數
        self.failed_videos = []   # 失敗的影片名稱
        self.ui()

    def ui(self):
        """設置使用者介面"""
        layout = QVBoxLayout()
        grid = QGridLayout()
        grid.setSpacing(30)

        self.link_label = QLabel('<a href="https://twitchtokengenerator.com/">取得 ACCESS TOKEN 與 CLIENT ID</a>')
        self.link_label.setOpenExternalLinks(True)
        self.link_label.setStyleSheet("QLabel { font-size: 18px; }")
        grid.addWidget(self.link_label, 0, 0, 1, 2, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.token_input = QLineEdit(self)
        self.token_input.setPlaceholderText("輸入 ACCESS TOKEN")
        self.token_input.setFixedSize(400, 40)
        grid.addWidget(self.token_input, 1, 0, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.id_input = QLineEdit(self)
        self.id_input.setPlaceholderText("輸入 CLIENT ID")
        self.id_input.setFixedSize(400, 40)
        grid.addWidget(self.id_input, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.downfram = QFrame(self)
        self.downfram.setFrameShape(QFrame.Shape.NoFrame)
        down_layout = QGridLayout(self.downfram)
        grid.addWidget(self.downfram, 3, 0, 1, 2, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.down_path = QLineEdit(self)
        self.down_path.setEnabled(False)
        BASE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        self.down_path.setText(BASE_DIR)
        self.down_path.setFixedSize(400, 40)
        down_layout.addWidget(self.down_path, 0, 0, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.down_path_button = QPushButton("選擇目錄")
        self.down_path_button.setFixedSize(100, 40)
        self.down_path_button.clicked.connect(self.path_button)
        down_layout.addWidget(self.down_path_button, 0, 1, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.progress_text = QTextEdit(self)
        self.progress_text.setReadOnly(True)
        self.progress_text.setFixedHeight(150)
        font = QFont()
        font.setPointSize(12)  # 設定字體大小為 12
        self.progress_text.setFont(font)
        grid.addWidget(self.progress_text, 4, 0, 1, 2)

        button_layout = QHBoxLayout()
        self.send_button = QPushButton("開始下載")
        self.send_button.setFixedSize(200, 80)
        self.send_button.clicked.connect(self.button_sent)
        button_layout.addWidget(self.send_button)

        self.stop_button = QPushButton("中止下載")
        self.stop_button.setFixedSize(200, 80)
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        grid.addLayout(button_layout, 5, 0, 1, 2, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addLayout(grid)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def path_button(self):
        """處理選擇目錄按鈕"""
        directory = QFileDialog.getExistingDirectory(self, "選擇目錄")
        if directory:
            self.down_path.setText(directory)

    def button_sent(self):
        """處理開始下載按鈕"""
        oauth_token = self.token_input.text().strip()
        client_id = self.id_input.text().strip()
        down_path = self.down_path.text().strip()

        if not oauth_token or not client_id:
            QMessageBox.warning(self, "輸入錯誤", "請輸入 ACCESS TOKEN 和 CLIENT ID!")
            return

        base_headers = {"Client-ID": client_id, "Authorization": f"Bearer {oauth_token}"}
        user_id = get_user_id(oauth_token)
        if not user_id:
            QMessageBox.warning(self, "錯誤", "無法獲取使用者 ID，請檢查 ACCESS TOKEN!")
            return

        highlights = get_highlights_rest(base_headers, user_id)
        if not highlights:
            self.progress_text.append("未找到任何精華片段！")
            return

        self.total_videos = len(highlights)
        self.processed_videos = 0
        self.completed_videos = 0
        self.skipped_videos = 0
        self.failed_videos = []
        self.send_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_text.clear()
        self.workers.clear()

        for video_info in highlights:
            signals = WorkerSignals()
            worker = DownloadWorker(video_info, base_headers, down_path, signals)
            signals.progress.connect(self.update_progress)
            signals.finished.connect(self.worker_finished)
            self.workers.append((worker, video_info['title']))
            self.thread_pool.start(worker)

    def stop_download(self):
        """中止所有下載任務"""
        for worker, _ in self.workers:
            worker.stop()
        self.thread_pool.clear()  # 清除執行緒池中的任務
        self.stop_button.setEnabled(False)
        self.send_button.setEnabled(True)
        self.show_summary("下載已中止")

    def update_progress(self, message):
        """更新進度訊息"""
        self.progress_text.append(message)

    def worker_finished(self, success, status):
        """單個下載任務完成"""
        self.processed_videos += 1
        if success:
            if status == "completed":
                self.completed_videos += 1
            elif status == "skipped":
                self.skipped_videos += 1
        elif status == "failed":
            worker_title = next((title for worker, title in self.workers if worker.signals.finished == self.sender()), None)
            if worker_title:
                self.failed_videos.append(worker_title)

        progress = int((self.processed_videos / self.total_videos) * 100)
        self.progress_bar.setValue(progress)

        # 檢查是否所有任務都已完成
        if self.processed_videos == self.total_videos or not self.thread_pool.activeThreadCount():
            self.send_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.show_summary("所有下載任務已處理完畢！" if self.processed_videos == self.total_videos else "下載任務已終止或部分完成")

    def show_summary(self, status_message):
        """顯示下載總結"""
        pending_videos = self.total_videos - self.completed_videos - self.skipped_videos- len(self.failed_videos) # 未下載數
        summary = (
            f"{status_message}\n"
            f"總數量: {self.total_videos}\n"
            f"已下載: {self.completed_videos}\n"
            f"已跳過: {self.skipped_videos}\n"
            f"未下載: {pending_videos}\n"
            f"失敗: {len(self.failed_videos)}"
        )
        if self.failed_videos:
            summary += "\n失敗影片名稱:\n" + "\n".join(self.failed_videos)
        self.progress_text.append(summary)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWidget()
    window.show()
    sys.exit(app.exec())