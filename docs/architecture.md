[English](architecture.md) | [繁體中文](architecture.zh-TW.md)

# Architecture

## High-level

```mermaid
flowchart TB
    subgraph user["User Layer"]
        CLI["mem-broom CLI"]
        APP["Your RAG App"]
    end

    subgraph core["forget-rag core"]
        API["ForgettingMemory API"]
        HEAT["heat.py<br/>decay scoring"]
        TIERS["tiers.py<br/>L1 / L2 / L3"]
    end

    subgraph backends["Backends"]
        SQLITE[("SQLite<br/>+ FTS5")]
        VEC[("Vector store<br/>bge-m3")]
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

## Tier transitions

```mermaid
stateDiagram-v2
    [*] --> L1: add()
    L1 --> L2: heat < L1_threshold
    L2 --> L3: heat < L2_threshold
    L1 --> L1: search() boost
    L2 --> L1: search() promote
    L3 --> [*]: user.forget()
```

| Tier | Storage | Searchable via | Cost |
|------|---------|---------------|------|
| L1   | Vector + FTS5 | Hybrid (BM25 + vector) | Highest |
| L2   | FTS5 only | BM25 only | Medium |
| L3   | Archived JSON | Explicit lookup only | Lowest |

## Search data flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as ForgettingMemory
    participant H as heat.py
    participant DB as SQLite

    U->>API: search("query")
    API->>DB: BM25 + FTS5
    DB-->>API: candidate chunks
    API->>H: compute heat for each
    H-->>API: ranked results
    API->>DB: UPDATE last_access, access_count
    API-->>U: top-k results
```
