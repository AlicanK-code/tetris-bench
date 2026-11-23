def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    total_holes = sum(1 for row in board for cell in row if not cell)
    top_holes = sum(1 for row in range(5) for cell in board[row] if not cell)
    
    column_heights = [sum(row[j] for row in board) for j in range(10)]
    max_col_height = max(column_heights)
    avg_col_height = sum(column_heights) / 10.0
    variance = sum((h - avg_col_height) ** 2 for h in column_heights) / 10.0
    
    score_val = lines_cleared * 1000 + \
                (250 - top_holes) * 50 + \
                (250 - max_col_height) * 50 + \
                (250 - variance) * 40 - total_holes * 3
    
    return float(score_val)
