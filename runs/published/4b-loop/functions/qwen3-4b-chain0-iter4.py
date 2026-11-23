def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    current_height = -1
    for r in range(20):
        for c in range(10):
            if board[r][c]:
                if r > current_height:
                    current_height = r
    
    columns = [0] * 10
    for c in range(10):
        for r in range(20):
            if board[r][c]:
                columns[c] += 1
    
    total_empty = 20 * 10 - sum(columns)
    
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
    
    surface_unevenness = max(columns) - min(columns)
    
    score_val = lines_cleared * 100 + (20 - current_height) * 50 + total_empty * 3 - surface_unevenness * 15 - holes * 25
    return float(score_val)
