def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Compute holes
    holes = 0
    for col in range(10):
        current_filled = False
        for row in range(20):
            if board[row][col]:
                current_filled = True
            else:
                if current_filled:
                    holes += 1
    
    # Compute max height
    max_height = 0
    for col in range(10):
        current_max = -1
        for row in range(20):
            if board[row][col]:
                current_max = row
        if current_max > max_height:
            max_height = current_max
    
    # Compute score
    score_val = lines_cleared * 100 - holes * 10 - max_height
    
    return score_val
