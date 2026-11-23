def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate column heights correctly (from top to bottom)
    heights = []
    for col in range(10):
        h = 0
        for row in range(20):
            if board[row][col]:
                h += 1
            else:
                break
        heights.append(h)
    
    # Calculate number of holes
    holes = 0
    for col in range(10):
        highest_filled_row = None
        for row in range(20):
            if board[row][col]:
                highest_filled_row = row
                break
        if highest_filled_row is not None:
            for row in range(highest_filled_row + 1, 20):
                if not board[row][col]:
                    holes += 1
    
    # Calculate bumpiness (sum of absolute differences between adjacent columns)
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])
    
    # Calculate sum of squares and max height
    sum_squares = sum(h**2 for h in heights)
    max_h = max(heights)
    
    # Combine all factors into a score with adjusted weights
    score = lines * 1000 - holes * 20 - bumpiness * 2 - sum_squares * 1.0 - max_h * 5
    
    return float(score)
