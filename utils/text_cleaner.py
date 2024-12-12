import re

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

    # Use extract_code_blocks to get code blocks
    code_blocks = extract_code_blocks(content)
    
    # Remove code blocks from content
    for block in code_blocks:
        content = content.replace(f'```{block}```', '')

    return content 

def extract_code_blocks(content: str) -> list:
    """
    Extracts all text between triple backticks from a given string.
    
    Args:
        content (str): The text content that may contain code blocks.
        
    Returns:
        list: A list of strings with the content between triple backticks or the original content if no backticks are found.
    """
    if not isinstance(content, str):
        return []  # Return empty list if content is not a string

    # Regex pattern to match text between triple backticks
    pattern = r'```[\w]*\n([\s\S]*?)```'
    
    # Find all matches
    matches = re.findall(pattern, content)
    
    # If no matches found, return the original content as a single-item list
    if not matches:
        return [content]  # Return original content in a list

    # Return trimmed content for each match
    return [match.strip() for match in matches] 