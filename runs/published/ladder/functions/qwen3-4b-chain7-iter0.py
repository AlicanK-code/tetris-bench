def score(board, placement):
    surface_height = -1
    for row in range(19, -1, -1):
        if any(board[row][col] for col in range(10)):
            surface_height = row
            break
    
    max_col_height = 0
    for j in range(10):
        count = 0
        for i in range(20):
            if board[i][j]:
                count += 1
        if count > max_col_height:
            max_col_height = count
    
    total_empty = 0
    for row in board:
        for cell in row:
            if not cell:
                total_empty += 1
    
    return float(placement["lines_cleared"] * 10 + (100 - surface_height) * 5 + (100 - max_col_height) + total_empty * 2)
