def score(board, placement):
    # Compute column heights (lowest filled row for each column)
    heights = []
    for c in range(10):
        lowest_row = -1
        for r in reversed(range(20)):
            if board[r][c]:
                lowest_row = r
                break
        heights.append(lowest_row)
    
    max_height = max(heights)
    
    # Compute number of holes
    num_holes = 0
    for c in range(10):
        first_filled_row = None
        for r in range(20):
            if board[r][c]:
                first_filled_row = r
                break
        if first_filled_row is not None:
            for r in range(first_filled_row, 20):
                if not board[r][c]:
                    num_holes += 1
    
    # Compute bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])
    
    # Combine factors with weights
    lines_cleared = placement["lines_cleared"]
    score = (lines_cleared * 10) - (max_height * 0.5) - (num_holes * 2) - (bumpiness * 0.3)
    
    # Add a small unique contribution based on placement parameters
    kind = placement["kind"]
    rotation = placement["rotation"]
    column = placement["column"]
    row = placement["row"]
    score += (ord(kind) + rotation + column + row) * 0.0001
    
    return float(score)
