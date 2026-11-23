def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    total_empty = sum(1 for row in board for cell in row if not cell)
    
    col_heights = [sum(1 for r in range(20) if board[r][j]) for j in range(10)]
    max_col_height = max(col_heights)
    min_col_height = min(col_heights)
    surface_unevenness = max_col_height - min_col_height

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

    bottom_empty = sum(1 for r in range(15, 20) for c in range(10) if not board[r][c])
    
    return float(lines_cleared * 100 - total_empty * 2.5 - holes * 3 - max_col_height * 0.7 - surface_unevenness * 4.5 + bottom_empty)
