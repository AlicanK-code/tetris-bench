def score(board, placement):
    filled = 0
    for row in board:
        filled += sum(row)
    total_empty = 200 - filled
    
    tallest_col = 0
    for j in range(10):
        col_height = 0
        for i in range(20):
            if board[i][j]:
                col_height += 1
        if col_height > tallest_col:
            tallest_col = col_height
    
    lines_cleared = placement["lines_cleared"]
    return lines_cleared * 10 + (20 - tallest_col) * 10 - total_empty * 0.5
