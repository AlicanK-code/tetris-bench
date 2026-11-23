import math

def score(board, placement):
    # Calculate column heights
    heights = []
    for col in range(10):
        h = 0
        for row in range(20):
            if board[row][col]:
                h += 1
        heights.append(h)
    
    # Maximum column height
    max_height = max(heights)
    
    # Number of holes
    num_holes = sum((20 - h) for h in heights if h > 0)
    
    # Bumpiness between adjacent columns
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])
    
    # Standard deviation of column heights
    mean_height = sum(heights) / 10.0
    variance = sum((h - mean_height) ** 2 for h in heights) / 10.0
    std_dev = math.sqrt(variance)
    
    # Combine features into a score
    lines_cleared = placement["lines_cleared"]
    score = (lines_cleared * 10) - (max_height * 2) - (num_holes * 3) - (bumpiness * 1) - (std_dev * 1)
    return float(score)
