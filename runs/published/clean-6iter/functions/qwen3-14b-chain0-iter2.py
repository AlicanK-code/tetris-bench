def score(board, placement):
    # Compute column heights
    heights = []
    for col in range(10):
        h = 20  # default if column is empty
        for row in range(20):
            if board[row][col]:
                h = row
                break
        heights.append(h)
    
    # Calculate holes correctly
    holes = 0
    for col in range(10):
        h = heights[col]
        for row in range(h, 20):
            if not board[row][col]:
                holes += 1
    
    # Calculate metrics
    aggregate_height = sum(heights)
    bumpiness = sum(abs(heights[i] - heights[i+1]) for i in range(9))
    max_height = max(heights)
    
    # Get lines cleared from placement
    lines_cleared = placement["lines_cleared"]
    
    # Weighted score with adjusted coefficients
    score = (lines_cleared * 500) - (holes * 50) - (bumpiness * 20) - (aggregate_height * 10) - (max_height * 100)
    
    # Add a tiny value based on placement parameters to ensure different candidates have different scores
    additional = 0.0001 * (ord(placement["kind"]) + placement["rotation"])
    score += additional
    
    return float(score)
