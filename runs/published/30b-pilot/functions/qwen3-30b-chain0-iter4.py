def score(board, placement):
    lines = placement['lines_cleared']
    score_val = lines * 2000.0
    
    holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                for r2 in range(row):
                    if board[r2][col]:
                        holes += 1
                        break
    
    score_val -= holes * 500.0
    
    top_filled = [20] * 10
    for col in range(10):
        for r in range(20):
            if board[r][col]:
                top_filled[col] = r
                break
    
    irregularity = 0
    for col in range(9):
        irregularity += abs(top_filled[col] - top_filled[col+1])
    
    score_val -= irregularity * 150.0
    
    max_top = max(top_filled)
    score_val -= max_top * 50.0
    
    return score_val
