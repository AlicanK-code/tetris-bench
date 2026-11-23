def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Correctly calculate holes: empty cells between filled cells
    holes = 0
    for row in range(20):
        for col in range(10):
            if not board[row][col]:
                has_above = any(board[r][col] for r in range(row))
                has_below = any(board[r][col] for r in range(row + 1, 20))
                if has_above and has_below:
                    holes += 1

    # Calculate column heights (number of filled cells from top)
    heights = []
    for col in range(10):
        height = 0
        for row in range(20):
            if board[row][col]:
                height += 1
            else:
                break
        heights.append(height)
    
    # Compute derived metrics
    max_height = max(heights)
    sum_squares = sum(h ** 2 for h in heights)
    surface_roughness = sum(abs(heights[i] - heights[i + 1]) for i in range(9))
    
    # Adjusted scoring formula with optimized weights
    score = (lines_cleared * 1000) - (holes * 80) - (max_height * 60) - (sum_squares * 20) - (surface_roughness * 30)
    
    # Add minimal terms to differentiate placements with identical metrics
    score += placement['rotation'] * 0.01 + placement['column'] * 0.001 + placement['row'] * 0.0001 + ord(placement['kind']) * 0.00001
    
    return float(score)
