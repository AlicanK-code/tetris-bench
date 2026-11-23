def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Compute holes
    holes = 0
    for col in range(10):
        has_filled_above = False
        for row in range(20):
            if board[row][col]:
                has_filled_above = True
            else:
                if has_filled_above:
                    holes += 1
    
    # Compute height
    height = 0
    for col in range(10):
        count = sum(1 for row in range(20) if board[row][col])
        if count > height:
            height = count
    
    # Compute empty rows
    empty_rows = 0
    for row in range(20):
        if all(not cell for cell in board[row]):
            empty_rows += 1
    
    # Combine into score
    score_val = lines_cleared * 100 - holes * 10 - height * 5 + empty_rows * 1
    return score_val
