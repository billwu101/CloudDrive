# 雲端硬碟專案總體進度

本文件只追蹤模組是否完成。各模組的細部工作請在對應任務文件中勾選。

模組完成條件：

1. 對應任務文件中的必要 checklist 已完成。
2. 該模組單元測試通過。
3. 與相依模組的接口已驗證。
4. 沒有阻擋 MVP 的已知錯誤。

## 專案基礎

- [x] [Project Setup 與開發環境](./project-setup.md)
- [x] [Database 與 Migration](./database.md)
- [x] [API Contract 與共用 Schema](./api-contract.md)

## 後端模組

- [x] [Backend Core](./backend-core.md)
- [x] [Backend Auth](./backend-auth.md)
- [x] [Backend User 與 Quota](./backend-user-quota.md)
- [x] [Backend Permission](./backend-permission.md)
- [x] [Backend DriveItem](./backend-drive-item.md)
- [x] [Backend Storage](./backend-storage.md)
- [x] [Backend Upload](./backend-upload.md)
- [x] [Backend Download](./backend-download.md)
- [x] [Backend Preview](./backend-preview.md)
- [x] [Backend Trash](./backend-trash.md)
- [x] [Backend Search](./backend-search.md)
- [x] [Backend Share](./backend-share.md)
- [x] [Backend FileVersion](./backend-file-version.md)
- [x] [Backend ActivityLog](./backend-activity-log.md)

## 前端模組

- [x] [Frontend Routing](./frontend-routing.md)
- [x] [Frontend API Client](./frontend-api-client.md)
- [x] [Frontend Auth](./frontend-auth.md)
- [x] [Frontend Layout](./frontend-layout.md)
- [x] [Frontend Drive](./frontend-drive.md)
- [x] [Frontend Upload](./frontend-upload.md)
- [x] [Frontend Preview](./frontend-preview.md)
- [x] [Frontend Share](./frontend-share.md)
- [x] [Frontend Trash](./frontend-trash.md)
- [x] [Frontend Search](./frontend-search.md)

## 整合與驗收

- [x] [Integration、E2E 與驗收](./integration-testing.md)

## 未來擴充（設計完成，尚未實作）

- [ ] [Backend Assistant](./backend-assistant.md) — In-App AI Assistant，設計見 [assistant-design.md](../assistant-design.md)
- [ ] [Frontend Assistant](./frontend-assistant.md) — 聊天面板與串接

## 建議執行順序

- [x] 第一階段：Project Setup、Backend Core、Database。
- [x] 第二階段：API Contract、Backend Auth、Backend Storage。
- [x] 第三階段：Backend DriveItem、ActivityLog、User Quota。（Permission、FileVersion 移至第四階段）
- [x] 第四階段：Backend Upload、Download、Preview、Trash、Search、Share。
- [x] 第五階段：Frontend API Client、Frontend Layout。
- [x] 第六階段：Frontend Auth、Frontend Drive。
- [x] 第七階段：Frontend Routing、Upload、Preview。
- [x] 第八階段：Frontend Trash、Search、Share。
- [x] 第九階段：Integration、E2E 與驗收。

## 進度統計

| 類別 | 完成 | 總數 |
| --- | ---: | ---: |
| 專案基礎 | 3 | 3 |
| 後端模組 | 14 | 14 |
| 前端模組 | 10 | 10 |
| 整合與驗收 | 1 | 1 |
| 合計 | 28 | 28 |
