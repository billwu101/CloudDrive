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
- [ ] [Backend User 與 Quota](./backend-user-quota.md)
- [ ] [Backend Permission](./backend-permission.md)
- [ ] [Backend DriveItem](./backend-drive-item.md)
- [x] [Backend Storage](./backend-storage.md)
- [ ] [Backend Upload](./backend-upload.md)
- [ ] [Backend Download](./backend-download.md)
- [ ] [Backend Preview](./backend-preview.md)
- [ ] [Backend Trash](./backend-trash.md)
- [ ] [Backend Search](./backend-search.md)
- [ ] [Backend Share](./backend-share.md)
- [ ] [Backend FileVersion](./backend-file-version.md)
- [ ] [Backend ActivityLog](./backend-activity-log.md)

## 前端模組

- [ ] [Frontend Routing](./frontend-routing.md)
- [ ] [Frontend API Client](./frontend-api-client.md)
- [ ] [Frontend Auth](./frontend-auth.md)
- [ ] [Frontend Layout](./frontend-layout.md)
- [ ] [Frontend Drive](./frontend-drive.md)
- [ ] [Frontend Upload](./frontend-upload.md)
- [ ] [Frontend Preview](./frontend-preview.md)
- [ ] [Frontend Share](./frontend-share.md)
- [ ] [Frontend Trash](./frontend-trash.md)
- [ ] [Frontend Search](./frontend-search.md)

## 整合與驗收

- [ ] [Integration、E2E 與驗收](./integration-testing.md)

## 建議執行順序

- [x] 第一階段：Project Setup、Backend Core、Database。
- [x] 第二階段：API Contract、Backend Auth、Backend Storage。
- [ ] 第三階段：Backend DriveItem、Permission、FileVersion、ActivityLog、User Quota。
- [ ] 第四階段：Backend Upload、Download、Preview、Trash、Search、Share。
- [ ] 第五階段：Frontend API Client、Frontend Layout。
- [ ] 第六階段：Frontend Auth、Frontend Drive。
- [ ] 第七階段：Frontend Routing、Upload、Preview。
- [ ] 第八階段：Frontend Trash、Search、Share。
- [ ] 第九階段：Integration、E2E 與驗收。

## 進度統計

| 類別 | 完成 | 總數 |
| --- | ---: | ---: |
| 專案基礎 | 3 | 3 |
| 後端模組 | 3 | 14 |
| 前端模組 | 0 | 10 |
| 整合與驗收 | 0 | 1 |
| 合計 | 6 | 28 |
