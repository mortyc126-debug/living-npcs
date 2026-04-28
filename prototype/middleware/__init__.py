"""Living NPCs middleware — cognitive layer between Mindcraft and llama-server."""

# Бамп при значимых изменениях логики (фильтры, prompt, модель по умолчанию).
# Виден при старте middleware и в /health — чтобы по логу было ясно,
# какая версия кода реально запущена.
__version__ = "0.3.0-grounder"
