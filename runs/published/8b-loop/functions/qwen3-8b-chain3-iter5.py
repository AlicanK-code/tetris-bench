def score(board, placement):
    holes = 0
    heights = []
    max_h = 0
    for c in range(10):
        filled_above = 0
        count = 0
        for r in range(20):
            if board[r][c]:
                filled_above += 1
                count += 1
            else:
                if filled_above > 0:
                    holes += 1
        max_h = max(max_h, count)
        heights.append(count)
    
    avg_height = sum(heights) / len(heights)
    unevenness = sum(abs(h - avg_height) for h in heights)
    
    bottom_empty = 0
    for r in range(19, -1, -1):
        if all(not cell for cell in board[r]):
            bottom_empty += 1
        else:
            break
    
    lines_cleared = placement["lines_cleared"]
    
    score_val = (lines_cleared * 50) - (holes * 100) - (max_h * 150) - (unevenness * 150) - (bottom_empty * 100)
    return score_val
