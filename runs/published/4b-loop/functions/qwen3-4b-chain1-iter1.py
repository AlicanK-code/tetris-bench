def score(board, placement):
    total_empty = sum(1 for row in board for cell in row if not cell)
    max_col_height = max(sum(1 for r in range(20) if board[r][j]) for j in range(10))
    min_col_height = min(sum(1 for r in range(20) if board[r][j]) for j in range(10))
    
    holes = 0
    for r in range(20):
        for c in range(10):
            if not board[r][c]:
                up_ok = (r > 0) and board[r-1][c]
                down_ok = (r < 19) and board[r+1][c]
                left_ok = (c > 0) and board[r][c-1]
                right_ok = (c < 9) and board[r][c+1]
                if up_ok and down_ok and left_ok and right_ok:
                    holes += 1
    
    surface_unevenness = max_col_height - min_col_height
    return float(placement["lines_cleared"] * 500 - 20 * total_empty - 5 * holes + max_col_height - surface_unevenness * 10)
