[English](architecture.md) | [繁體中文](architecture.zh-TW.md)

# 架構

## 高階架構

```mermaid
flowchart TB
    subgraph user["使用者層"]
        CLI["mem-broom CLI"]
        APP["你的 RAG 應用"]
    end

    subgraph core["forget-rag core"]
        API["ForgettingMemory API"]
        HEAT["heat.py<br/>衰減分數"]
        TIERS["tiers.py<br/>L1 / L2 / L3"]
    end

    subgraph backends["後端"]
        SQLITE[("SQLite<br/>+ FTS5")]
        VEC[("向量庫<br/>bge-m3")]
        LC["LangChain<br/>adapter"]
    end

    CLI --> API
    APP --> API
    API --> HEAT
    API --> TIERS
    HEAT --> SQLITE
    TIERS --> SQLITE
    API --> VEC
    API -.optional.-> LC
```

## 分層轉移

```mermaid
stateDiagram-v2
    [*] --> L1: add()
    L1 --> L2: heat < L1 閾值
    L2 --> L3: heat < L2 閾值
    L1 --> L1: search() 加熱
    L2 --> L1: search() 升回
    L3 --> [*]: user.forget()
```

| 層級 | 儲存 | 可搜索 | 成本 |
|------|------|-------|------|
| L1   | 向量 + FTS5 | 混合（BM25 + 向量） | 最高 |
| L2   | 只剩 FTS5 | 只剩 BM25 | 中等 |
| L3   | JSON 歸檔 | 需明確查詢才找得到 | 最低 |

## 搜尋資料流

```mermaid
sequenceDiagram
    participant U as 使用者
    participant API as ForgettingMemory
    participant H as heat.py
    participant DB as SQLite

    U->>API: search("query")
    API->>DB: BM25 + FTS5
    DB-->>API: 候選 chunks
    API->>H: 計算每筆熱度
    H-->>API: 排序結果
    API->>DB: UPDATE last_access, access_count
    API-->>U: top-k 結果
```
