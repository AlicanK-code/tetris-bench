def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Compute top empty cells (top 5 rows)
    top_empty = 0
    for r in range(5):
        for c in range(10):
            if not board[r][c]:
                top_empty += 1
    
    # Compute holes
    holes = 0
    for r in range(20):
        for c in range(10):
            if not board[r][c]:
                up = r > 0 and board[r-1][c]
                down = r < 19 and board[r+1][c]
                left = c > 0 and board[r][c-1]
                right = c < 9 and board[r][c+1]
                if up and down and left and right:
                    holes += 1
    
    # Compute column heights
    column_heights = []
    for j in range(10):
        max_row = -1
        for r in range(20):
            if board[r][j]:
                max_row = r
        column_heights.append(max_row)
    
    max_col = max(column_heights)
    min_col = min(column_heights)
    avg_col = sum(column_heights) / 10.0
    unevenness = max_col - min_col
    
    # Combine into score
    score_val = lines_cleared * 100 + top_empty * 5 + (20 - holes) * 5 + (100 - unevenness) * 2
    return float(score_val)
