# Twitch 精華下載工具

## 簡介
Twitch 精華下載工具是一個基於 Python 和 PyQt6 的桌面應用程式，讓使用者能夠輕鬆下載 Twitch 上的精華片段（Highlights）。只需提供有效的 ACCESS TOKEN 和 CLIENT ID，即可從指定使用者的 Twitch 帳號中獲取並下載精華影片。

## 功能
- **獲取精華片段**: 根據使用者提供的 ACCESS TOKEN，自動獲取 Twitch 使用者的精華影片列表。
- **多執行緒下載**: 使用多執行緒技術，最多同時下載 3 個影片，提升下載效率。
- **進度監控**: 提供實時進度更新，包括下載狀態、完成數量及失敗訊息。
- **中止功能**: 支援隨時中止下載任務。
- **檔案管理**: 自動清理檔案名稱中的無效字元，並支援自訂下載路徑。

## 環境需求
- Python 3.12.4 或更高版本
- 所需套件（見下方安裝步驟）

## 安裝步驟
1. **安裝 Python**  
   確保您的系統已安裝 Python 3.8 或更高版本。可從 [Python 官方網站](https://www.python.org/) 下載。

2. **clone 或下載此專案**  
   使用 Git clone 或直接下載 ZIP 檔案並解壓縮：
   """
   git clone https://github.com/sessioncookie/twitch_highlights_download.git
   """

3. **安裝依賴套件**  
   在專案目錄中執行以下命令安裝所需套件：
   """
   pip install requests PyQt6 imageio-ffmpeg
   """

## 使用方法
1. **獲取 ACCESS TOKEN 和 CLIENT ID**  
   - 前往 [Twitch Token Generator](https://twitchtokengenerator.com/)。
   - 點擊 "取得 ACCESS TOKEN 與 CLIENT ID" 連結，按照指示生成並複製您的 ACCESS TOKEN 和 CLIENT ID。

2. **啟動程式**  
   在專案目錄中執行以下命令：
   """
   python main.py
   """

3. **操作介面**  
   - **輸入 ACCESS TOKEN 和 CLIENT ID**: 在對應欄位中貼上您的憑證。
   - **選擇下載目錄**: 點擊「選擇目錄」按鈕選擇儲存影片的路徑（預設為程式所在目錄）。
   - **開始下載**: 點擊「開始下載」按鈕，程式將自動獲取並下載精華片段。
   - **中止下載**: 如需停止，點擊「中止下載」按鈕。

## 注意事項
- 請確保網路連線穩定，下載過程中斷可能導致失敗。
- 若下載失敗，失敗的影片名稱會顯示在總結中。
- 下載檔案預設儲存為 .mp4 格式。

## 取得TOKEN教學

![教學0](https://github.com/user-attachments/assets/01e7371c-92de-4d37-98d5-d81c491242ec)
![教學1](https://github.com/user-attachments/assets/76aca4cb-36d8-4511-b15a-31ea201d69f8)
![教學2](https://github.com/user-attachments/assets/e8527268-5da5-4d3e-a01b-c513302b43dd)
![教學3](https://github.com/user-attachments/assets/fd24fe91-89df-4153-bc2e-ffc8fb733487)
![教學6](https://github.com/user-attachments/assets/33e73f2e-81d7-4ee7-be5b-0bc14dbac396)
![教學5](https://github.com/user-attachments/assets/9c356955-7858-432a-bf97-d94110acb476)

## 授權
此專案目前未指定具體授權，僅供學習與個人使用。

