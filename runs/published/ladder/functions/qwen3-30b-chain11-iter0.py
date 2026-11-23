def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    holes = 0
    for c in range(10):
        for r in range(20):
            if board[r][c]:
                holes += r
                break
    
    surface_heights = []
    for c in range(10):
        min_row = 20
        for r in range(20):
            if board[r][c]:
                min_row = r
                break
        surface_heights.append(min_row)
    
    max_surface = max(surface_heights)
    
    unevenness = 0
    for c in range(9):
        unevenness += abs(surface_heights[c] - surface_heights[c+1])
    
    base_score = lines_cleared * 100.0 - holes - (max_surface * 5.0) - (unevenness * 0.5)
    
    unique_term = placement["rotation"] / 1000.0 + placement["column"] / 1000.0
    
    return base_score + unique_term
