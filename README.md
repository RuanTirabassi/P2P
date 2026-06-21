# Album P2P — Sistema Distribuído de Figurinhas

Rede P2P não estruturada para busca e troca de figurinhas via WebSocket + JSON.

## Requisitos

```bash
pip install -r requirements.txt
```

## Como executar

```bash
# Terminal 1 (primeiro nó)
python peer.py --peer-id ALUNO-01 --sticker FIG-01 --port 8080

# Terminal 2
python peer.py --peer-id ALUNO-02 --sticker FIG-02 --port 8081 --peers 127.0.0.1:8080

# Terminal 3
python peer.py --peer-id ALUNO-03 --sticker FIG-03 --port 8082 --peers 127.0.0.1:8080
```

## Comandos CLI

| Comando | Descrição |
|---|---|
| `search FIG-XX` | Busca figurinha na rede via flood TTL=7 |
| `inventory` | Mostra inventário atual |
| `peers` | Lista peers conhecidos e conectados |
| `quit` | Encerra o nó |

## Estrutura

```
├── peer.py          # Nó principal (servidor + cliente WebSocket + CLI)
├── protocols.py     # Builders dos 8 protocolos JSON
├── inventory.py     # Inventário persistente em JSON
├── requirements.txt # websockets>=12.0
└── README.md
```

## Fluxo de troca

```
A busca FIG-12      B (vizinho)        C (tem FIG-12)
  SEARCH(ttl=7) ──►
                    SEARCH(ttl=6) ────►
                                       SEARCH_HIT ──► A
  TRADE_OFFER ────────────────────────────────────► C
                                       TRADE_ACCEPT ◄─ C
                                    TRANSFER_CONFIRM ◄─ C
  [A: -FIG-01 +FIG-12]           [C: -FIG-12 +FIG-01]
```
