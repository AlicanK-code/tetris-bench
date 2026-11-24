def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for col in range(10):
        filled_rows = []
        for row in range(20):
            if board[row][col]:
                filled_rows.append(row)
        if not filled_rows:
            continue
        lowest_filled_row = min(filled_rows)
        for row in range(lowest_filled_row):
            if not board[row][col]:
                holes += 1
    
    # Calculate column heights
    heights = []
    for col in range(10):
        height = 0
        for row in range(20):
            if board[row][col]:
                height += 1
        heights.append(height)
    tallest = max(heights)
    
    # Calculate surface unevenness
    avg_h = sum(heights) / 10
    surface_unevenness = sum(abs(h - avg_h) for h in heights)
    
    # Compute score with adjusted weights
    weight_lines = 1000
    weight_holes = 300
    weight_tallest = 150
    weight_uneven = 200
    score_val = (lines * weight_lines) - (holes * weight_holes) - (tallest * weight_tallest) - (surface_unevenness * weight_uneven)
    return float(score_val)
