def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Precompute highest filled row (hfr) for each column
    hfr_list = []
    for col in range(10):
        hfr = None
        for row in range(20):
            if board[row][col]:
                hfr = row
                break
        hfr_list.append(hfr)
    
    # Compute maximum column height (number of filled cells from bottom)
    max_height = 0
    for col in range(10):
        height = 0
        for row in range(19, -1, -1):
            if board[row][col]:
                height += 1
            else:
                break
        if height > max_height:
            max_height = height
    
    # Compute number of holes
    holes = 0
    for col in range(10):
        hfr = hfr_list[col]
        if hfr is not None:
            for row in range(hfr + 1, 20):
                if not board[row][col]:
                    holes += 1
    
    # Compute surface roughness (variance of column heights)
    surface_heights = []
    for col in range(10):
        hfr = hfr_list[col]
        surface_heights.append(hfr if hfr is not None else 19)
    mean = sum(surface_heights) / 10
    roughness = sum((h - mean) ** 2 for h in surface_heights)
    
    # Combine factors into a score
    score = (lines_cleared * 10) - (max_height * 2) - (holes * 1) - (roughness * 0.5)
    return float(score)
