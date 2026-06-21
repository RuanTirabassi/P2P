"""
inventory.py — Gerenciamento do inventário de figurinhas do nó
Regras:
  - Cada aluno começa com 28 cópias da sua figurinha autoral
  - A figurinha autoral nunca é removida do disco (arquivo PNG permanece)
  - O sistema impede inventário negativo
"""
import json
import os


class Inventory:
    def __init__(self, peer_id: str, own_sticker_id: str, filepath: str = "inventory.json"):
        self.peer_id = peer_id
        self.own_sticker_id = own_sticker_id
        self.filepath = filepath
        self._stickers: dict = {}  # { sticker_id: quantidade }
        self._load()

    def _load(self):
        """Carrega inventário do arquivo JSON, ou inicializa com 28 cópias da figurinha autoral."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._stickers = data.get("stickers", {})
            print(f"[Inventory] Carregado de {self.filepath}: {self._stickers}")
        else:
            self._stickers = {self.own_sticker_id: 28}
            self._save()
            print(f"[Inventory] Inicializado com 28x {self.own_sticker_id}")

    def _save(self):
        """Persiste inventário em disco."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump({
                "peer_id": self.peer_id,
                "own_sticker_id": self.own_sticker_id,
                "stickers": self._stickers
            }, f, indent=2, ensure_ascii=False)

    def has(self, sticker_id: str) -> bool:
        """Retorna True se o nó possui ao menos 1 unidade da figurinha."""
        return self._stickers.get(sticker_id, 0) > 0

    def quantity(self, sticker_id: str) -> int:
        return self._stickers.get(sticker_id, 0)

    def add(self, sticker_id: str, qty: int = 1):
        """Incrementa quantidade de uma figurinha."""
        self._stickers[sticker_id] = self._stickers.get(sticker_id, 0) + qty
        self._save()
        print(f"[Inventory] +{qty} {sticker_id} → total: {self._stickers[sticker_id]}")

    def remove(self, sticker_id: str, qty: int = 1) -> bool:
        """
        Decrementa quantidade. Retorna False e NÃO altera se causaria inventário negativo.
        """
        current = self._stickers.get(sticker_id, 0)
        if current - qty < 0:
            print(f"[Inventory] ERRO: remover {qty}x {sticker_id} causaria negativo (atual={current})")
            return False
        self._stickers[sticker_id] = current - qty
        self._save()
        print(f"[Inventory] -{qty} {sticker_id} → total: {self._stickers[sticker_id]}")
        return True

    def apply_trade(self, give_sticker_id: str, receive_sticker_id: str) -> bool:
        """
        Aplica troca: remove give_sticker_id e adiciona receive_sticker_id.
        Retorna False se o give_sticker_id não estiver disponível.
        """
        if not self.has(give_sticker_id):
            print(f"[Inventory] Troca impossível: não possui {give_sticker_id}")
            return False
        self.remove(give_sticker_id)
        self.add(receive_sticker_id)
        return True

    def list_all(self) -> dict:
        return dict(self._stickers)

    def __str__(self):
        items = ", ".join(f"{k}:{v}" for k, v in sorted(self._stickers.items()) if v > 0)
        return f"Inventário[{self.peer_id}]: {items}"
