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
        lowest_filled_row = max(filled_rows)
        for row in range(lowest_filled_row):
            if not board[row][col]:
                holes += 1
    
    # Calculate tallest column
    tallest = 0
    for col in range(10):
        filled_rows = []
        for row in range(20):
            if board[row][col]:
                filled_rows.append(row)
        if filled_rows:
            current_height = max(filled_rows)
            if current_height > tallest:
                tallest = current_height
    
    # Calculate column heights for surface_unevenness
    column_heights = []
    for col in range(10):
        max_row = 0
        for row in range(20):
            if board[row][col]:
                max_row = row
        column_heights.append(max_row)
    avg_h = sum(column_heights) / 10
    surface_unevenness = sum(abs(h - avg_h) for h in column_heights)
    
    # Compute score with adjusted weights
    weight_lines = 1000
    weight_holes = 10
    weight_tallest = 5
    weight_uneven = 5
    score_val = (lines * weight_lines) - (holes * weight_holes) - (tallest * weight_tallest) - (surface_unevenness * weight_uneven)
    return score_val
