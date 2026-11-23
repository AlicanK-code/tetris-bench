def score(board, placement):
    total_empty = 0
    for row in board:
        for cell in row:
            if not cell:
                total_empty += 1
    
    col_heights = [0] * 10
    for i in range(20):
        for j in range(10):
            if board[i][j]:
                col_heights[j] += 1
    
    mean = sum(col_heights) / 10.0
    variance = sum((h - mean)**2 for h in col_heights) / 10.0
    std_dev = math.sqrt(variance)
    
    if std_dev < 1e-5:
        std_dev = 1e-5
    
    return placement["lines_cleared"] * 10 + total_empty * 2 + (100 / std_dev)
