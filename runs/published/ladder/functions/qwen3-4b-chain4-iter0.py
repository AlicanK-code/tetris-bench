def score(board, placement):
    total_filled = 0
    for row in board:
        total_filled += sum(row)
    
    max_height = 0
    for j in range(10):
        col_height = 0
        for i in range(20):
            if board[i][j]:
                col_height += 1
        if col_height > max_height:
            max_height = col_height
    
    return float(placement["lines_cleared"] * 20 + total_filled * 10 - max_height * 5)
