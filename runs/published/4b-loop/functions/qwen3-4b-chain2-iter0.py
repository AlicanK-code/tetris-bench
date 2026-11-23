def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    total_holes = sum(1 for row in board for cell in row if not cell)
    
    column_heights = [sum(row[j] for row in board) for j in range(10)]
    max_col_height = max(column_heights)
    avg_col_height = sum(column_heights) / len(column_heights)
    variance = sum((h - avg_col_height)**2 for h in column_heights) / len(column_heights)
    
    score_val = lines_cleared * 100.0 + (200.0 - total_holes) * 2.5 + (250.0 - max_col_height) * 1.5 + (250.0 - variance)
    
    return float(score_val)
