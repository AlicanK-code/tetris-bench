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
    
    # Calculate metrics
    max_height = max(heights)
    aggregate_height = sum(heights)
    bumpiness = sum(abs(heights[i] - heights[i+1]) for i in range(9))
    holes = sum(h for h in heights if h < 20)
    
    # Get lines cleared from placement
    lines_cleared = placement["lines_cleared"]
    
    # Weighted score
    score = (lines_cleared * 10) - (holes * 1) - (bumpiness * 1) - (aggregate_height * 0.5) - (max_height * 0.5)
    
    # Add a tiny value based on placement parameters to ensure different candidates have different scores
    additional = 0.0001 * (ord(placement["kind"]) + placement["rotation"])
    score += additional
    
    return score
