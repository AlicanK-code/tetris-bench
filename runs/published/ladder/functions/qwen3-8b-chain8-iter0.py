def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for col in range(10):
        filled_above = False
        for row in range(20):
            if board[row][col]:
                filled_above = True
            elif filled_above:
                holes += 1
    
    # Calculate column heights and other metrics
    column_heights = []
    for col in range(10):
        current_max = 0
        for row in range(20):
            if board[row][col]:
                current_max = row
        column_heights.append(current_max)
    
    max_height = max(column_heights)
    avg_height = sum(column_heights) / len(column_heights)
    unevenness = sum(abs(h - avg_height) for h in column_heights)
    
    # Combine all terms
    score_value = lines_cleared * 1000 - holes * 100 - max_height * 10 - unevenness * 10
    
    return float(score_value)
