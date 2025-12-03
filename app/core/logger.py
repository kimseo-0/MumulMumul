import logging

def setup_logger(name: str = __name__) -> logging.Logger:
    """로거 설정"""
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # 기존 핸들러가 없으면 추가
    if not logger.handlers:
        logger.addHandler(console_handler)
    
    return logger

logger = setup_logger(__name__)