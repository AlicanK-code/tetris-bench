import math

def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        has_filled_above = False
        for r in range(20):
            if board[r][c]:
                has_filled_above = True
            else:
                if has_filled_above:
                    holes += 1
    
    # Calculate column heights
    heights = []
    for c in range(10):
        count = 0
        for r in range(20):
            if board[r][c]:
                count += 1
        heights.append(count)
    
    max_height = max(heights)
    
    # Calculate standard deviation of column heights
    mean = sum(heights) / 10
    variance = sum((h - mean)**2 for h in heights) / 10
    std_dev = math.sqrt(variance)
    
    # Combine all factors with weighted contributions
    return lines_cleared * 100 - holes * 10 - max_height * 5 - std_dev * 5
