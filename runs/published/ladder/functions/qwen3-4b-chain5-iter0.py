def score(board, placement):
    column_counts = [0] * 10
    for r in range(20):
        for c in range(10):
            if board[r][c]:
                column_counts[c] += 1
    
    avg = sum(column_counts) / 10.0
    variance = sum((count - avg)**2 for count in column_counts) / 10.0
    
    total_holes = 0
    for r in range(1, 19):
        for c in range(10):
            if not board[r][c] and board[r-1][c] and board[r+1][c]:
                total_holes += 1
    
    base_score = placement["lines_cleared"] * 5
    variance_score = 100 - (variance * 10)
    holes_score = 50 - total_holes
    return base_score + variance_score + holes_score
