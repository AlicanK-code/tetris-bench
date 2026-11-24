def score(board, placement):
    lines = placement['lines_cleared']
    score_val = lines * 500.0
    
    holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                for r2 in range(row):
                    if board[r2][col]:
                        holes += 1
                        break
    
    score_val -= holes * 20.0
    
    top_filled = [20] * 10
    for col in range(10):
        for r in range(20):
            if board[r][col]:
                top_filled[col] = r
                break
    
    irregularity = 0
    for col in range(9):
        irregularity += abs(top_filled[col] - top_filled[col+1])
    
    score_val -= irregularity * 5.0
    
    max_top = 0
    for col in range(10):
        if top_filled[col] < 20:
            if top_filled[col] > max_top:
                max_top = top_filled[col]
    
    score_val -= max_top * 2.0
    
    unique_id = placement['rotation'] * 100 + placement['column'] * 10 + placement['row']
    score_val += unique_id * 0.001
    
    return score_val
