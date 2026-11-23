def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Count holes
    holes = 0
    for c in range(10):
        filled_above = False
        for r in range(20):
            if board[r][c]:
                filled_above = True
            else:
                if filled_above:
                    holes += 1
    
    # Compute tallest column height
    tallest = 0
    for c in range(10):
        height = 0
        for r in range(20):
            if board[r][c]:
                height += 1
        tallest = max(tallest, height)
    
    # Additional metric: sum of column heights
    sum_heights = 0
    for c in range(10):
        height = 0
        for r in range(20):
            if board[r][c]:
                height += 1
        sum_heights += height
    
    # Return a weighted score combining all metrics
    return lines_cleared * 100 - holes * 5 - tallest * 2 - sum_heights * 0.1
