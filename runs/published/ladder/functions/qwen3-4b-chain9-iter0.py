def score(board, placement):
    col_heights = [0] * 10
    for i in range(20):
        for j in range(10):
            if board[i][j]:
                col_heights[j] += 1
    
    max_col = max(col_heights)
    holes = 0
    for i in range(20):
        for j in range(10):
            if not board[i][j]:
                if i > 0 and i < 19:
                    if board[i-1][j] and board[i+1][j]:
                        holes += 1
    
    lines_cleared = placement["lines_cleared"]
    return float(lines_cleared * 100 + (20 - max_col) * 50 + (10 - holes))
