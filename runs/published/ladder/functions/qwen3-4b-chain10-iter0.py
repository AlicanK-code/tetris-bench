def score(board, placement):
    total_empty = 0
    for row in board:
        total_empty += 10 - sum(row)
    
    column_heights = [0] * 10
    for j in range(10):
        for i in range(20):
            if board[i][j]:
                column_heights[j] += 1
    
    tallest = max(column_heights)
    avg_height = sum(column_heights) / 10.0
    variance = sum((h - avg_height)**2 for h in column_heights) / 10.0
    
    epsilon = 1e-5
    return float(placement["lines_cleared"] * 50 + (200 - total_empty) * 10 + (20 - tallest) * 10 + 5 / (variance + epsilon))
