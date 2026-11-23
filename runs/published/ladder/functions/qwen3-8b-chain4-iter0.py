def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        has_filled_below = False
        for r in range(19, -1, -1):
            if board[r][c]:
                has_filled_below = True
            else:
                if has_filled, below:
                    holes += 1
    
    # Calculate tallest column
    tallest = 0
    for c in range(10):
        max_row = -1
        for r in range(20):
            if board[r][c]:
                max_row = r
        if max_row > tallest:
            tallest = max_row
    
    # Calculate surface variance
    heights = []
    for c in range(10):
        max_row = -1
        for r in range(20):
            if board[r][c]:
                max_row = r
        heights.append(max_row)
    average = sum(heights) / 10.0
    variance = sum((h - average)**2 for h in heights)
    
    # Combine metrics with adjusted weights
    score_val = lines_cleared * 100 - holes - tallest - variance
    return float(score_val)
