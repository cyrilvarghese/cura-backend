def clean_code_block(content: str) -> str:
    """
    Removes code block markers from a string if they exist.
    
    Args:
        content (str): The text content that may contain code block markers
        
    Returns:
        str: Cleaned text without code block markers
    """
    if isinstance(content, str) and content.startswith('```'):
        # Remove opening code block with optional language identifier
        content = content.split('\n', 1)[1] if '\n' in content else content
        content = content.replace('```json\n', '').replace('```\n', '').replace('\n```', '')
    return content 