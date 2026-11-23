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
    
    adjacent_empty = 0
    for (r, c) in placement["cells"]:
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr = r + dr
            nc = c + dc
            if 0 <= nr < 20 and 0 <= nc < 10 and not board[nr][nc]:
                adjacent_empty += 1
                
    return float(lines_cleared * 100 - total_empty * 3 - holes * 5 - max_col_height * 2 - surface_unevenness * 4 - bottom_empty - adjacent_empty)
