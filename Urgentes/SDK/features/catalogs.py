# features/catalogs.py
# -*- coding: utf-8 -*-

class CatalogManager:
    def __init__(self, sdk):
        self.sdk = sdk
        self.data = {
            "concepto": [],
            "serie": [],
            "cliente": [],
            "producto": [],
            "agente": [],
            "almacen": [],
            "moneda": [],
        }

    def load_all(self, logger=print) -> int:
        total = 0
        def load(name, fn):
            nonlocal total
            try:
                items = fn() or []
                self.data[name] = items
                logger(f"Catálogo {name}: {len(items)}")
                total += len(items)
            except Exception as e:
                logger(f"Catálogo {name}: omitido ({e})")

        load("concepto", self.sdk.listar_conceptos)
        load("serie",    self.sdk.listar_series)
        load("cliente",  self.sdk.listar_clientes)
        load("producto", self.sdk.listar_productos)
        load("agente",   self.sdk.listar_agentes)
        load("almacen",  self.sdk.listar_almacenes)
        load("moneda",   self.sdk.listar_monedas)
        return total

    def get(self, kind: str):
        return self.data.get(kind, [])
