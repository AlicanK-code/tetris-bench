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
    
    average_col_height = sum(columns) / 10.0
    
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
    
    score_val = lines_cleared * 10 + (20 - current_height) * 5 + (10 - average_col_height) * 3 - holes * 2
    return float(score_val)
