import yaml
from pathlib import Path
from app.logger import logger

class TextManager:
    """Менеджер текста, поддерживающий i18n через создание нового языка в yaml файле
    """
    def __init__(self, filename: str = "locales/messages.yaml"):
        root_dir = Path(__file__).parent.parent
        path = root_dir / filename
        
        logger.info(f"Looking for yaml at {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            self._texts = yaml.safe_load(f)
    
    def get(self, key: str, lang: str = "ru", **kwargs) -> str:
        """Получает текст из файла с определенным ключом и переводом

        Args:
            key (str): ключ текста, пример: start
            lang (str, optional): выбор языка, по умолчанию ru

        Returns:
            str: возвращает текст по ключу
        """
        text = self._texts.get(lang, {}).get(key)
        
        if text is None:
            return f"Text {key} not found"
        
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing key {e} for translation {key}")
                return text
        
        return text
    
text_manager =TextManager()