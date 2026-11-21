def score(board, placement):
    # Calculate column heights correctly (number of filled rows from top)
    heights = []
    for col in range(10):
        height = 0
        for row in range(20):
            if board[row][col]:
                height += 1
            else:
                break
        heights.append(height)
    
    # Calculate holes (empty cells below filled cells in the same column)
    holes = 0
    for col in range(10):
        seen_filled = False
        for row in range(20):
            if board[row][col]:
                seen_filled = True
            else:
                if seen_filled:
                    holes += 1
    
    # Calculate metrics
    aggregate_height = sum(heights)
    max_height = max(heights)
    bumpiness = sum(abs(heights[i] - heights[i+1]) for i in range(9))
    
    # Get lines cleared from placement
    lines_cleared = placement["lines_cleared"]
    
    # Weighted score with adjusted coefficients
    score = (lines_cleared * 1000) - (aggregate_height * 10) - (max_height * 50) - (holes * 50) - (bumpiness * 20)
    
    # Add a small value based on placement parameters to ensure uniqueness
    additional = 0.1 * (ord(placement["kind"]) + placement["rotation"] + placement["column"] + placement["row"])
    score += additional
    
    return float(score)
