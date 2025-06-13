# Gemini Fullstack LangGraph 快速入門

本專案展示了一個全端應用程式，採用 React 前端和 LangGraph 支援的後端代理。該代理旨在透過動態產生搜尋詞彙、使用 Google 搜尋查詢網路、反思結果以識別知識差距，並反覆調整搜尋，直到能夠提供有充分依據且附有引文的答案，從而對使用者查詢進行全面研究。此應用程式可作為使用 LangGraph 和 Google Gemini 模型建構研究增強型對話式 AI 的範例。

![Gemini Fullstack LangGraph](./app.png)

## 功能

- 💬 全端應用程式，包含 React 前端和 LangGraph 後端。
- 🧠 由 LangGraph 代理提供支援，用於進階研究和對話式 AI。
- 🔍 使用 Google Gemini 模型動態產生搜尋查詢。
- 🌐 透過 Google Search API 整合網路研究。
- 🤔 反思性推理以識別知識差距並調整搜尋。
- 📄 產生包含引文的答案（來自收集的來源）。
- 🔄 在開發過程中支援前端和後端開發的熱重載。

## 專案結構

專案分為兩個主要目錄：

- `frontend/`：包含使用 Vite 建構的 React 應用程式。
- `backend/`：包含 LangGraph/FastAPI 應用程式，包括研究代理邏輯。

## 開始使用：開發與本機測試

請依照下列步驟在本機執行應用程式以進行開發和測試。

**1. 先決條件：**

- Node.js 和 npm (或 yarn/pnpm)
- Python 3.8+
- **`GEMINI_API_KEY`**：後端代理需要 Google Gemini API 金鑰。
    1. 導覽至 `backend/` 目錄。
    2. 透過複製 `backend/.env.example` 檔案來建立名為 `.env` 的檔案。
    3. 開啟 `.env` 檔案並新增您的 Gemini API 金鑰：`GEMINI_API_KEY="YOUR_ACTUAL_API_KEY"`

**2. 安裝相依套件：**

**後端：**

```bash
cd backend
pip install .
```

**前端：**

```bash
cd frontend
npm install
```

**3. 執行開發伺服器：**

**後端與前端：**

```bash
make dev
```
這將執行後端和前端開發伺服器。開啟您的瀏覽器並導覽至前端開發伺服器 URL (例如：`http://localhost:5173/app`)。

_或者，您可以分別執行後端和前端開發伺服器。對於後端，請在 `backend/` 目錄中開啟一個終端機並執行 `langgraph dev`。後端 API 將在 `http://127.0.0.1:2024` 上可用。它還會在 LangGraph UI 中開啟一個瀏覽器視窗。對於前端，請在 `frontend/` 目錄中開啟一個終端機並執行 `npm run dev`。前端將在 `http://localhost:5173` 上可用。_

## 後端代理運作方式 (高階)

後端的核心是定義在 `backend/src/agent/graph.py` 中的 LangGraph 代理。它遵循以下步驟：

![代理流程](./agent.png)

1. **產生初始查詢：** 根據您的輸入，它會使用 Gemini 模型產生一組初始搜尋查詢。
2. **網路研究：** 對於每個查詢，它會使用 Gemini 模型搭配 Google Search API 來尋找相關的網頁。
3. **反思與知識差距分析：** 代理會分析搜尋結果，以判斷資訊是否充足或是否存在知識差距。它會使用 Gemini 模型進行此反思過程。
4. **反覆調整：** 如果發現差距或資訊不足，它會產生後續查詢並重複網路研究和反思步驟 (最多可達設定的最大迴圈次數)。
5. **完成答案：** 一旦研究被認為足夠，代理會使用 Gemini 模型將收集到的資訊整合成一個連貫的答案，包括來自網路來源的引文。

## 部署

在生產環境中，後端伺服器提供最佳化的靜態前端建置。LangGraph 需要一個 Redis 執行個體和一個 Postgres 資料庫。Redis 用作發布/訂閱代理，以啟用來自背景執行的即時輸出串流。Postgres 用於儲存助理、執行緒、執行、持續執行緒狀態和長期記憶體，並以「完全一次」語義管理背景任務佇列的狀態。有關如何部署後端伺服器的更多詳細資訊，請參閱 [LangGraph 文件](https://langchain-ai.github.io/langgraph/concepts/deployment_options/)。以下是如何建置包含最佳化前端建置和後端伺服器的 Docker 映像檔，並透過 `docker-compose` 執行它的範例。

_注意：對於 docker-compose.yml 範例，您需要一個 LangSmith API 金鑰，您可以從 [LangSmith](https://smith.langchain.com/settings) 取得。_

_注意：如果您未執行 docker-compose.yml 範例或將後端伺服器公開到公用網際網路，請更新 `frontend/src/App.tsx` 檔案中主機的 `apiUrl`。目前，`apiUrl` 設定為 `http://localhost:8123` (用於 docker-compose) 或 `http://localhost:2024` (用於開發)。_

**1. 建置 Docker 映像檔：**

從**專案根目錄**執行下列指令：
```bash
docker build -t gemini-fullstack-langgraph -f Dockerfile .
```
**2. 執行生產伺服器：**

```bash
GEMINI_API_KEY=<your_gemini_api_key> LANGSMITH_API_KEY=<your_langsmith_api_key> docker-compose up
```

開啟您的瀏覽器並導覽至 `http://localhost:8123/app/` 以查看應用程式。API 將在 `http://localhost:8123` 上可用。

## 使用的技術

- [React](https://reactjs.org/) (搭配 [Vite](https://vitejs.dev/)) - 用於前端使用者介面。
- [Tailwind CSS](https://tailwindcss.com/) - 用於樣式設計。
- [Shadcn UI](https://ui.shadcn.com/) - 用於元件。
- [LangGraph](https://github.com/langchain-ai/langgraph) - 用於建構後端研究代理。
- [Google Gemini](https://ai.google.dev/models/gemini) - 用於查詢產生、反思和答案合成的 LLM。

## 授權

本專案採用 Apache License 2.0 授權。詳情請參閱 [LICENSE](LICENSE) 檔案。
