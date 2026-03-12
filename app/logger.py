import logging
import datetime
from functools import wraps
import time
import os

# эту штуку заменить на loguru
class Logger:
    def __init__(self):     
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"app_log_{current_time}.log"
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        full_log_path = os.path.join(log_dir, log_filename)
        logging.basicConfig(
            filename=full_log_path,
            filemode="w",
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    def debug(self, description: str):
        self.logger.debug(description)
        
    def info(self, description: str):
        self.logger.info(description)
    
    def warn(self, description: str):
        self.logger.warning(description)
    
    def error(self, description: str):
        self.logger.error(description)
        
    def log_with_timer(self, description: str | None = None):
        """делает лог функции с таймером выполнения
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                if description:
                    self.logger.info(description)
                try:
                    result = await func(*args, **kwargs)
                except Exception as e:
                    self.logger.error(e)
                    raise e
                else:
                    end_time = time.perf_counter()
                    process_time = end_time - start_time
                    self.logger.info(f"{func.__name__} compeleted successfully for {process_time}s")
                    return result
            return wrapper
        return decorator

logger = Logger()
            