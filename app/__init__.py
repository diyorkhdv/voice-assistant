"""Voice Intent & Personal Banking Voice Assistant.

A single FastAPI service that implements both interview tasks:
  * V1 — Voice Intent Agent  (STT -> intent classification -> TTS)
  * V2 — Banking Voice Assistant (STT -> structured query -> DB -> NL synthesis -> TTS)
"""
__version__ = "1.0.0"
