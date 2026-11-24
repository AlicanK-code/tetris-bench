import math

def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        filled = [row for row in range(20) if board[row][c]]
        max_filled = max(filled) if filled else -1
        for r in range(20):
            if not board[r][c] and max_filled > r:
                holes += 1
    
    # Calculate max height
    max_height = 0
    for c in range(10):
        filled_rows = [row for row in range(20) if board[row][c]]
        if filled_rows:
            current_height = max(filled_rows)
        else:
            current_height = 0
        if current_height > max_height:
            max_height = current_height
    
    # Calculate standard deviation of column heights
    heights = []
    for c in range(10):
        filled_rows = [row for row in range(20) if board[row][c]]
        if filled_rows:
            current_height = max(filled_rows)
        else:
            current_height = 0
        heights.append(current_height)
    
    mean = sum(heights) / len(heights)
    variance = sum((h - mean)**2 for h in heights) / len(heights)
    std_dev = math.sqrt(variance)
    
    # Combine all factors into a score
    return lines_cleared * 100 - holes - max_height - std_dev
