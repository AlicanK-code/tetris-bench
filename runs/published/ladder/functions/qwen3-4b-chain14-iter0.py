def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    total_holes = 0
    for row in board:
        for cell in row:
            if not cell:
                total_holes += 1
    
    column_heights = [0] * 10
    for j in range(10):
        for i in range(20):
            if board[i][j]:
                column_heights[j] += 1
    
    total = sum(column_heights)
    mean = total / 10.0
    variance = sum((h - mean)**2 for h in column_heights) / 10.0
    
    max_row = -1
    for i in range(20):
        for j in range(10):
            if board[i][j]:
                if i > max_row:
                    max_row = i
    
    smoothness_score = 100 - (variance * 50)
    score_value = lines_cleared * 100 + (200 - total_holes) + smoothness_score - (max_row * 5)
    
    return float(score_value)
